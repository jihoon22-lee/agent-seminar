"""X1 검증: 같은 기능(팀 용어 조회)을 스킬 / MCP / 플러그인으로 만든 세 폴더를 각각 확인한다."""
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, skill_loaded, tool_called  # noqa: E402

A, B, C = HERE / "a-skill", HERE / "b-mcp", HERE / "c-plugin"
SKILL_DIR = A / ".opencode" / "skills" / "team-glossary"
PROMPT = "우리 팀 용어 사전에서 '카나리'가 무슨 뜻인지 찾아서 알려 줘."
PY = sys.executable


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


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def tool_ids(sb: Sandbox, cwd: Path):
    port = free_port()
    proc = subprocess.Popen([sb.bin, "serve", "--port", str(port), "--hostname", "127.0.0.1"], cwd=str(cwd),
                            env=sb.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(180):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/experimental/tool?provider=opencode&model=big-pickle",
                                            timeout=60) as r:
                    return json.loads(r.read().decode("utf-8"))
            except Exception:  # noqa: BLE001
                time.sleep(1)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    return None


def run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONUTF8": "1"}, **kw)


# 1) 세 폴더의 glossary.json 은 내용이 같다 (같은 기능을 세 방식으로 만든 것)
texts = [p.read_text(encoding="utf-8") for p in (SKILL_DIR / "glossary.json", B / "glossary.json", C / "glossary.json")]
check("세 폴더의 glossary.json 내용이 같다", len(set(texts)) == 1)
glossary = json.loads(texts[0])
check("용어 사전에 6개 용어", len(glossary) == 6)

# 2) 스킬: 스크립트 직접 실행
out = run([PY, str(SKILL_DIR / "scripts" / "lookup.py"), "카나리"])
check("a: lookup.py '카나리' -> 5% / 30분", out.returncode == 0 and "5%" in out.stdout and "30분" in out.stdout, out.stdout + out.stderr)
out = run([PY, str(SKILL_DIR / "scripts" / "lookup.py"), "없는용어"])
check("a: 없는 용어는 목록을 보여 주고 종료코드 1", out.returncode == 1 and "등록된 용어" in out.stdout, out.stdout)

# 3) MCP: 원시 JSON-RPC 핸드셰이크
msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "c", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "lookup_term", "arguments": {"term": "slo"}}},
]
out = run([PY, str(B / "server.py")], input="\n".join(json.dumps(m) for m in msgs) + "\n", timeout=30)
replies = [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
check("b: stdio 서버가 3개 요청에 응답 (알림 제외)", len(replies) == 3, out.stdout + out.stderr)
tools_json = json.dumps(replies[1]["result"]["tools"], ensure_ascii=False) if len(replies) == 3 else ""
check("b: tools/list 에 lookup_term", "lookup_term" in tools_json)
check("b: lookup_term('slo') -> 99.95%", len(replies) == 3 and "99.95%" in replies[2]["result"]["content"][0]["text"])

with Sandbox("x1") as sb:
    skills = {s["name"]: s for s in sb.debug_skills(A)}
    check("a: opencode 가 team-glossary 스킬을 발견", "team-glossary" in skills, str(list(skills)))
    status = sb.mcp_list(B)
    check("b: opencode mcp list -> glossary connected", status.get("glossary") == "connected", str(status))
    ids = tool_ids(sb, C)
    check("c: 플러그인 도구 team_glossary 등록됨", ids is not None and any(t["id"] == "team_glossary" for t in ids), str(ids and [t["id"] for t in ids]))
    plugin_json = next((json.dumps(t, ensure_ascii=False) for t in (ids or []) if t["id"] == "team_glossary"), "")

    # 항상 컨텍스트에 올라가는 양(글자 수). README 표의 근거.
    s = skills.get("team-glossary", {})
    skill_always = len(s.get("name", "")) + len(s.get("description", ""))
    skill_body = len(s.get("content", ""))
    print(f"INFO 스킬: 상시 {skill_always}자 (이름+설명), 로드되면 본문 {skill_body}자 추가")
    print(f"INFO MCP : 상시 {len(tools_json)}자 (도구 스키마)")
    print(f"INFO 플러그인: 상시 {len(plugin_json)}자 (도구 스키마)")
    check("스킬의 상시 비용이 MCP/플러그인 도구 스키마보다 작다", 0 < skill_always < len(tools_json) and skill_always < len(plugin_json),
          f"{skill_always} / {len(tools_json)} / {len(plugin_json)}")

    # 스크립트된 가짜 모델: 세 방식이 실제로 같은 답(카나리 = 5% / 30분)을 돌려주는지 결정적으로 확인한다.
    def scripted(cwd, steps):
        with ScriptedLLM(steps) as llm, Sandbox("x1-fake", global_config=llm.provider_config()) as fake:
            proc = fake.opencode(["run", "-m", "fake/scripted", "--auto", PROMPT], cwd, timeout=240, extra_env={"PWD": str(cwd)})
            return proc.stdout + "\n" + proc.stderr

    out = scripted(A, [[("skill", {"name": "team-glossary"})],
                       [("bash", {"command": 'python .opencode/skills/team-glossary/scripts/lookup.py "카나리"', "description": "용어 조회"})]])
    check("[스크립트] a: 스킬 로드 -> lookup.py 실행 -> 5% / 30분", skill_loaded(out, "team-glossary") and "5%" in out and "30분" in out, out[-700:])
    out = scripted(B, [[("glossary_lookup_term", {"term": "카나리"})]])
    check("[스크립트] b: ⚙ glossary_lookup_term -> 5% / 30분", tool_called(out, "glossary_lookup_term") and "5%" in out and "30분" in out, out[-700:])
    out = scripted(C, [[("team_glossary", {"term": "카나리"})]])
    check("[스크립트] c: ⚙ team_glossary -> 5% / 30분", tool_called(out, "team_glossary") and "5%" in out and "30분" in out, out[-700:])

    if model_enabled():
        out = sb.run_model(PROMPT, cwd=A, extra_env={"PWD": str(A)})
        model_check("a: 모델이 team-glossary 스킬을 로드함", out, skill_loaded(out, "team-glossary"))
        model_check("a: 답에 5% 와 30분이 들어 있다", out, "5%" in out and "30분" in out)
        out = sb.run_model(PROMPT, cwd=B, extra_env={"PWD": str(B)})
        model_check("b: 모델이 glossary_lookup_term 을 호출함", out, tool_called(out, "glossary_lookup_term"))
        model_check("b: 답에 5% 와 30분이 들어 있다", out, "5%" in out and "30분" in out)
        out = sb.run_model(PROMPT, cwd=C, extra_env={"PWD": str(C)})
        model_check("c: 모델이 team_glossary 를 호출함", out, tool_called(out, "team_glossary"))
        model_check("c: 답에 5% 와 30분이 들어 있다", out, "5%" in out and "30분" in out)
finish()
