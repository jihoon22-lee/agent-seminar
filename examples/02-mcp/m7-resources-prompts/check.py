"""m7 검증: MCP resources / prompts 가 opencode 1.19.5 에서 어떻게 보이는가.

모델 없이(가짜 LLM 사용) 확인하는 것:
  - 서버가 resources/prompts 를 정상 응답한다 (원시 JSON-RPC)
  - `opencode mcp list` 에서 connected
  - `opencode serve` 의 GET /command 에 source=mcp 명령, GET /experimental/resource 에 리소스
  - `opencode run --command` 로 MCP 프롬프트가 실행되고 $1 이 치환된다
  - @리소스 첨부(파일 파트 source=resource)가 resources/read 결과를 모델 입력에 넣는다
  - 모델이 받는 도구 목록에 list_mcp_resources / read_mcp_resource 가 있다
`--model` 을 주면 실제 모델이 read_mcp_resource 를 호출하는지도 (soft) 확인한다.
"""
import json
import os
import pathlib
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import MODEL_UNAVAILABLE, Sandbox, check, finish, model_check, model_enabled, tool_called  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402
from inspect_server import http_json, mcp_commands, mcp_resources  # noqa: E402

PY = sys.executable


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def rpc(proc, mid, method, params=None):
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def stop(proc):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


# --- 1. 서버 단독: 원시 JSON-RPC -------------------------------------------------
srv = subprocess.Popen([PY, "server.py"], cwd=HERE, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
try:
    init = rpc(srv, 1, "initialize", {"protocolVersion": "2025-06-18"})
    caps = init["result"]["capabilities"]
    check("initialize: tools/resources/prompts capability 선언", {"tools", "resources", "prompts"} <= set(caps), str(caps))
    res = rpc(srv, 2, "resources/list")["result"]["resources"]
    check("resources/list: 런북 3개", len(res) == 3 and res[0]["uri"].startswith("runbook://"), str(res))
    body = rpc(srv, 3, "resources/read", {"uri": "runbook://payment/restart"})["result"]["contents"][0]
    check("resources/read: 한글 본문", "결제 서비스 재시작" in body["text"], str(body)[:200])
    err = rpc(srv, 4, "resources/read", {"uri": "runbook://nope/x"})
    check("resources/read: 없는 URI 는 오류 응답", "error" in err, str(err))
    prompts = rpc(srv, 5, "prompts/list")["result"]["prompts"]
    check("prompts/list: incident-report, review-checklist", [p["name"] for p in prompts] == ["incident-report", "review-checklist"])
    got = rpc(srv, 6, "prompts/get", {"name": "incident-report", "arguments": {"ticket_id": "INC-1"}})["result"]
    check("prompts/get: 인자가 본문에 들어감", "INC-1" in got["messages"][0]["content"]["text"])
    tools = rpc(srv, 7, "tools/list")["result"]["tools"]
    check("tools/list: 도구 1개", [t["name"] for t in tools] == ["list_runbooks"])
finally:
    stop(srv)

# --- 2. opencode 쪽 관찰 (가짜 LLM 이라 결정적) ---------------------------------------
def last_user_text(llm, since):
    main = [r for r in llm.requests[since:] if r.get("tools")]
    return (FakeLLM.message_text(main[-1]["messages"][-1]) if main else ""), main


with FakeLLM() as llm, Sandbox("m7") as sb:
    # PWD: `opencode run` 은 프로세스 cwd 가 아니라 환경변수 PWD 로 프로젝트 폴더를 정한다.
    # 부모 셸의 PWD 가 그대로 넘어가면 엉뚱한 폴더(MCP 설정 없음)에서 실행되므로 직접 맞춘다.
    llm_env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "PWD": str(HERE)}

    status = sb.mcp_list(HERE)
    check("opencode mcp list: runbooks connected", status.get("runbooks") == "connected", str(status))

    # `opencode run --command`
    n = len(llm.requests)
    out = sb.opencode(["run", "-m", "fake/echo", "--command", "runbooks:incident-report", "INC-77"], HERE,
                      timeout=120, extra_env=llm_env)
    text, _ = last_user_text(llm, n)
    check("opencode run --command runbooks:incident-report INC-77: 프롬프트가 펼쳐져 전달",
          "INC-77" in text and "장애 보고서" in text, out.stdout + out.stderr + text)

    # `opencode run "/이름 ..."` 는 펼쳐지지 않는다 (관찰된 한계)
    n = len(llm.requests)
    sb.opencode(["run", "-m", "fake/echo", "/runbooks:review-checklist"], HERE, timeout=120, extra_env=llm_env)
    text, _ = last_user_text(llm, n)
    check("opencode run 본문의 '/명령' 은 펼쳐지지 않고 글자 그대로 전달 (--command 를 써야 함)",
          text.strip().strip('"') == "/runbooks:review-checklist", text[:200])

    # `opencode run -f runbook://...` 는 파일이 아니므로 거절된다
    out = sb.opencode(["run", "-m", "fake/echo", "-f", "runbook://payment/restart", "요약"], HERE,
                      timeout=120, extra_env=llm_env)
    check("opencode run -f runbook://… 는 'File not found' (CLI 로는 리소스를 첨부할 수 없음)",
          "File not found" in out.stdout + out.stderr, out.stdout + out.stderr)


# serve 는 샌드박스를 따로 쓴다 (서버 프로세스를 강제 종료해도 위 검사에 영향이 없도록)
with FakeLLM() as llm, Sandbox("m7-serve") as sb:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    trace_file = str(sb.root / "prompt-args.jsonl")
    overlay = dict(llm.provider_config(), mcp={"runbooks": {"type": "local", "command": ["python", "server.py"],
                                                                  "environment": {"M7_TRACE_FILE": trace_file}}})
    env = dict(sb.env, OPENCODE_CONFIG_CONTENT=json.dumps(overlay), PWD=str(HERE))
    proc = subprocess.Popen([sb.bin, "serve", "--port", str(port)], cwd=HERE, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(120):
            try:
                http_json("GET", base + "/mcp", timeout=2)
                break
            except Exception:
                time.sleep(0.5)
        for _ in range(60):  # MCP 연결이 끝나길 기다린다
            if http_json("GET", base + "/mcp").get("runbooks", {}).get("status") == "connected":
                break
            time.sleep(0.5)

        cmds = {c["name"]: c for c in mcp_commands(base)}
        check("GET /command: MCP 프롬프트가 source=mcp 명령으로 등록 (이름은 <서버>:<프롬프트>)",
              set(cmds) == {"runbooks:incident-report", "runbooks:review-checklist"}, str(list(cmds)))
        check("GET /command: 프롬프트 인자는 hints 로 보임 ($1)",
              cmds.get("runbooks:incident-report", {}).get("hints") == ["$1"], str(cmds.get("runbooks:incident-report")))
        resources = mcp_resources(base)
        check("GET /experimental/resource: 리소스 3개, 키는 <서버>:<URI>",
              sorted(resources) == sorted(f"runbooks:{u}" for u in
                                          ("runbook://payment/restart", "runbook://database/failover", "runbook://cache/flush")),
              str(list(resources)))

        # 세션 API 로 @리소스 첨부 (TUI 에서 @ 자동완성으로 고르면 같은 요청이 전송된다)
        sid = http_json("POST", base + "/session", {"title": "m7"})["id"]
        n = len(llm.requests)
        http_json("POST", f"{base}/session/{sid}/message", {
            "model": {"providerID": "fake", "modelID": "echo"},
            "parts": [
                {"type": "text", "text": "@payment-restart 요약해줘"},
                {"type": "file", "mime": "text/markdown", "filename": "payment-restart",
                 "url": "runbook://payment/restart",
                 "source": {"type": "resource", "clientName": "runbooks", "uri": "runbook://payment/restart",
                            "text": {"value": "@payment-restart", "start": 0, "end": 16}}}]})
        text, main = last_user_text(llm, n)
        check("@리소스 첨부: resources/read 결과(런북 본문)가 모델 입력에 들어감",
              "pending_retry" in text and "runbook://payment/restart" in text, text[:300])
        names = FakeLLM.tool_names(main[-1]) if main else []
        check("모델 도구 목록: list_mcp_resources / read_mcp_resource / list_mcp_resource_templates + runbooks_list_runbooks",
              {"list_mcp_resources", "read_mcp_resource", "list_mcp_resource_templates", "runbooks_list_runbooks"} <= set(names),
              str(names))

        # 슬래시 명령 API: POST /session/:id/command
        n = len(llm.requests)
        http_json("POST", f"{base}/session/{sid}/command",
                  {"command": "runbooks:incident-report", "arguments": "INC-4242", "model": "fake/echo"})
        text, _ = last_user_text(llm, n)
        check("POST /session/:id/command: MCP 프롬프트의 $1 이 INC-4242 로 치환되어 모델에 전달",
              "INC-4242" in text and "장애 보고서" in text, text[:300])
        # 인자 전달 방식: 서버는 실제 값이 아니라 문자열 "$1" 을 받는다 (opencode 가 템플릿을 받아 직접 치환)
        trace = [json.loads(l) for l in pathlib.Path(trace_file).read_text(encoding="utf-8").splitlines()] if pathlib.Path(trace_file).exists() else []
        sent = [t["arguments"] for t in trace if t["prompts/get"] == "incident-report"]
        check("prompts/get 으로 서버에 가는 인자는 실제 티켓 번호가 아니라 리터럴 \"$1\" (치환은 opencode 가 함)",
              sent and all(a == {"ticket_id": "$1"} for a in sent), str(trace))
        n = len(llm.requests)
        http_json("POST", f"{base}/session/{sid}/command",
                  {"command": "runbooks:incident-report", "arguments": "INC-1 extra words", "model": "fake/echo"})
        text, _ = last_user_text(llm, n)
        check("인자가 하나뿐인 프롬프트에 단어 여러 개를 주면 마지막 자리표시자($1)가 나머지를 전부 받음", "티켓 INC-1 extra words 에" in text, text[:200])
    finally:
        stop(proc)

# --- 실제 모델 (마지막에 둔다: 모델 대기열이 막혀도 위의 hard 검사는 이미 끝나 있다) ---------------------
if model_enabled():
    with Sandbox("m7-model") as sb:
        try:
            out = sb.run_model("runbooks MCP 서버의 리소스 중 결제 서비스 재시작 런북을 읽어서 첫 번째 단계만 한 줄로 알려줘.", HERE,
                               extra_env={"PWD": str(HERE)})
        except Exception as exc:  # 모델 대기열 시간 초과 등은 '검증 불가'로 보고
            out = MODEL_UNAVAILABLE + f" {exc}"
        model_check("실제 모델이 read_mcp_resource 로 런북을 읽음", out,
                    tool_called(out, "read_mcp_resource") and "payment-api" in out)

finish()
