#!/usr/bin/env python3
"""M15 - MCP의 "새 기능"을 일부러 다 써 보는 서버 (표준 라이브러리만).

이 서버는 쓸모 있는 일을 하지 않는다. opencode(클라이언트)가 아래 기능을 받아 주는지 관찰하려고 만들었다.
무슨 일이 있었는지는 두 곳에 남는다.

    stderr          사람이 보는 로그
    M15_LOG 파일    환경 변수 M15_LOG 가 가리키는 파일에 JSON 한 줄씩 (probe.py / check.py 가 읽는다)

도구:
    slow_count            오래 걸리는 도구. 받은 _meta.progressToken 으로 notifications/progress 를 보낸다
    both_text_and_structured   content(text)와 structuredContent 를 같이 돌려준다 (출력 스키마 선언)
    structured_only       content 는 비우고 structuredContent 만 돌려준다 (출력 스키마 선언)
    add_tool              새 도구 late_tool 을 추가하고 notifications/tools/list_changed 를 보낸다
    late_tool             add_tool 을 부르기 전에는 목록에 없다
    client_request_probe  서버가 거꾸로 클라이언트에게 요청(roots/list, sampling, elicitation)을 보내 본다

실행 확인 (에이전트 없이): python probe.py
"""
import collections
import json
import os
import queue
import sys
import threading
import time

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
sys.stderr.reconfigure(encoding="utf-8")

SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
METHOD_NOT_FOUND, INVALID_PARAMS = -32601, -32602
STEP_SECONDS = 1.0  # slow_count 가 한 단계에 쓰는 시간 (환경 변수 M15_STEP 으로 바꿀 수 있다)

LOG_PATH = os.environ.get("M15_LOG")


def log(*parts):
    print("[m15]", *parts, file=sys.stderr, flush=True)


def record(event, **fields):
    """관찰한 사실을 파일에 JSON 한 줄로 남긴다 (M15_LOG 가 있을 때만)."""
    log(event, json.dumps(fields, ensure_ascii=False))
    if LOG_PATH:
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"event": event, **fields}, ensure_ascii=False) + "\n")


# --- 입출력: 읽기는 스레드로 ---------------------------------------------------------------------
# 서버가 클라이언트에게 요청을 보내고 답을 기다리는 동안에도 stdin 을 읽어야 해서 읽기 전용 스레드를 둔다.
inbox = queue.Queue()
deferred = collections.deque()  # 답을 기다리는 동안 먼저 도착한 다른 메시지
next_server_id = [0]


def reader():
    for line in sys.stdin:
        inbox.put(line)
    inbox.put(None)  # stdin 이 닫혔다


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def notify(method, params=None):
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    send(msg)


def ask_client(method, params, timeout):
    """클라이언트에게 요청을 보내고 timeout 초 안에 오는 답(dict)을 돌려준다. 없으면 None."""
    next_server_id[0] += 1
    req_id = f"srv-{next_server_id[0]}"
    send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
    deadline = time.time() + timeout
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return None
        try:
            line = inbox.get(timeout=remaining)
        except queue.Empty:
            return None
        if line is None:
            inbox.put(None)
            return None
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == req_id and ("result" in msg or "error" in msg):
            return msg
        deferred.append(msg)  # 우리 요청의 답이 아니면 나중에 처리한다


# --- 도구 정의 -------------------------------------------------------------------------------------
LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "count": {"type": "integer"},
        "items": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["count", "items"],
}

BASE_TOOLS = [
    {
        "name": "slow_count",
        "description": "단계마다 1초씩 걸리는 느린 작업을 흉내 낸다. 진행 상황을 notifications/progress 로 보낸다.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "steps": {"type": "integer", "description": "단계 수 (기본 3)"},
                "report": {"type": "boolean", "description": "false 면 진행 알림(notifications/progress)을 보내지 않는다 (기본 true)"},
            },
        },
    },
    {
        "name": "both_text_and_structured",
        "description": "결과를 text 와 structuredContent 둘 다로 돌려준다 (출력 스키마 선언).",
        "inputSchema": {"type": "object", "properties": {}},
        "outputSchema": LIST_SCHEMA,
    },
    {
        "name": "structured_only",
        "description": "결과를 structuredContent 로만 돌려준다. content 는 비어 있다 (출력 스키마 선언).",
        "inputSchema": {"type": "object", "properties": {}},
        "outputSchema": LIST_SCHEMA,
    },
    {
        "name": "add_tool",
        "description": "late_tool 이라는 새 도구를 추가하고 notifications/tools/list_changed 를 보낸다.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "client_request_probe",
        "description": "서버가 클라이언트에게 요청(roots/list, sampling/createMessage, elicitation/create)을 보내고 답을 3초 기다린다.",
        "inputSchema": {
            "type": "object",
            "properties": {"method": {"type": "string", "enum": ["roots/list", "sampling/createMessage", "elicitation/create"]}},
            "required": ["method"],
        },
    },
]
LATE_TOOL = {
    "name": "late_tool",
    "description": "add_tool 을 부른 뒤에야 생기는 도구.",
    "inputSchema": {"type": "object", "properties": {}},
}
state = {"late": False, "client_caps": None}


def current_tools():
    return BASE_TOOLS + ([LATE_TOOL] if state["late"] else [])


def text_result(text, is_error=False):
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def slow_count(args, meta):
    steps = args.get("steps") if isinstance(args.get("steps"), int) else 3
    step_seconds = float(os.environ.get("M15_STEP", STEP_SECONDS))
    token = meta.get("progressToken")
    report = args.get("report", True) is not False
    # 클라이언트가 progressToken 을 보냈을 때만 progress 를 보낼 수 있다. (없으면 보내면 안 된다)
    record("call", tool="slow_count", progressToken=token, meta=meta)
    for i in range(1, steps + 1):
        time.sleep(step_seconds)
        if token is not None and report:
            notify("notifications/progress", {"progressToken": token, "progress": i, "total": steps, "message": f"{i}/{steps} 단계 완료"})
        notify("notifications/message", {"level": "info", "logger": "m15", "data": f"slow_count {i}/{steps}"})
    return text_result(f"{steps}단계를 모두 마쳤다. 토큰: {'있음' if token is not None else '없음'}")


def both_text_and_structured(_args, _meta):
    data = {"count": 2, "items": ["alpha", "beta"]}
    return {"content": [{"type": "text", "text": "항목 2개: alpha, beta (이 문장은 text 블록)"}], "structuredContent": data, "isError": False}


def structured_only(_args, _meta):
    return {"content": [], "structuredContent": {"count": 3, "items": ["x", "y", "z"]}, "isError": False}


def add_tool(_args, _meta):
    state["late"] = True
    record("late_tool_added")
    return text_result("late_tool 을 추가했다. 곧 notifications/tools/list_changed 가 나간다.")


def client_request_probe(args, _meta):
    method = args.get("method")
    params = {
        "roots/list": {},
        "sampling/createMessage": {"messages": [{"role": "user", "content": {"type": "text", "text": "안녕"}}], "maxTokens": 10},
        "elicitation/create": {"message": "값을 입력해 주세요", "requestedSchema": {"type": "object", "properties": {"v": {"type": "string"}}}},
    }.get(method)
    if params is None:
        raise RpcError(INVALID_PARAMS, f"알 수 없는 method: {method}")
    t0 = time.time()
    reply = ask_client(method, params, timeout=3)
    waited = round(time.time() - t0, 1)
    record("client_request", method=method, reply=reply, waited=waited)
    if reply is None:
        return text_result(f"{method}: {waited}초 안에 답이 없었다")
    return text_result(f"{method}: 답 {json.dumps(reply.get('result', reply.get('error')), ensure_ascii=False)}")


def late_tool(_args, _meta):
    return text_result("late_tool 이 호출됐다.")


HANDLERS = {
    "slow_count": slow_count,
    "both_text_and_structured": both_text_and_structured,
    "structured_only": structured_only,
    "add_tool": add_tool,
    "client_request_probe": client_request_probe,
    "late_tool": late_tool,
}


def call_tool(params):
    name = params.get("name")
    names = [t["name"] for t in current_tools()]
    if name not in names:
        raise RpcError(INVALID_PARAMS, f"알 수 없는 도구: {name}")
    meta = params.get("_meta") or {}
    if name != "slow_count":
        record("call", tool=name, progressToken=meta.get("progressToken"))
    return HANDLERS[name](params.get("arguments") or {}, meta)


def handle(msg):
    method, params, msg_id = msg.get("method"), msg.get("params") or {}, msg.get("id")
    if msg_id is None:
        if method == "notifications/cancelled":
            record("cancelled", params=params)
        elif method:
            record("client_notification", method=method)
        return None
    if method is None:  # 클라이언트가 우리 요청에 늦게 답한 경우 등. 무시한다
        return None
    try:
        if method == "initialize":
            wanted = params.get("protocolVersion")
            version = wanted if wanted in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            state["client_caps"] = params.get("capabilities")
            record("initialize", protocolVersion=wanted, clientCapabilities=params.get("capabilities"), clientInfo=params.get("clientInfo"))
            # tools.listChanged: "도구 목록이 바뀔 수 있고, 바뀌면 알림을 보낸다"는 선언
            result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": True}, "logging": {}},
                      "serverInfo": {"name": "m15-client-features", "version": "1.0.0"}}
        elif method == "tools/list":
            record("tools/list", tools=[t["name"] for t in current_tools()])
            result = {"tools": current_tools()}
        elif method == "tools/call":
            result = call_tool(params)
        elif method == "ping":
            result = {}
        else:
            raise RpcError(METHOD_NOT_FOUND, f"모르는 method: {method}")
    except RpcError as err:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": err.code, "message": err.message}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def main():
    log("시작")
    threading.Thread(target=reader, daemon=True).start()
    while True:
        if deferred:
            msg = deferred.popleft()
        else:
            line = inbox.get()
            if line is None:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON 파싱 실패"}})
                continue
            if not isinstance(msg, dict):
                continue
        was_add_tool = msg.get("method") == "tools/call" and (msg.get("params") or {}).get("name") == "add_tool"
        response = handle(msg)
        if response is not None:
            send(response)
        if was_add_tool and response and "result" in response:
            notify("notifications/tools/list_changed")  # 응답 뒤에 "목록이 바뀌었다"고 알린다
            record("list_changed_sent")
    log("stdin 종료")


if __name__ == "__main__":
    main()
