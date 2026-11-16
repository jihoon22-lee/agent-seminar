"""고장 2 — UTF-8 로 맞추지 않는다 (sys.stdout.reconfigure 없음).

MCP 는 UTF-8 JSON 을 주고받는다. 그런데 Python 의 stdout/stdin 은 기본적으로 운영체제 로케일 인코딩을 쓴다.
 - Linux / macOS: 보통 UTF-8 이라 문제가 드러나지 않는다.
 - 한국어 Windows: 파이프로 연결되면 cp949 로 인코딩된다 → 한글이 깨져서 도착하거나 인자의 한글이 깨져 읽힌다.
 - 영어 Windows(cp1252): 한글을 인코딩하지 못해 UnicodeEncodeError 로 서버가 죽는다.
재현 방법은 demo.py 참고 (PYTHONUTF8=0 으로 UTF-8 모드를 끄면 Windows 기본 상태가 된다).
"""
import json
import sys

# BUG: sys.stdout.reconfigure(encoding="utf-8") / sys.stdin.reconfigure(encoding="utf-8") 가 빠져 있다.

TOOLS = [{"name": "greet", "description": "이름을 받아 한국어로 인사한다.",
          "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}]


def handle(msg):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "broken-encoding", "version": "0.1"}}
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
            # ensure_ascii=False 라서 한글이 그대로 stdout 인코딩으로 나간다 (기본값 True 면 \uXXXX 로 이스케이프되어 우연히 안전)
            print(json.dumps(out, ensure_ascii=False), flush=True)
