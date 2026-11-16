"""고장 4 — 도구를 호출하는 순간 예외로 죽는다.

연결과 tools/list 는 멀쩡해서 `opencode mcp list` 는 connected 로 보인다. 그래서 더 찾기 어렵다.
tools/call 에서 처리되지 않은 예외가 나면 서버 프로세스가 통째로 종료된다.
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

TOOLS = [{"name": "greet", "description": "이름을 받아 한국어로 인사한다.",
          "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}]


def handle(msg):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "crash-on-call", "version": "0.1"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        raise RuntimeError("database connection lost")  # BUG: 잡지 않은 예외 → 프로세스 종료 (traceback 은 stderr 로)
    else:
        result = {}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


for line in sys.stdin:
    if line.strip():
        out = handle(json.loads(line))
        if out is not None:
            print(json.dumps(out, ensure_ascii=False), flush=True)
