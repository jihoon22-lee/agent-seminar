"""C3 용 아주 작은 MCP 서버: 도구 하나(current_time)만 제공한다. 표준 라이브러리만 사용.

launch.py 가 OPENCODE_CONFIG_CONTENT 로 이 서버를 "이번 실행에만" 등록한다.
어떤 opencode.json 에도 이 서버는 적혀 있지 않다.

규칙: stdout 에는 MCP 메시지(JSON 한 줄)만 쓴다. 진단 문구는 stderr 로.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

TOOL = {
    "name": "current_time",
    "description": "지금 이 컴퓨터의 현지 날짜와 시각(시간대 포함)을 돌려준다. '지금 몇 시야?' 같은 질문에 쓴다.",
    "inputSchema": {"type": "object", "properties": {}},
}


def handle(msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification
        return None
    if method == "initialize":
        version = msg.get("params", {}).get("protocolVersion", "2025-03-26")
        result = {"protocolVersion": version, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "clock", "version": "1.0.0"}}
    elif method == "tools/list":
        result = {"tools": [TOOL]}
    elif method == "tools/call":
        now = datetime.now().astimezone()
        text = f"{now.strftime('%Y-%m-%d %H:%M:%S')} ({now.tzname()}, UTC{now.strftime('%z')})"
        result = {"content": [{"type": "text", "text": text}]}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> None:
    print("clock ready", file=sys.stderr, flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        reply = handle(json.loads(line))
        if reply is not None:
            print(json.dumps(reply, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
