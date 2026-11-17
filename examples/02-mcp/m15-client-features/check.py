"""M15 check: 서버가 보내는 새 기능(progress, structuredContent, list_changed 등)과, opencode 1.19.5가 그것을 어떻게 받는지 고정한다.

"opencode 쪽 관찰" 검사는 일부러 현재 동작을 그대로 못 박아 둔 것이다. opencode가 업데이트되어 동작이 바뀌면
이 검사가 실패한다. 그때는 버그가 아니라 "달라졌다는 알림"이니, probe.py로 새 동작을 확인하고 README 표를 고치자.
"""
import json
import os
import subprocess
import sys
import pathlib
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SERVER = HERE / "server.py"


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env.update(extra)
    return env


class StdioClient:
    def __init__(self, **env):
        self.proc = subprocess.Popen([sys.executable, str(SERVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, cwd=str(HERE), env=clean_env(**env))
        self.n = 0
        self.stderr_lines = []
        threading.Thread(target=lambda: [self.stderr_lines.append(x) for x in iter(self.proc.stderr.readline, b"")], daemon=True).start()

    def send(self, obj):
        self.proc.stdin.write(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
        self.proc.stdin.flush()

    def recv(self):
        return json.loads(self.proc.stdout.readline().decode("utf-8"))

    def request(self, method, params=None):
        """요청을 보내고, 응답이 올 때까지 사이에 낀 알림들을 모아서 (응답, 알림 목록)으로 돌려준다."""
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method}
        if params is not None:
            msg["params"] = params
        self.send(msg)
        notes = []
        while True:
            reply = self.recv()
            if reply.get("id") == self.n and ("result" in reply or "error" in reply):
                return reply, notes
            notes.append(reply)

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc.stdout.close()
        return self.proc.returncode


def call(c, name, arguments=None, meta=None):
    params = {"name": name, "arguments": arguments or {}}
    if meta is not None:
        params["_meta"] = meta
    return c.request("tools/call", params)


# --- 설정 파일 ---------------------------------------------------------------------------------
config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
check("opencode.json은 v1 형식(mcp.features.type/command)이고 model 키가 없다",
      config["mcp"]["features"]["type"] == "local" and isinstance(config["mcp"]["features"]["command"], list)
      and "model" not in config and config.get("$schema") == "https://opencode.ai/config.json")

# --- 서버 단독 (opencode 없이): 서버가 약속대로 보내는가 ---------------------------------------------------------
c = StdioClient(M15_STEP="0.05")
r, _ = c.request("initialize", {"protocolVersion": "2025-11-25", "capabilities": {"roots": {}}, "clientInfo": {"name": "check", "version": "0"}})
caps = r["result"]["capabilities"]
check("initialize: tools.listChanged=true 와 logging 을 선언한다", caps.get("tools", {}).get("listChanged") is True and "logging" in caps, str(caps))
c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
r, _ = c.request("tools/list")
tools = {t["name"]: t for t in r["result"]["tools"]}
check("tools/list: 도구 5개, late_tool은 아직 없다",
      list(tools) == ["slow_count", "both_text_and_structured", "structured_only", "add_tool", "client_request_probe"], str(list(tools)))
check("outputSchema는 두 구조화 도구에만 있다",
      "outputSchema" in tools["both_text_and_structured"] and "outputSchema" in tools["structured_only"]
      and not any("outputSchema" in tools[n] for n in ("slow_count", "add_tool", "client_request_probe")))

r, notes = call(c, "slow_count", {"steps": 3}, meta={"progressToken": "tok-1"})
progress = [n for n in notes if n.get("method") == "notifications/progress"]
check("slow_count: progressToken을 받으면 단계마다 notifications/progress 3개를 응답보다 먼저 보낸다 (토큰·total·message 포함)",
      len(progress) == 3 and all(p["params"]["progressToken"] == "tok-1" and p["params"]["total"] == 3 for p in progress)
      and [p["params"]["progress"] for p in progress] == [1, 2, 3] and progress[0]["params"]["message"], str(notes))
check("progress 알림에는 id가 없다 (알림이므로 답장을 기대하지 않는다)", all("id" not in p for p in progress))
check("notifications/message(로그 알림)도 단계마다 나간다", sum(1 for n in notes if n.get("method") == "notifications/message") == 3)
r, notes = call(c, "slow_count", {"steps": 2})
check("progressToken이 없으면 progress를 보내지 않는다 (스펙: 토큰이 있을 때만)",
      not [n for n in notes if n.get("method") == "notifications/progress"] and r["result"]["content"][0]["text"].endswith("없음"), str(notes))
r, notes = call(c, "slow_count", {"steps": 2, "report": False}, meta={"progressToken": 9})
check("report=false면 토큰이 있어도 progress를 보내지 않는다 (시간 제한 시험용)", not [n for n in notes if n.get("method") == "notifications/progress"])

r, _ = call(c, "both_text_and_structured")
res = r["result"]
check("both_text_and_structured: text 블록과 structuredContent가 같이 온다",
      res["content"][0]["type"] == "text" and res["structuredContent"] == {"count": 2, "items": ["alpha", "beta"]})
r, _ = call(c, "structured_only")
res = r["result"]
check("structured_only: content는 빈 배열, structuredContent만 있다", res["content"] == [] and res["structuredContent"]["count"] == 3)

r, _ = call(c, "late_tool")
check("add_tool 전에 late_tool을 부르면 -32602", r.get("error", {}).get("code") == -32602, str(r))
c.n += 1
c.send({"jsonrpc": "2.0", "id": c.n, "method": "tools/call", "params": {"name": "add_tool", "arguments": {}}})
first = c.recv()
second = c.recv()
check("add_tool: 응답 다음에 notifications/tools/list_changed가 나간다",
      first.get("id") == c.n and second.get("method") == "notifications/tools/list_changed" and "id" not in second, f"{first} {second}")
r, _ = c.request("tools/list")
check("그 뒤 tools/list에는 late_tool이 있다", "late_tool" in [t["name"] for t in r["result"]["tools"]])
r, _ = call(c, "late_tool")
check("late_tool 호출 성공", r["result"]["content"][0]["text"] == "late_tool 이 호출됐다.")

# 서버가 클라이언트에게 요청을 보내는 경로: 우리가 클라이언트 역할로 답해 준다
c.n += 1
c.send({"jsonrpc": "2.0", "id": c.n, "method": "tools/call", "params": {"name": "client_request_probe", "arguments": {"method": "roots/list"}}})
server_req = c.recv()
check("client_request_probe: 서버가 roots/list 요청(id 있음)을 클라이언트에게 보낸다", server_req.get("method") == "roots/list" and "id" in server_req, str(server_req))
c.send({"jsonrpc": "2.0", "id": server_req["id"], "result": {"roots": [{"uri": "file:///demo"}]}})
final = c.recv()
check("클라이언트의 답을 받아 도구 결과에 담는다", "file:///demo" in final["result"]["content"][0]["text"], str(final))
check("서버는 stdin을 닫으면 정상 종료(0)한다", c.close() == 0)

# --- opencode 연결 + 실제 관찰 (probe.observe) ---------------------------------------------------------
with Sandbox("m15") as sb:
    status = sb.mcp_list(HERE)
    check("opencode mcp list: features connected", status.get("features") == "connected", str(status))

import probe  # noqa: E402

try:
    f = probe.observe()
except Exception as exc:  # noqa: BLE001
    check("probe.observe()가 opencode 세션 4개를 끝까지 돌린다", False, repr(exc))
    finish()

# 아래 검사는 opencode 1.19.5의 "현재 동작"을 고정한 것이다. 실패하면 opencode가 달라진 것이다.
check("[opencode] initialize: protocolVersion 2025-11-25, clientInfo opencode 1.19.5",
      f["protocol_version"] == "2025-11-25" and f["client_info"] == {"name": "opencode", "version": "1.19.5"}, str(f["client_info"]))
check("[opencode] 클라이언트 capabilities는 roots뿐이다 (sampling, elicitation 없음)", f["client_capabilities"] == {"roots": {}}, str(f["client_capabilities"]))
check("[opencode] 모든 tools/call에 정수 progressToken이 붙고, 그 값은 요청 id와 같다 (cancelled의 requestId와 일치)",
      f["call_count"] == 8 and all(isinstance(t, int) for t in f["token_list"]) and f["token_list"] == f["cancelled_ids"], str((f["token_list"], f["cancelled_ids"])))
check("[opencode] 호출이 끝날 때마다 notifications/cancelled가 온다", f["cancelled_count"] == f["call_count"])
check("[opencode] 진행 알림(notifications/progress)은 화면·--print-logs DEBUG에 나오지 않는다 (출력에 'progress'가 없다)",
      not f["progress_word_in_debug_logs"] and not f["progress_message_in_debug_logs"])
check("[opencode] 진행 알림은 --format json 이벤트에도 나오지 않는다 (도구 이벤트 metadata는 truncated뿐)",
      not f["progress_word_in_json_events"] and f["json_event_metadata"] == {"truncated": False}, str(f["json_event_metadata"]))
check("[opencode] 진행 알림은 도구 호출 제한 시간(timeout 3000ms)을 연장한다: 5초 도구가 알림이 있으면 끝나고, 없으면 timed out",
      f["timeout3s_with_progress"] == "5단계를 모두 마쳤다. 토큰: 있음" and "Request timed out" in (f["timeout3s_without_progress"] or ""),
      f"{f['timeout3s_with_progress']!r} / {f['timeout3s_without_progress']!r}")
check("[opencode] notifications/message는 --print-logs DEBUG 로그에 'MCP server log' 줄로 나오고, 옵션 없이는 나오지 않는다",
      len(f["message_log_lines"]) == 3 and "logger=m15" in f["message_log_lines"][0] and not f["message_log_in_default_output"])
check("[opencode] 서버의 stderr는 --print-logs DEBUG에도 나오지 않는다", not f["server_stderr_in_logs"])
check("[opencode] text+structuredContent: 모델은 text 블록만 받는다", f["result_both"] == "항목 2개: alpha, beta (이 문장은 text 블록)", str(f["result_both"]))
check("[opencode] structuredContent만: 모델은 그 JSON을 compact 문자열로 받는다", f["result_structured_only"] == '{"count":3,"items":["x","y","z"]}', str(f["result_structured_only"]))
check("[opencode] 모델에게 가는 도구 정의는 name, description, parameters뿐이고 outputSchema가 없다",
      f["tool_def_function_keys"] == ["description", "name", "parameters"] and not f["output_schema_in_tool_def"], str(f["tool_def_function_keys"]))
check("[opencode] list_changed 뒤에 tools/list를 다시 부른다 (총 2번)", f["refetch_after_list_changed"] and f["tools_list_calls"] == 2, str(f["tools_list_calls"]))
check("[opencode] 새 도구는 add_tool 결과가 가는 바로 그 모델 요청부터 목록에 있다 (5번째 요청)",
      f["late_tool_first_listed_in_request"] == f["add_tool_result_first_sent_in_request"] == 5, str((f["late_tool_first_listed_in_request"], f["add_tool_result_first_sent_in_request"])))
check("[opencode] 그 요청에서 모델이 late_tool을 바로 불러 성공한다", f["late_tool_call_result"])
replies = f["client_request_replies"]
check("[opencode] roots/list 요청에는 프로젝트 폴더의 file:// URI로 답한다",
      replies.get("roots/list", {}).get("result", {}).get("roots", [{}])[0].get("uri", "").startswith("file://")
      and replies["roots/list"]["result"]["roots"][0]["uri"].endswith("m15-client-features"), str(replies.get("roots/list")))
check("[opencode] sampling/createMessage와 elicitation/create 요청은 -32601 Method not found로 거절한다",
      all(replies.get(m, {}).get("error", {}).get("code") == -32601 for m in ("sampling/createMessage", "elicitation/create")), str(replies))

if model_enabled():
    with Sandbox("m15m") as sb:
        out = sb.run_model("features_slow_count 도구를 steps 2로 호출하고 결과를 한 줄로 알려줘.", HERE,
                           extra_env={"PWD": str(HERE)})
        model_check("모델이 features_slow_count 도구를 호출했다", out, "features_slow_count" in out)
finish()
