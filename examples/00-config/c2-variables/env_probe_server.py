"""C2 용 아주 작은 MCP 서버 (표준 라이브러리만, 약 70줄).

opencode 가 이 프로세스를 띄울 때 `environment` 값이 어떻게 도착했는지 보여 준다.
  * 시작할 때 out/received.json 에 도착한 값을 기록한다 (사람/check.py 가 확인용으로 읽음)
  * 도구 env_report 가 같은 내용을 모델에게 돌려준다

규칙: stdout 에는 MCP 메시지(JSON 한 줄)만 쓴다. 진단 문구는 stderr 로.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
NAMES = ["DEMO_API_TOKEN", "FILE_TOKEN", "GREETING", "SHELL_STYLE", "UNSET_VALUE", "PLAIN_NOTE"]


def received() -> dict[str, str | None]:
    # None = 변수 자체가 없음, "" = 빈 문자열로 도착
    return {name: os.environ.get(name) for name in NAMES}


def record() -> None:
    out = HERE / "out"
    out.mkdir(exist_ok=True)
    (out / "received.json").write_text(json.dumps(received(), ensure_ascii=False, indent=2), encoding="utf-8")


TOOL = {
    "name": "env_report",
    "description": "이 MCP 서버 프로세스가 opencode 로부터 받은 환경변수 6개의 실제 값을 JSON 으로 돌려준다.",
    "inputSchema": {"type": "object", "properties": {}},
}


def handle(msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification (initialized 등)
        return None
    if method == "initialize":
        version = msg.get("params", {}).get("protocolVersion", "2025-03-26")
        result = {"protocolVersion": version, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "env-probe", "version": "1.0.0"}}
    elif method == "tools/list":
        result = {"tools": [TOOL]}
    elif method == "tools/call":
        text = json.dumps(received(), ensure_ascii=False)
        result = {"content": [{"type": "text", "text": text}]}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> None:
    record()
    print("env-probe ready", file=sys.stderr, flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        reply = handle(json.loads(line))
        if reply is not None:
            print(json.dumps(reply, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
