"""M5 검증: 공유 서버의 인증·감사 로그·도구와, opencode 의 {env:} 치환이 url 에서도 동작하는지 확인한다."""
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, tool_called  # noqa: E402


# --- 스크립트된 가짜 모델 (check.py 안에 복사해 쓰는 조각) ---------------------------------------------
# 무료 모델 한도와 상관없이 "도구가 실제로 실행되는지"를 결정적으로 검증하기 위한 OpenAI 호환 서버 흉내.
# opencode 에 provider 로 등록하면 `opencode run -m fake/scripted` 로 쓸 수 있다.
import json as _json
import threading as _threading
import time as _time
from http.server import BaseHTTPRequestHandler as _Handler, ThreadingHTTPServer as _Server


class _QuietServer(_Server):
    """opencode 가 끝나며 keep-alive 연결을 끊는 것(Windows 의 ConnectionResetError)은 정상이라 traceback 을 찍지 않는다."""

    def handle_error(self, request, client_address):
        if not isinstance(sys.exc_info()[1], (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            super().handle_error(request, client_address)


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

        self.server = _QuietServer(("127.0.0.1", 0), Handler)
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


def rpc(url: str, token: str | None, body: dict | None = None, method: str = "POST", path: str = "/"):
    """(상태코드, 파싱된 JSON 또는 None) 을 돌려준다."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw and r.headers.get("Content-Type", "").startswith("application/json") else raw)
    except urllib.error.HTTPError as e:
        return e.code, None


def call(url, token, name, arguments, rid=10):
    return rpc(url, token, {"jsonrpc": "2.0", "id": rid, "method": "tools/call", "params": {"name": name, "arguments": arguments}})


tmp = Path(tempfile.mkdtemp(prefix="m5-check-"))
tokens = tmp / "tokens.json"
shutil.copy(HERE / "tokens.json", tokens)
default_log = HERE / "logs" / "server.log"
had_log = default_log.exists()
port = free_port()
url = f"http://127.0.0.1:{port}"
# --log-file 을 주지 않아 기본 위치(logs/server.log)에 기록되는지도 함께 본다.
# 서버는 감사 로그를 stderr 에도 찍는다. stderr 를 PIPE 로 받고 읽지 않으면, 파이프 버퍼가 작은 Windows 에서
# 몇 KB 뒤에 서버의 print 가 멈추고 도구 호출이 시간 초과로 끝난다. 그래서 파일로 받는다.
server_err = open(tmp / "server.stderr.log", "w", encoding="utf-8")
server = subprocess.Popen([sys.executable, str(HERE / "server.py"), "--port", str(port), "--tokens", str(tokens)],
                          stdout=subprocess.DEVNULL, stderr=server_err)
try:
    for _ in range(50):
        try:
            if rpc(url, None, method="GET", path="/healthz")[0] == 200:
                break
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    check("GET /healthz 는 인증 없이 200", rpc(url, None, method="GET", path="/healthz")[0] == 200)

    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}}}
    check("토큰 없이 POST 하면 401", rpc(url, None, init)[0] == 401)
    check("틀린 토큰은 401", rpc(url, "nope", init)[0] == 401)
    check("토큰 없는 GET 도 401 (클라이언트에 405 대신 인증 오류가 보이게)", rpc(url, None, method="GET")[0] == 401)
    check("유효한 토큰으로 GET 하면 405", rpc(url, "demo-token-alice-1", method="GET")[0] == 405)
    status, res = rpc(url, "demo-token-alice-1", init)
    check("initialize 성공 + serverInfo", status == 200 and res["result"]["serverInfo"]["name"] == "team-shared", str(res))
    check("알림(initialized)은 202",
          rpc(url, "demo-token-alice-1", {"jsonrpc": "2.0", "method": "notifications/initialized"})[0] == 202)
    status, res = rpc(url, "demo-token-alice-1", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in res["result"]["tools"]] if status == 200 else []
    check("tools/list = oncall_lookup, team_status", names == ["oncall_lookup", "team_status"], str(names))

    _, res = call(url, "demo-token-alice-1", "oncall_lookup", {"team": "platform", "date": "2026-11-18"})
    text = res["result"]["content"][0]["text"]
    check("oncall_lookup(platform, 2026-11-18) -> 1차 carol", "1차 carol" in text and not res["result"]["isError"], text)
    _, res = call(url, "demo-token-alice-1", "oncall_lookup", {"team": "platform", "date": "2027-03-10"})
    text_out = res["result"]["content"][0]["text"]
    check("일정표 밖의 날짜는 오류 없이 주간 순환 배정으로 답한다", not res["result"]["isError"] and "순환" in text_out and "1차" in text_out, text_out)
    _, res = call(url, "demo-token-bob-1", "oncall_lookup", {"team": "payment", "date": "2026-11-05"})
    check("oncall_lookup(payment, 2026-11-05) -> 1차 dana", "1차 dana" in res["result"]["content"][0]["text"])
    _, res = call(url, "demo-token-bob-1", "oncall_lookup", {"team": "nothing"})
    check("없는 팀은 isError", res["result"]["isError"] is True)
    _, res = call(url, "demo-token-carol-1", "team_status", {})
    check("team_status 가 상태 목록을 돌려준다", "payment-api: degraded" in res["result"]["content"][0]["text"])

    # 감사 로그: 누가(user) 어떤 도구를 호출했는지 파일에 남는다
    time.sleep(0.3)
    log = default_log.read_text(encoding="utf-8") if default_log.is_file() else ""
    check("logs/server.log 에 user=alice tool=oncall_lookup 기록", "user=alice tool=oncall_lookup" in log, log[-400:])
    check("logs/server.log 에 user=bob, user=carol 기록", "user=bob tool=oncall_lookup" in log and "user=carol tool=team_status" in log)
    check("거부된 요청도 user=- ... denied(401) 로 기록", "user=- auth" in log and "denied(401)" in log)

    # 토큰 교체: 서버 재시작 없이 새 토큰이 통하고, 지운 토큰은 막힌다
    data = json.loads(tokens.read_text(encoding="utf-8"))
    data["demo-token-alice-2"] = "alice"
    del data["demo-token-alice-1"]
    tokens.write_text(json.dumps(data), encoding="utf-8")
    check("새 토큰(alice-2)은 재시작 없이 통한다", rpc(url, "demo-token-alice-2", init)[0] == 200)
    check("지운 토큰(alice-1)은 바로 막힌다", rpc(url, "demo-token-alice-1", init)[0] == 401)

    with Sandbox("m5") as sb:
        env = {"TEAM_MCP_URL": url + "/", "TEAM_MCP_TOKEN": "demo-token-bob-1"}
        cfg = sb.debug_config(HERE, extra_env=env)
        remote = cfg.get("mcp", {}).get("team-shared", {})
        check("{env:TEAM_MCP_URL} 가 url 에서 치환된다", remote.get("url") == url + "/", json.dumps(remote))
        status = sb.mcp_list(HERE, extra_env=env)
        check("opencode mcp list: team-shared connected", status.get("team-shared") == "connected", str(status))
        status = sb.mcp_list(HERE, extra_env={**env, "TEAM_MCP_TOKEN": "wrong-token"})
        check("틀린 토큰이면 failed", status.get("team-shared") == "failed", str(status))
        status = sb.mcp_list(HERE, extra_env={"TEAM_MCP_URL": "", "TEAM_MCP_TOKEN": "x"})
        check("TEAM_MCP_URL 이 비어 있으면 failed (Invalid MCP URL)", status.get("team-shared") == "failed", str(status))

        # 스크립트된 가짜 모델이 원격 MCP 도구를 부른다: 호출 -> 결과 -> 서버 감사 로그에 user=bob
        steps = [[("team-shared_oncall_lookup", {"team": "platform", "date": "2026-11-18"})], [("team-shared_team_status", {})]]
        with ScriptedLLM(steps) as llm, Sandbox("m5-fake", global_config=llm.provider_config()) as fake:
            proc = fake.opencode(["run", "-m", "fake/scripted", "--auto", "플랫폼 온콜이 누구야?"], HERE, timeout=240,
                                 extra_env={**env, "PWD": str(HERE)})
            out = proc.stdout + "\n" + proc.stderr
        time.sleep(0.3)
        log = default_log.read_text(encoding="utf-8")
        check("[스크립트] ⚙ team-shared_oncall_lookup 호출 + 결과에 carol", tool_called(out, "team-shared_oncall_lookup") and "carol" in out, out[-600:])
        check("[스크립트] 서버 감사 로그에 user=bob 의 두 호출이 남는다",
              "user=bob tool=oncall_lookup" in log and "user=bob tool=team_status" in log, log[-500:])

        if model_enabled():
            out = sb.run_model("team-shared MCP 의 oncall_lookup 으로 platform 팀의 2026-11-18 온콜 1차 담당자가 누구인지 알려 줘.",
                               cwd=HERE, extra_env={**env, "TEAM_MCP_TOKEN": "demo-token-bob-1", "PWD": str(HERE)})
            model_check("모델이 team-shared_oncall_lookup 을 호출함", out, tool_called(out, "team-shared_oncall_lookup"))
            model_check("답에 carol 이 들어 있다", out, "carol" in out)
            time.sleep(0.3)
            log = default_log.read_text(encoding="utf-8")
            model_check("감사 로그에 모델의 호출이 user=bob 으로 남았다", out, "user=bob tool=oncall_lookup" in log
                        and "2026-11-18" in log)
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
    server_err.close()
    shutil.rmtree(tmp, ignore_errors=True)
    if not had_log:
        shutil.rmtree(HERE / "logs", ignore_errors=True)
finish()
