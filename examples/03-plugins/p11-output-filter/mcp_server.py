#!/usr/bin/env python3
"""검증용 아주 작은 MCP 서버 (표준 라이브러리만): 가짜 비밀이 든 설정을 돌려주는 도구 하나.

MCP 도구의 결과가 플러그인의 tool.execute.after 에서 어떤 모양으로 보이는지 확인하려는 용도입니다.
opencode.json 의 mcp.cfg 가 이 파일을 실행합니다 (도구 이름: cfg_show_config).
"""
import json
import sys

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8", newline="\n")

TEXT = "DB_PASSWORD=demo-secret-value-123\nmode=dev"


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
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": [{"name": "show_config", "description": "현재 설정을 보여 준다 (예제용: 가짜 비밀이 들어 있음)", "inputSchema": {"type": "object", "properties": {}}}]}})
    elif method == "tools/call":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"content": [{"type": "text", "text": TEXT}]}})
    else:
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
