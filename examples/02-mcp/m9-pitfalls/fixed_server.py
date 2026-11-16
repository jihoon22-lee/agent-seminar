"""고친 서버 — 위 네 가지 고장을 모두 피한 최소 stdio MCP 서버.

 1. stdout 에는 JSON-RPC 메시지만 쓴다. 배너·진단·디버깅 출력은 전부 stderr (log()).
 2. 시작할 때 stdin/stdout 을 UTF-8 로 맞춘다. 파일은 항상 encoding="utf-8" 로 연다.
 3. 입력을 읽기 시작하기 전에 무거운 일을 하지 않는다. 오래 걸리는 준비는 첫 도구 호출 때 하거나 백그라운드에서.
 4. tools/call 의 예외를 잡아 `isError: true` 결과로 돌려준다. 서버는 계속 살아 있고 모델은 오류 내용을 읽고 대응할 수 있다.
"""
import json
import sys
import traceback

sys.stdout.reconfigure(encoding="utf-8")   # (2)
sys.stdin.reconfigure(encoding="utf-8")

TOOLS = [{"name": "greet", "description": "이름을 받아 한국어로 인사한다. name 이 'boom' 이면 일부러 오류를 낸다.",
          "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}]


def log(*args):
    print("[fixed_server]", *args, file=sys.stderr, flush=True)  # (1) 로그는 stderr


def call_tool(name, arguments):
    if name != "greet":
        raise ValueError(f"unknown tool: {name}")
    if arguments["name"] == "boom":
        raise RuntimeError("database connection lost")
    return f"안녕하세요, {arguments['name']}님!"


def handle(msg):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:
        log("notification", method)
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "fixed", "version": "0.1"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            result = {"content": [{"type": "text", "text": call_tool(params["name"], params.get("arguments") or {})}]}
        except Exception as exc:  # (4) 도구 실행 오류는 프로토콜 오류가 아니라 isError 결과로
            log("tool error:", traceback.format_exc())
            result = {"isError": True, "content": [{"type": "text", "text": f"도구 실행 실패: {exc}"}]}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found: " + str(method)}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    log("started")  # (3) 준비 없이 바로 입력 대기
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            out = handle(json.loads(line))
        except Exception:
            log("handler error:", traceback.format_exc())
            continue
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
