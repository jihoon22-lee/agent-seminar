"""M4 check: HTTP 서버(Streamable HTTP)의 원시 동작과 opencode remote 연결을 확인한다. 서버는 check.py가 직접 띄우고 끝에 종료한다."""
import json
import os
import socket
import subprocess
import sys
import pathlib
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402  (모델 없이 결정적으로 도구 호출을 시험하는 가짜 모델 서버)


def scripted_call(sb, cwd, tool, args, extra_env=None):
    """가짜 모델이 `tool`을 `args`로 부르게 한다. 반환: (opencode 출력, 모델에게 제공된 도구 이름들, 모델에게 돌아간 도구 결과 텍스트들)."""
    with FakeLLM(script=[("tool", tool, args), "DONE"]) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "PYTHONUTF8": "0"}
        env.update(extra_env or {})
        proc = sb.opencode(["run", "-m", "fake/echo", "--auto", "go"], cwd, timeout=120, extra_env=env)
        requests = llm.main_requests()
        names = FakeLLM.tool_names(requests[0]) if requests else []
        results = []
        for request in requests:
            for message in request["messages"]:
                text = llm.message_text(message)
                if message.get("role") == "tool" and text not in results:
                    results.append(text)
    return proc.stdout + proc.stderr, names, results
SERVER = HERE / "server.py"
PORT = 3917
URL = f"http://127.0.0.1:{PORT}/mcp"
TOKEN = "demo-" + "token-123"       # 가짜 값


def clean_env(**extra):
    """자식 프로세스용 환경: PYTHONUTF8/PYTHONIOENCODING을 제거해 Windows 기본 인코딩(cp949) 상태에서도 서버가 동작하는지 확인한다."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env.update(extra)
    return env


def tool_seen(transcript, name):
    """성공(⚙)뿐 아니라 실패(✗, isError 결과)한 호출도 포함해 도구 이름이 transcript에 나오는지 본다."""
    return any(name in line for line in transcript.splitlines() if line.lstrip().startswith(("⚙", "✗", "→")))


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}}}


def http(method, url=URL, body=None, headers=None, raw=None):
    """(상태, 헤더, 본문 바이트). 4xx/5xx도 예외 없이 돌려준다."""
    data = raw if raw is not None else (json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.headers, err.read()


def auth(token=TOKEN):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"}


def start_server(port=PORT, token=TOKEN, extra_env=None, log_path=None):
    env = clean_env()
    env.pop("API_TOKEN", None)
    env.pop("LOG_LEVEL", None)
    if token is not None:
        env["API_TOKEN"] = token
    env.update(extra_env or {})
    log = open(log_path, "wb") if log_path else subprocess.DEVNULL
    proc = subprocess.Popen([sys.executable, str(SERVER), "--http", "--port", str(port)], cwd=str(HERE), env=env,
                            stdout=subprocess.DEVNULL, stderr=log)
    return proc, log


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_ready(proc, port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return True
        except OSError:
            time.sleep(0.2)
    return False


def stop(proc, log=None):
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    if log not in (None, subprocess.DEVNULL):
        log.close()


# --- 설정 파일 ------------------------------------------------------------------------------------
config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
remote = config["mcp"]["glossary-remote"]
check("opencode.json: remote 항목 (url, headers에 {env:DEMO_TOKEN}, oauth:false), model 키 없음",
      remote["type"] == "remote" and remote["url"] == URL and remote["headers"]["Authorization"] == "Bearer {env:DEMO_TOKEN}"
      and remote["oauth"] is False and "model" not in config)

# --- 토큰 없이 --http 로 시작하면 거부 -----------------------------------------------------------------
OTHER_PORT = free_port()
proc, log = start_server(port=OTHER_PORT, token=None)
try:
    code = proc.wait(timeout=10)
except subprocess.TimeoutExpired:
    code = None
    stop(proc, log)
check("API_TOKEN 없이 --http로 시작하면 서버가 종료한다 (기본이 안전한 쪽)", code not in (None, 0), f"code={code}")

# --- 다른 포트 지정 (--port) ---------------------------------------------------------------------------
proc, log = start_server(port=OTHER_PORT)
try:
    ok = wait_ready(proc, OTHER_PORT)
    status, _, _ = http("POST", f"http://127.0.0.1:{OTHER_PORT}/mcp", INIT, auth())
    check("--port 로 포트를 바꿀 수 있다", ok and status == 200, f"ready={ok} status={status}")
finally:
    stop(proc, log)

# --- 원시 HTTP 동작 ---------------------------------------------------------------------------------------
_fd, _name = tempfile.mkstemp(prefix="m4-check-server-", suffix=".log")
os.close(_fd)
tmp_log = pathlib.Path(_name)
proc, log = start_server(extra_env={"LOG_LEVEL": "DEBUG"}, log_path=tmp_log)
try:
    ready = wait_ready(proc, PORT)
    check(f"서버가 127.0.0.1:{PORT}에서 시작한다", ready, "포트가 이미 사용 중이면 이전에 띄운 서버를 종료하세요")
    if ready:
        status, headers, body = http("POST", body=INIT, headers=auth())
        reply = json.loads(body.decode("utf-8"))
        check("POST initialize -> 200 application/json, protocolVersion echo",
              status == 200 and headers.get_content_type() == "application/json" and reply["result"]["protocolVersion"] == "2025-11-25",
              f"{status} {headers.get('Content-Type')} {body[:200]}")
        status, headers, body = http("POST", body={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=auth())
        check("POST 알림(id 없음) -> 202, 본문 없음", status == 202 and body == b"", f"{status} {body!r}")
        status, _, body = http("POST", body={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=auth())
        names = [t["name"] for t in json.loads(body)["result"]["tools"]]
        check("POST tools/list -> lookup_term, list_terms, server_info", names == ["lookup_term", "list_terms", "server_info"], str(names))
        status, headers, body = http("POST", body={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                                    "params": {"name": "lookup_term", "arguments": {"term": "카나리"}}}, headers=auth())
        text = json.loads(body.decode("utf-8"))["result"]["content"][0]["text"]
        check("한글이 HTTP 본문(UTF-8)으로 깨지지 않고 왕복한다", "일부(예: 5%)에만 먼저 내보내" in text and "utf-8" in headers.get("Content-Type", "").lower(), text)
        status, _, body = http("POST", body={"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                              "params": {"name": "lookup_term", "arguments": {"term": "없는용어"}}}, headers=auth())
        check("없는 용어 -> 200 + isError:true (HTTP 오류가 아니다)", status == 200 and json.loads(body)["result"]["isError"] is True)
        status, _, body = http("POST", body={"jsonrpc": "2.0", "id": 5, "method": "nope"}, headers=auth())
        check("모르는 method -> 200 + JSON-RPC error -32601", status == 200 and json.loads(body)["error"]["code"] == -32601)
        status, _, _ = http("POST", raw=b"{broken", headers=auth())
        check("깨진 JSON -> 400", status == 400)

        status, headers, _ = http("GET", headers={"Authorization": f"Bearer {TOKEN}", "Accept": "text/event-stream"})
        check("GET (인증됨) -> 405, Allow: POST", status == 405 and headers.get("Allow") == "POST", f"{status}")
        status, headers, _ = http("POST", body=INIT, headers=auth("wrong-token"))
        check("토큰이 다르면 POST -> 401 + WWW-Authenticate: Bearer", status == 401 and headers.get("WWW-Authenticate") == "Bearer", f"{status}")
        status, _, _ = http("POST", body=INIT, headers={"Content-Type": "application/json"})
        check("Authorization 헤더가 없으면 POST -> 401", status == 401)
        status, _, _ = http("POST", body=INIT, headers={**auth(), "Authorization": "Bearer "})
        check("'Bearer '(빈 토큰)도 401", status == 401)
        status, _, _ = http("GET", headers={"Accept": "text/event-stream"})
        check("인증 없는 GET -> 401 (405보다 인증이 먼저)", status == 401)
        status, _, _ = http("POST", body=INIT, headers={**auth(), "Origin": "https://evil.example"})
        check("낯선 Origin 헤더 -> 403 (DNS 리바인딩 방어)", status == 403)
        status, _, _ = http("POST", body=INIT, headers={**auth(), "Origin": "http://localhost:3000"})
        check("localhost Origin은 허용", status == 200)
        status, _, _ = http("POST", url=f"http://127.0.0.1:{PORT}/other", body=INIT, headers=auth())
        check("다른 경로 -> 404", status == 404)

        # --- http_probe.py ---------------------------------------------------------------------------
        probe = subprocess.run([sys.executable, str(HERE / "http_probe.py")], cwd=str(HERE), capture_output=True, timeout=60,
                               env=clean_env(DEMO_TOKEN=TOKEN))
        out = probe.stdout.decode("utf-8", "replace")
        check("http_probe.py가 원시 HTTP 요청/응답을 출력한다 (200, 202, 405, 401 포함)",
              probe.returncode == 0 and all(s in out for s in ("HTTP 200", "HTTP 202", "HTTP 405", "HTTP 401")),
              out[-500:] + probe.stderr.decode("utf-8", "replace")[-300:])

        # --- opencode -----------------------------------------------------------------------------
        with Sandbox("m4") as sb:
            status = sb.mcp_list(HERE, extra_env={"DEMO_TOKEN": TOKEN, "PYTHONUTF8": "0"})
            check("opencode mcp list: glossary-remote connected (올바른 토큰)", status.get("glossary-remote") == "connected", str(status))
            wrong = sb.opencode(["mcp", "list"], HERE, extra_env={"DEMO_TOKEN": "wrong-token"})
            check("토큰이 틀리면 failed, 오류 메시지에 401이 보인다 (oauth:false)",
                  "failed" in wrong.stdout and "401" in wrong.stdout, wrong.stdout)
            empty = sb.opencode(["mcp", "list"], HERE, extra_env={"DEMO_TOKEN": ""})
            check("DEMO_TOKEN이 비어 있어도 failed (Bearer 뒤가 비어 401)", "failed" in empty.stdout and "401" in empty.stdout, empty.stdout)

            out, names, results = scripted_call(sb, HERE, "glossary-remote_lookup_term", {"term": "롤백"}, {"DEMO_TOKEN": TOKEN})
            check("(가짜 모델) 원격 서버의 도구 glossary-remote_*가 모델에게 제공되고 한글 결과가 HTTP로 돌아온다",
                  "glossary-remote_lookup_term" in names and "glossary-remote_server_info" in names
                  and any("직전의 정상 버전" in r for r in results), f"{names} {results}")
            out, names, results = scripted_call(sb, HERE, "glossary-remote_server_info", {}, {"DEMO_TOKEN": TOKEN})
            check("(가짜 모델) server_info가 TRANSPORT=http를 보고한다 (원격 서버가 실제로 응답했다)",
                  any("TRANSPORT=http" in r for r in results), str(results))

            # oauth:false 유무에 따른 차이: 401을 받았을 때 OAuth 탐색 요청(.well-known, /register)을 보내는가
            def probe_count(oauth_value):
                cfg = json.loads(json.dumps(config))
                if oauth_value is None:
                    cfg["mcp"]["glossary-remote"].pop("oauth")
                with tempfile.TemporaryDirectory() as tmp:
                    (pathlib.Path(tmp) / "opencode.json").write_text(json.dumps(cfg), encoding="utf-8")
                    before = tmp_log.read_text(encoding="utf-8", errors="replace").count("/.well-known/")
                    sb.opencode(["mcp", "list"], tmp, extra_env={"DEMO_TOKEN": "wrong-token"})
                    time.sleep(0.5)
                    return tmp_log.read_text(encoding="utf-8", errors="replace").count("/.well-known/") - before
            with_false, without_key = probe_count(False), probe_count(None)
            check("oauth:false이면 401 후에도 OAuth 탐색(.well-known) 요청을 보내지 않고, 키가 없으면 보낸다",
                  with_false == 0 and without_key > 0, f"oauth:false -> {with_false}회, oauth 키 없음 -> {without_key}회")

            if model_enabled():
                # PYTHONUTF8=0: Sandbox가 켜 둔 UTF-8 모드를 꺼서 Windows 기본 인코딩 상태에서 시험한다
                out = sb.run_model("glossary-remote 도구로 롤백이 무슨 뜻인지 찾아줘.", HERE,
                                   extra_env={"PWD": str(HERE), "DEMO_TOKEN": TOKEN, "PYTHONUTF8": "0"})
                model_check("모델이 glossary-remote_lookup_term(원격 서버)을 호출했다", out, tool_seen(out, "glossary-remote_lookup_term"))
                model_check("한글 결과가 깨지지 않고 답변에 반영됐다 (롤백 정의의 일부가 나온다)", out, any(w in out for w in ("직전의 정상 버전", "되돌리", "정상 버전")))
                print(out[-600:])
finally:
    stop(proc, log)
    tmp_log.unlink(missing_ok=True)
finish()
