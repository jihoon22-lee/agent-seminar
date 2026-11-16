"""m7 — resources 와 prompts 까지 노출하는 최소 MCP 서버 (표준 라이브러리만 사용).

stdio 위의 줄 단위 JSON-RPC. 지원 메서드:
  initialize, ping,
  tools/list, tools/call            (도구 1개: list_runbooks)
  resources/list, resources/read    (runbooks/*.md → runbook://<서비스>/<절차>)
  resources/templates/list          (runbook://{service}/{procedure} 템플릿)
  prompts/list, prompts/get         (incident-report, review-checklist)

규칙: stdout 에는 MCP 메시지만 쓴다. 로그는 stderr 로 쓴다.
"""
import json
import os
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
RUNBOOKS = {  # URI → 파일
    "runbook://payment/restart": HERE / "runbooks" / "payment-restart.md",
    "runbook://database/failover": HERE / "runbooks" / "db-failover.md",
    "runbook://cache/flush": HERE / "runbooks" / "cache-flush.md",
}

TOOLS = [{
    "name": "list_runbooks",
    "description": "등록된 런북의 URI 목록을 돌려준다. 런북 본문은 resources/read 로 읽는다.",
    "inputSchema": {"type": "object", "properties": {}},
}]

RESOURCES = [
    {"uri": uri, "name": uri.removeprefix("runbook://").replace("/", "-"),
     "title": "런북: " + uri.removeprefix("runbook://"),
     "description": "운영 런북 (" + uri.removeprefix("runbook://") + ")",
     "mimeType": "text/markdown"}
    for uri in RUNBOOKS
]

PROMPTS = [
    {"name": "incident-report",
     "description": "티켓 번호로 장애 보고서 초안을 쓰게 하는 프롬프트",
     "arguments": [{"name": "ticket_id", "description": "예: INC-1234", "required": True}]},
    {"name": "review-checklist",
     "description": "코드 리뷰 체크리스트로 변경분을 검토하게 하는 프롬프트",
     "arguments": []},
]


def log(*a):
    print("[m7]", *a, file=sys.stderr, flush=True)


def get_prompt(name, args):
    # 디버깅 요령: stderr 는 opencode 가 보여 주지 않으므로, 서버가 실제로 받은 값을 보고 싶으면 파일에 남긴다.
    trace = os.environ.get("M7_TRACE_FILE")
    if trace:
        with open(trace, "a", encoding="utf-8") as f:
            f.write(json.dumps({"prompts/get": name, "arguments": args}, ensure_ascii=False) + "\n")
    if name == "incident-report":
        ticket = args.get("ticket_id", "INC-0000")
        text = (f"티켓 {ticket} 에 대한 장애 보고서 초안을 작성하세요.\n"
                "섹션: 요약 / 영향 범위 / 타임라인 / 원인 / 재발 방지책.\n"
                "알 수 없는 항목은 추측하지 말고 '확인 필요'라고 쓰세요.")
        return {"description": f"{ticket} 장애 보고서", "messages": [
            {"role": "user", "content": {"type": "text", "text": text}}]}
    if name == "review-checklist":
        text = ("현재 변경분을 아래 체크리스트로 검토하고 항목마다 OK/문제/해당없음으로 답하세요.\n"
                "1. 오류 처리가 있는가\n2. 테스트가 변경분을 덮는가\n3. 비밀값이 코드에 들어가 있지 않은가\n"
                "4. 로그에 개인정보가 남지 않는가")
        return {"description": "리뷰 체크리스트", "messages": [
            {"role": "user", "content": {"type": "text", "text": text}}]}
    return None


def handle(msg):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:  # 알림(notifications/initialized 등)은 응답하지 않는다
        log("notification", method)
        return None
    log("request", method)
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                  "serverInfo": {"name": "runbooks", "version": "0.1.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        lines = "\n".join(RUNBOOKS)
        result = {"content": [{"type": "text", "text": lines}]}
    elif method == "resources/list":
        result = {"resources": RESOURCES}
    elif method == "resources/templates/list":
        result = {"resourceTemplates": [{
            "uriTemplate": "runbook://{service}/{procedure}", "name": "runbook",
            "description": "서비스별 런북", "mimeType": "text/markdown"}]}
    elif method == "resources/read":
        uri = params.get("uri", "")
        path = RUNBOOKS.get(uri)
        if path is None:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32002, "message": f"Resource not found: {uri}"}}
        result = {"contents": [{"uri": uri, "mimeType": "text/markdown",
                                "text": path.read_text(encoding="utf-8")}]}
    elif method == "prompts/list":
        result = {"prompts": PROMPTS}
    elif method == "prompts/get":
        got = get_prompt(params.get("name"), params.get("arguments") or {})
        if got is None:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32602, "message": "Unknown prompt: " + str(params.get("name"))}}
        result = got
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found: " + str(method)}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        out = handle(json.loads(line))
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
