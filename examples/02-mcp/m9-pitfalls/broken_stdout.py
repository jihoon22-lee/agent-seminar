"""고장 1 — stdout 에 MCP 메시지가 아닌 글자를 섞는다.

stdio MCP 에서 stdout 은 JSON-RPC 메시지 전용 통로다. 로그·배너·print 디버깅은 stderr 로 써야 한다.
opencode 1.19.5 에서 관찰한 것:
  - 줄바꿈이 있는 잡음 한 줄(`print("배너")`)은 무시되고 서버가 정상 동작한다.
  - 줄바꿈 없는 잡음(`sys.stdout.write("배너 ")`, `print(..., end="")`)은 다음 JSON 응답에 붙어 버려
    그 줄이 깨진다 → initialize 에 답이 없는 것으로 보여 제한 시간 뒤 failed.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

# BUG: 시작 배너를 stdout 으로 내보낸다. STDOUT_MODE 로 두 가지 실수를 비교할 수 있다.
#   partial(기본): 줄바꿈 없이 쓴다 → 다음 JSON 응답 앞에 붙어서 그 줄 전체가 깨진다
#   line         : 한 줄을 통째로 출력한다 → opencode 1.19.5 는 JSON 이 아닌 줄을 버리고 계속 진행한다(관찰됨)
if os.environ.get("STDOUT_MODE", "partial") == "line":
    print("=== My MCP Server v1.0 starting ===")
else:
    sys.stdout.write("My MCP Server v1.0 starting... ")

TOOLS = [{"name": "greet", "description": "이름을 받아 한국어로 인사한다.",
          "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}]


def handle(msg):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "broken-stdout", "version": "0.1"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": f"안녕하세요, {params['arguments']['name']}님!"}]}
    else:
        result = {}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


for line in sys.stdin:
    if line.strip():
        out = handle(json.loads(line))
        if out is not None:
            print(json.dumps(out, ensure_ascii=False), flush=True)
