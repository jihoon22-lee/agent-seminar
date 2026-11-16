"""X2 검증: MCP(티켓 DB) + 스킬(절차) + 플러그인(감사 로그·쓰기 제한)이 함께 동작하는지 확인한다.

모델 없이도 "스크립트된 가짜 모델"이 도구를 순서대로 호출하게 해서 세 요소의 연동을 결정적으로 검증한다.
진짜 모델로 한 번 더 보는 검사는 --model 일 때만 돈다.
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, skill_loaded, tool_called  # noqa: E402

PY = sys.executable
AS_OF = "2026-11-17"
PROMPT = "이번 주 payment 서비스 장애 분석 리포트 만들어줘"
REPORT = HERE / "reports" / f"{AS_OF}-payment.md"
AUDIT = HERE / "logs" / "audit.jsonl"

# --- 스크립트된 가짜 모델 (check.py 안에 복사해 쓰는 조각) ---------------------------------------------
# 무료 모델 한도와 상관없이 "도구가 실제로 실행되는지"를 결정적으로 검증하기 위한 OpenAI 호환 서버 흉내.
# opencode 에 provider 로 등록하면 `opencode run -m fake/scripted` 로 쓸 수 있다.
import json as _json
import threading as _threading
import time as _time
from http.server import BaseHTTPRequestHandler as _Handler, ThreadingHTTPServer as _Server


class ScriptedLLM:
    """steps[i] = [(도구이름, 인자dict), ...]  i 번째 응답에서 모델이 호출할 도구들.
    steps 를 다 쓰면 지금까지 받은 도구 결과를 그대로 읽어 주는 최종 문장을 돌려준다."""

    def __init__(self, steps):
        self.steps = steps
        outer = self

        class Handler(_Handler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a):
                pass

            def do_POST(self):
                body = _json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                msgs, tools = body.get("messages", []), body.get("tools") or []
                rounds = sum(1 for m in msgs if m.get("role") == "assistant" and m.get("tool_calls"))
                calls, text = None, "제목"
                if tools:
                    if rounds < len(outer.steps):
                        calls = outer.steps[rounds]
                    else:
                        results = [m.get("content") for m in msgs if m.get("role") == "tool"]
                        text = "도구 결과:\n" + "\n".join(str(r)[:600] for r in results)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()

                def send(raw):
                    self.wfile.write(f"{len(raw):x}\r\n".encode() + raw + b"\r\n")

                def chunk(delta, finish=None):
                    data = {"id": "c1", "object": "chat.completion.chunk", "created": int(_time.time()), "model": "scripted",
                            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                    send(("data: " + _json.dumps(data) + "\n\n").encode())

                chunk({"role": "assistant", "content": ""})
                if calls:
                    for i, (name, args) in enumerate(calls):
                        chunk({"tool_calls": [{"index": i, "id": f"call_{rounds}_{i}", "type": "function",
                                               "function": {"name": name, "arguments": _json.dumps(args, ensure_ascii=False)}}]})
                    chunk({}, "tool_calls")
                else:
                    chunk({"content": text})
                    chunk({}, "stop")
                send(b"data: [DONE]\n\n")
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()

        self.server = _Server(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]

    def provider_config(self):
        return {"provider": {"fake": {"npm": "@ai-sdk/openai-compatible", "name": "Scripted",
                                      "options": {"baseURL": f"http://127.0.0.1:{self.port}/v1", "apiKey": "unused"},
                                      "models": {"scripted": {"name": "scripted", "tool_call": True,
                                                              "limit": {"context": 100000, "output": 4000}}}}}}

    def __enter__(self):
        _threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *_exc):
        self.server.shutdown()
        self.server.server_close()
# -------------------------------------------------------------------------------------------------------


def run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", cwd=str(HERE), **kw)


def audit_entries():
    if not AUDIT.is_file():
        return []
    return [json.loads(line) for line in AUDIT.read_text(encoding="utf-8").splitlines() if line.strip()]


try:
    # 1) 데이터 준비
    out = run([PY, "prepare.py", "--as-of", AS_OF])
    check("prepare.py 가 tickets.db 를 만든다", out.returncode == 0 and (HERE / "tickets.db").is_file(), out.stdout + out.stderr)
    out = run([PY, "prepare.py", "--as-of", AS_OF])
    check("prepare.py 는 여러 번 실행해도 된다 (처음부터 다시 만듦)", out.returncode == 0)
    con = sqlite3.connect(HERE / "tickets.db")
    week = con.execute("SELECT COUNT(*) FROM tickets WHERE service='payment' AND created_at>='2026-11-11'").fetchone()[0]
    prev = con.execute("SELECT COUNT(*) FROM tickets WHERE service='payment' AND created_at>='2026-11-04' AND created_at<'2026-11-11'").fetchone()[0]
    con.close()
    check("payment 티켓: 이번 주가 지난주보다 확연히 많다", week >= 30 and prev <= 10, f"{week} / {prev}")

    # 2) MCP 서버: 원시 JSON-RPC
    def rpc(*calls):
        msgs = [{"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "c", "version": "0"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}]
        for i, (name, args) in enumerate(calls, start=2):
            msgs.append({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}})
        proc = run([PY, "tickets_server.py"], input="\n".join(json.dumps(m) for m in msgs) + "\n", timeout=60)
        return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    replies = rpc(("week_range", {}), ("ticket_stats", {"service": "payment", "from_date": "2026-11-11", "to_date": "2026-11-17"}),
                  ("recent_deploys", {"service": "payment", "from_date": "2026-11-11", "to_date": "2026-11-17"}),
                  ("search_tickets", {"service": "payment", "from_date": "2026-11-13", "to_date": "2026-11-13", "severity": "P1"}),
                  ("get_ticket", {"ticket_id": 99999}))
    names = [t["name"] for t in replies[1]["result"]["tools"]]
    check("MCP: 도구 6개 (쓰기 도구 없음)", sorted(names) == sorted(["week_range", "list_services", "ticket_stats", "search_tickets", "get_ticket", "recent_deploys"]), str(names))
    text = lambda r: r["result"]["content"][0]["text"]  # noqa: E731
    wr = json.loads(text(replies[2]))
    check("MCP: week_range = 기준일까지 최근 7일", (wr["from"], wr["to"], wr["today"]) == ("2026-11-11", "2026-11-17", AS_OF), str(wr))
    st = json.loads(text(replies[3]))
    check("MCP: ticket_stats 피크 일자가 배포 다음 날(2026-11-13)", st["peak_day"]["date"] == "2026-11-13" and st["total"] == week, str(st))
    dep = json.loads(text(replies[4]))
    check("MCP: recent_deploys 에 v2.14.0, v2.14.1", [d["version"] for d in dep["deploys"]] == ["v2.14.0", "v2.14.1"], str(dep))
    sr = json.loads(text(replies[5]))
    check("MCP: search_tickets 가 P1 만 돌려준다", sr["count"] > 0 and all(t["severity"] == "P1" for t in sr["tickets"]), str(sr)[:300])
    check("MCP: 없는 티켓은 isError", replies[6]["result"]["isError"] is True)

    ro = sqlite3.connect(f"{(HERE / 'tickets.db').resolve().as_uri()}?mode=ro", uri=True)
    try:
        ro.execute("DELETE FROM tickets")
        wrote = True
    except sqlite3.OperationalError:
        wrote = False
    finally:
        ro.close()
    check("읽기 전용 연결(mode=ro)로는 DB 를 바꿀 수 없다", not wrote)

    # 3) 플러그인 가드 단위 검사 (node 가 있을 때만)
    node = shutil.which("node")
    if node:
        plugin_url = (HERE / ".opencode" / "plugins" / "audit-guard.js").resolve().as_uri()
        probe = tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8")
        probe.write(f"""
import {{ AuditGuard }} from "{plugin_url}"
import {{ mkdtempSync }} from "node:fs"
import {{ tmpdir }} from "node:os"
import {{ join }} from "node:path"
const dir = mkdtempSync(join(tmpdir(), "guard-"))
const hooks = await AuditGuard({{ directory: dir }})
const tryTool = async (tool, args) => {{
  try {{ await hooks["tool.execute.before"]({{ tool, sessionID: "s", callID: "c" + Math.random() }}, {{ args }}); return "allowed" }}
  catch (e) {{ return "blocked" }}
}}
const out = {{
  report: await tryTool("write", {{ filePath: join(dir, "reports", "a.md") }}),
  rel: await tryTool("write", {{ filePath: "reports/a.md" }}),
  outside: await tryTool("write", {{ filePath: join(dir, "notes.txt") }}),
  traversal: await tryTool("edit", {{ filePath: join(dir, "reports", "..", "x.md") }}),
  patchOk: await tryTool("apply_patch", {{ patchText: "*** Begin Patch\\n*** Add File: reports/b.md\\n+x\\n*** End Patch" }}),
  patchBad: await tryTool("apply_patch", {{ patchText: "*** Begin Patch\\n*** Add File: src/b.py\\n+x\\n*** End Patch" }}),
  read: await tryTool("read", {{ filePath: join(dir, "notes.txt") }}),
  mcp: await tryTool("tickets_ticket_stats", {{ service: "payment" }}),
}}
console.log(JSON.stringify(out))
""")
        probe.close()
        res = subprocess.run([node, probe.name], capture_output=True, text=True, encoding="utf-8", timeout=60)
        Path(probe.name).unlink(missing_ok=True)
        try:
            got = json.loads(res.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
        check("가드(node 단위 검사): reports/ 안(절대·상대 경로)은 허용", got.get("report") == "allowed" and got.get("rel") == "allowed", res.stdout + res.stderr)
        check("가드(node 단위 검사): reports/ 밖, '..' 우회는 차단", got.get("outside") == "blocked" and got.get("traversal") == "blocked", res.stdout + res.stderr)
        check("가드(node 단위 검사): apply_patch 의 대상 경로도 검사", got.get("patchOk") == "allowed" and got.get("patchBad") == "blocked", res.stdout + res.stderr)
        check("가드(node 단위 검사): 읽기·MCP 도구는 막지 않는다", got.get("read") == "allowed" and got.get("mcp") == "allowed", res.stdout + res.stderr)
    else:
        print("[SKIP] node 가 없어 가드 단위 검사는 건너뜀 (아래 스크립트 실행 검사가 같은 동작을 확인한다)")

    # 4) opencode 가 세 요소를 인식하는가
    with Sandbox("x2") as sb:
        env = {"PWD": str(HERE)}
        check("opencode mcp list: tickets connected", sb.mcp_list(HERE, extra_env=env).get("tickets") == "connected")
        skills = {s["name"] for s in sb.debug_skills(HERE, extra_env=env)}
        check("스킬 incident-analysis 발견", "incident-analysis" in skills, str(skills))
        cfg = sb.debug_config(HERE, extra_env=env)
        check("플러그인 audit-guard.js 가 설정에 잡힌다", any("audit-guard.js" in str(p) for p in cfg.get("plugin", [])), str(cfg.get("plugin")))

    # 5) 스크립트된 가짜 모델로 종단 간 실행
    tpl = HERE / ".opencode" / "skills" / "incident-analysis" / "templates" / "report.md"
    steps = [
        [("skill", {"name": "incident-analysis"})],
        [("tickets_week_range", {}), ("tickets_week_range", {"offset": 1})],
        [("tickets_ticket_stats", {"service": "payment", "from_date": "2026-11-11", "to_date": "2026-11-17"}),
         ("tickets_ticket_stats", {"service": "payment", "from_date": "2026-11-04", "to_date": "2026-11-10"})],
        [("tickets_search_tickets", {"service": "payment", "from_date": "2026-11-13", "to_date": "2026-11-14", "severity": "P1"}),
         ("tickets_recent_deploys", {"service": "payment", "from_date": "2026-11-11", "to_date": "2026-11-17"})],
        [("read", {"filePath": str(tpl)})],
        [("write", {"filePath": str(HERE / "notes.txt"), "content": "메모"})],   # 가드가 막아야 한다
        [("write", {"filePath": str(REPORT), "content": "# payment 장애 분석 리포트\n\nv2.14.0 배포 직후 급증\n"})],
    ]
    with ScriptedLLM(steps) as llm, Sandbox("x2-fake", global_config=llm.provider_config()) as fake:
        proc = fake.opencode(["run", "-m", "fake/scripted", "--auto", PROMPT], HERE, timeout=300, extra_env={"PWD": str(HERE)})
        out = proc.stdout + "\n" + proc.stderr
    check("[스크립트] 스킬 incident-analysis 로드", skill_loaded(out, "incident-analysis"), out[-800:])
    check("[스크립트] MCP 도구 호출 (tickets_ticket_stats)", tool_called(out, "tickets_ticket_stats"), out[-800:])
    check("[스크립트] reports/ 밖 쓰기(notes.txt)는 플러그인이 차단", "[audit-guard]" in out and not (HERE / "notes.txt").exists(), out[-800:])
    check("[스크립트] reports/<날짜>-payment.md 는 저장됨", REPORT.is_file() and "v2.14.0" in REPORT.read_text(encoding="utf-8"))
    entries = audit_entries()
    tools_logged = {e.get("tool") for e in entries}
    check("[스크립트] 감사 로그에 skill / MCP / read / write 호출이 모두 있다",
          {"skill", "tickets_week_range", "tickets_ticket_stats", "read", "write"} <= tools_logged, str(sorted(tools_logged)))
    check("[스크립트] 감사 로그에 차단 기록(blocked)이 남는다",
          any(e.get("phase") == "blocked" and e.get("tool") == "write" for e in entries))
    check("[스크립트] MCP 결과 크기가 기록된다 (outputChars > 0)",
          any(e.get("phase") == "result" and e.get("tool") == "tickets_ticket_stats" and e.get("outputChars", 0) > 100 for e in entries))

    # 6) 진짜 모델 (선택)
    if model_enabled():
        shutil.rmtree(HERE / "reports", ignore_errors=True)
        (HERE / "reports").mkdir()
        AUDIT.unlink(missing_ok=True)
        with Sandbox("x2-model") as sb:
            out = sb.run_model(PROMPT, cwd=HERE, extra_env={"PWD": str(HERE)}, timeout=600)
        model_check("모델이 incident-analysis 스킬을 로드함", out, skill_loaded(out, "incident-analysis"))
        model_check("모델이 tickets MCP 도구를 호출함", out, tool_called(out, "tickets_"))
        reports = sorted((HERE / "reports").glob("*.md"))
        model_check("reports/ 에 리포트가 저장됨", out, bool(reports))
        model_check("리포트가 v2.14.0 배포를 원인 후보로 언급", out, bool(reports) and "v2.14.0" in reports[0].read_text(encoding="utf-8"))
        model_check("감사 로그에 tickets_ 호출이 기록됨", out, any(str(e.get("tool", "")).startswith("tickets_") for e in audit_entries()))
finally:
    # 검사가 만든 것은 지운다 (모두 .gitignore 대상이지만 다음 실행에 영향을 주지 않도록)
    for name in ("reports", "logs"):
        shutil.rmtree(HERE / name, ignore_errors=True)
    (HERE / "tickets.db").unlink(missing_ok=True)
    (HERE / "notes.txt").unlink(missing_ok=True)
finish()
