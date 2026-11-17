#!/usr/bin/env python3
"""probe.py - opencode가 MCP의 새 기능을 어디까지 받아 주는지 실제로 돌려 보고 표로 출력한다.

M1의 raw_session.py가 "서버 쪽에서 본 JSON 대화"라면, 이 스크립트는 "진짜 opencode를 붙여 놓고 관찰"한다.
모델은 가짜 모델(fake_llm.py)이라 결과가 항상 같고 인터넷이 필요 없다. 가짜 모델이 정해진 순서로 도구를 부르고,
그동안 서버(M15_LOG 파일)와 가짜 모델(받은 요청 본문)과 opencode(화면·로그·JSON 이벤트)에서 일어난 일을 모은다.

    python probe.py

opencode는 tools/octest.py의 Sandbox 안에서만 실행한다. 실제 ~/.config/opencode나 세션 DB를 건드리지 않는다.
세션이 네 번 돌아서 1분 안팎 걸린다.
"""
import json
import os
import pathlib
import re
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# 서버 이름이 "features"라서 모델에게 보이는 도구 이름은 features_<도구>
FULL_SCRIPT = [
    ("tool", "features_slow_count", {"steps": 3}),
    ("tool", "features_both_text_and_structured", {}),
    ("tool", "features_structured_only", {}),
    ("tool", "features_add_tool", {}),
    ("tool", "features_late_tool", {}),  # add_tool 바로 다음 요청에서 이미 부를 수 있는가
    ("tool", "features_client_request_probe", {"method": "roots/list"}),
    ("tool", "features_client_request_probe", {"method": "sampling/createMessage"}),
    ("tool", "features_client_request_probe", {"method": "elicitation/create"}),
    "DONE",
]


def run_session(name, script, extra_args=(), mcp_timeout=None):
    """가짜 모델로 opencode를 한 번 돌리고 관찰 결과를 dict로 돌려준다."""
    fd, name_ = tempfile.mkstemp(prefix="m15-events-", suffix=".jsonl")
    os.close(fd)
    log_path = pathlib.Path(name_)
    try:
        with Sandbox(name) as sb, FakeLLM(script=script) as llm:
            cfg = llm.provider_config()
            if mcp_timeout:  # 도구 호출 제한 시간을 줄여서 시험할 때
                cfg["mcp"] = {"features": {"type": "local", "command": ["python", "server.py"], "enabled": True, "timeout": mcp_timeout}}
            proc = sb.opencode(["run", "-m", "fake/echo", "--auto", *extra_args, "go"], HERE, timeout=180,
                               extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps(cfg), "M15_LOG": str(log_path)})
            requests = llm.main_requests()
            tool_results = []  # 모델이 받은 도구 결과 문자열 (요청마다 쌓이므로 중복 제거)
            for request in requests:
                for message in request["messages"]:
                    text = llm.message_text(message)
                    if message.get("role") == "tool" and text not in tool_results:
                        tool_results.append(text)
            tool_lists = [llm.tool_names(r) for r in requests]
            tool_defs = requests[0]["tools"] if requests else []
        events = [json.loads(x) for x in log_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    finally:
        log_path.unlink(missing_ok=True)
    return {"out": proc.stdout + "\n" + proc.stderr, "stdout": proc.stdout, "stderr": proc.stderr, "events": events,
            "requests": requests, "tool_results": tool_results, "tool_lists": tool_lists, "tool_defs": tool_defs}


def first_request_with(requests, needle):
    """messages 안에 needle이 든 도구 결과가 처음 나오는 모델 요청의 번호(1부터). 없으면 None."""
    for i, request in enumerate(requests, 1):
        for m in request["messages"]:
            content = m.get("content")
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            if m.get("role") == "tool" and needle in (text or ""):
                return i
    return None


def observe():
    """네 번의 opencode 세션을 돌려 관찰 결과를 모은다. check.py도 이 함수를 쓴다."""
    facts = {}

    # 세션 A: 전체 시나리오 + --print-logs DEBUG (opencode가 로그로 무엇을 남기는지)
    a = run_session("m15a", FULL_SCRIPT, ("--print-logs", "--log-level", "DEBUG"))
    ev = a["events"]
    init = next(e for e in ev if e["event"] == "initialize")
    facts["client_capabilities"] = init["clientCapabilities"]
    facts["client_info"] = init["clientInfo"]
    facts["protocol_version"] = init["protocolVersion"]
    calls = [e for e in ev if e["event"] == "call"]
    facts["progress_tokens"] = {c["tool"]: c["progressToken"] for c in calls}
    facts["token_list"] = [c["progressToken"] for c in calls]
    facts["cancelled_ids"] = [e["params"].get("requestId") for e in ev if e["event"] == "cancelled"]
    facts["cancelled_count"] = sum(1 for e in ev if e["event"] == "cancelled")
    facts["call_count"] = len(calls)
    facts["progress_word_in_debug_logs"] = bool(re.search("progress", a["out"], re.I))
    facts["progress_message_in_debug_logs"] = "1/3 단계 완료" in a["out"]
    facts["message_log_lines"] = [l for l in a["out"].splitlines() if "MCP server log" in l]
    facts["server_stderr_in_logs"] = "[m15]" in a["out"]
    facts["screen_lines"] = [l.strip() for l in a["out"].splitlines() if l.lstrip().startswith("⚙")]
    results = a["tool_results"]
    facts["tool_results"] = results
    facts["result_both"] = next((r for r in results if r.startswith("항목 2개")), None)
    facts["result_structured_only"] = next((r for r in results if r.startswith("{")), None)
    defs = a["tool_defs"]
    facts["tool_def_function_keys"] = sorted({k for d in defs for k in d["function"]})
    structured_defs = [d for d in defs if d["function"]["name"] in ("features_both_text_and_structured", "features_structured_only")]
    dumped = json.dumps(structured_defs, ensure_ascii=False)
    facts["output_schema_in_tool_def"] = "outputSchema" in dumped or '"count"' in dumped or "output_schema" in dumped
    facts["structured_tool_def"] = next((d["function"] for d in structured_defs if d["function"]["name"] == "features_structured_only"), None)
    # tools/list 가 다시 불렸고, 늦은 도구가 어느 모델 요청부터 보였는가
    order = [e["event"] for e in ev]
    facts["tools_list_calls"] = sum(1 for e in ev if e["event"] == "tools/list")
    facts["refetch_after_list_changed"] = (
        "list_changed_sent" in order and "tools/list" in order[order.index("list_changed_sent"):])
    facts["late_tool_first_listed_in_request"] = next(
        (i for i, names in enumerate(a["tool_lists"], 1) if "features_late_tool" in names), None)
    facts["add_tool_result_first_sent_in_request"] = first_request_with(a["requests"], "late_tool 을 추가했다")
    facts["model_request_count"] = len(a["requests"])
    facts["late_tool_call_result"] = "late_tool 이 호출됐다." in results
    replies = {e["method"]: e["reply"] for e in ev if e["event"] == "client_request"}
    facts["client_request_replies"] = replies

    # 세션 B: --format json (화면 대신 기계가 읽는 이벤트)에 진행 알림이 나오는가
    b = run_session("m15b", [("tool", "features_slow_count", {"steps": 3}), "DONE"], ("--format", "json"))
    facts["progress_word_in_json_events"] = bool(re.search("progress", b["stdout"], re.I))
    facts["message_log_in_default_output"] = "MCP server log" in b["out"]  # --print-logs 없이 돌린 세션
    facts["json_event_metadata"] = None
    for line in b["stdout"].splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "tool_use":
            facts["json_event_metadata"] = obj["part"]["state"].get("metadata")

    # 세션 C: 도구 호출 제한을 3초로 줄이고 5초짜리 도구를 부른다. 진행 알림이 있을 때/없을 때
    c1 = run_session("m15c1", [("tool", "features_slow_count", {"steps": 5, "report": True}), "DONE"], mcp_timeout=3000)
    c2 = run_session("m15c2", [("tool", "features_slow_count", {"steps": 5, "report": False}), "DONE"], mcp_timeout=3000)
    facts["timeout3s_with_progress"] = c1["tool_results"][0] if c1["tool_results"] else None
    facts["timeout3s_without_progress"] = c2["tool_results"][0] if c2["tool_results"] else None
    return facts


def print_report(f):
    yn = lambda v: "예" if v else "아니오"  # noqa: E731
    print("== 관찰 결과 (opencode 1.19.5, 가짜 모델)\n")
    print(f"client initialize : protocolVersion={f['protocol_version']} clientInfo={f['client_info']}")
    print(f"                    capabilities={json.dumps(f['client_capabilities'])}")
    print(f"progressToken     : {f['progress_tokens']}  (도구마다 정수가 들어 있고 모든 tools/call에 붙는다)")
    print(f"notifications/cancelled : tools/call {f['call_count']}번 중 {f['cancelled_count']}번")
    print(f"opencode 화면(⚙ 줄) : {f['screen_lines']}")
    print(f"'progress'라는 글자가 opencode 출력에 있는가 - 기본 화면+--print-logs DEBUG: {yn(f['progress_word_in_debug_logs'])}, "
          f"--format json 이벤트: {yn(f['progress_word_in_json_events'])}")
    print(f"--format json 도구 이벤트의 metadata : {f['json_event_metadata']}")
    print(f"notifications/message(로그)가 --print-logs DEBUG에 나오는가: {yn(f['message_log_lines'])} / --print-logs 없이 돌린 세션에 나오는가: {yn(f['message_log_in_default_output'])}")
    for line in f["message_log_lines"][:1]:
        print("    예) " + re.sub(r"^timestamp=\S+ ", "", line))
    print(f"서버의 stderr가 --print-logs DEBUG에 나오는가: {yn(f['server_stderr_in_logs'])}")
    print(f"모델이 받은 결과 (text+structured) : {f['result_both']!r}")
    print(f"모델이 받은 결과 (structured만)    : {f['result_structured_only']!r}")
    print(f"모델에게 간 도구 정의의 키          : {f['tool_def_function_keys']}")
    print(f"  structured_only 정의 전체        : {json.dumps(f['structured_tool_def'], ensure_ascii=False)}")
    print(f"outputSchema가 모델에게 갔는가      : {yn(f['output_schema_in_tool_def'])}")
    print(f"tools/list 호출 횟수 {f['tools_list_calls']}번, list_changed 뒤에 다시 불렀는가: {yn(f['refetch_after_list_changed'])}")
    print(f"late_tool이 처음 보인 모델 요청 : {f['late_tool_first_listed_in_request']}번째 "
          f"(add_tool 결과가 처음 간 요청 : {f['add_tool_result_first_sent_in_request']}번째, 전체 {f['model_request_count']}번)")
    print(f"그 요청에서 바로 late_tool을 불렀는가: {yn(f['late_tool_call_result'])}")
    for method, reply in f["client_request_replies"].items():
        print(f"서버 -> 클라이언트 요청 {method}: {json.dumps(reply.get('result', reply.get('error')), ensure_ascii=False)}")
    print(f"timeout=3000ms, 5초짜리 도구: 진행 알림 있음 -> {f['timeout3s_with_progress']!r}")
    print(f"timeout=3000ms, 5초짜리 도구: 진행 알림 없음 -> {f['timeout3s_without_progress']!r}")

    print("\n== 요약표\n")
    rows = [
        ("initialize의 클라이언트 capabilities", "(서버가 받음)", f"{json.dumps(f['client_capabilities'])} - sampling, elicitation 선언 없음"),
        ("_meta.progressToken", "(클라이언트가 보냄)", "모든 tools/call에 정수 토큰을 붙인다 (그 요청의 id와 같은 값)"),
        ("notifications/progress", "토큰을 써서 단계마다 전송",
         "오류 없이 받는다. 화면/로그/JSON 이벤트 어디에도 나오지 않는다. 호출 제한 시간은 늘려 준다"),
        ("notifications/message", "level=info 로그 전송", "--print-logs --log-level DEBUG 로그에 INFO 줄(MCP server log)로 나온다. --print-logs 없이는 안 나온다"),
        ("structuredContent + text", "둘 다 + outputSchema", "모델은 text 블록만 받는다"),
        ("structuredContent 만", "content=[] + outputSchema", "모델은 structuredContent의 JSON 문자열을 받는다"),
        ("outputSchema", "tools/list 에 포함", "모델에게 가는 도구 정의에 들어가지 않는다 (name, description, parameters 뿐)"),
        ("notifications/tools/list_changed", "도구 추가 후 전송", "tools/list 를 다시 부르고 다음 모델 요청부터 새 도구가 보인다"),
        ("roots/list (서버->클라이언트)", "요청", "프로젝트 폴더의 file:// URI 를 답한다"),
        ("sampling/createMessage, elicitation/create", "요청", "-32601 Method not found 로 즉시 거절한다"),
        ("notifications/cancelled", "(클라이언트가 보냄)", "호출이 끝날 때마다 AbortError 사유로 온다"),
    ]
    width = max(len(r[0]) for r in rows)
    for feature, sent, did in rows:
        print(f"- {feature:<{width}} | 서버: {sent} | opencode: {did}")


if __name__ == "__main__":
    print_report(observe())
