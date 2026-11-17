#!/usr/bin/env python3
"""검증용 아주 작은 MCP 서버 (표준 라이브러리만): 가짜 비밀이 든 설정을 돌려주는 도구 네 개.

MCP 도구의 결과가 플러그인의 tool.execute.after 에서 어떤 모양으로 보이는지 확인하려는 용도입니다.
opencode.json 의 mcp.cfg 가 이 파일을 실행합니다. 도구마다 결과 모양이 다릅니다.

    cfg_show_config           content: [{type:"text"}]
    cfg_show_resource         content: [{type:"resource", resource:{uri, text}}]
    cfg_show_structured       content: [{type:"text"}] 와 structuredContent (둘 다 있음)
    cfg_show_structured_only  content: [] 와 structuredContent 만 있음
"""
import json
import sys

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8", newline="\n")

TEXT = "DB_PASSWORD=demo-secret-value-123\nmode=dev"
STRUCTURED = {"DB_PASSWORD": "demo-secret-value-123", "mode": "dev"}
RESULTS = {
    "show_config": {"content": [{"type": "text", "text": TEXT}]},
    "show_resource": {"content": [{"type": "resource", "resource": {"uri": "file:///demo/app.env", "mimeType": "text/plain", "text": "DB_PASSWORD=demo-secret-value-123"}}]},
    "show_structured": {"content": [{"type": "text", "text": TEXT}], "structuredContent": STRUCTURED},
    "show_structured_only": {"content": [], "structuredContent": STRUCTURED},
}


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    if "id" not in msg:  # 알림에는 답하지 않는다
        continue
    method = msg.get("method")
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}}, "serverInfo": {"name": "cfg", "version": "1"}}})
    elif method == "tools/list":
        tools = [{"name": name, "description": f"현재 설정을 보여 준다 ({name}, 예제용: 가짜 비밀이 들어 있음)", "inputSchema": {"type": "object", "properties": {}}} for name in RESULTS]
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": tools}})
    elif method == "tools/call":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": RESULTS.get(msg.get("params", {}).get("name"), RESULTS["show_config"])})
    else:
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
