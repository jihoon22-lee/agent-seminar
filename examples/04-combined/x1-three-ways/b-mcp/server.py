"""팀 용어 사전 MCP 서버 (stdio, 표준 라이브러리만 사용). 도구: lookup_term(term)

stdout 에는 MCP 메시지(줄바꿈으로 구분된 JSON-RPC)만 쓴다. 로그는 stderr 로.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

GLOSSARY = Path(__file__).resolve().parent / "glossary.json"

TOOLS = [{
    "name": "lookup_term",
    "description": "팀 용어 사전에서 용어(ADR, SLO, 에러 버짓, 온콜, 카나리, 핫픽스 등)의 뜻을 찾는다. 팀마다 값이 다르므로 추측하지 말고 이 도구로 확인한다.",
    "inputSchema": {
        "type": "object",
        "properties": {"term": {"type": "string", "description": "찾을 용어. 예: ADR"}},
        "required": ["term"],
    },
}]


def lookup(term: str) -> tuple[str, bool]:
    glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    for key, meaning in glossary.items():
        if key.lower() == term.strip().lower():
            return f"{key}: {meaning}", False
    return f"'{term}' 는 사전에 없습니다. 등록된 용어: {', '.join(glossary)}", True


def handle(msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None  # 알림에는 응답하지 않는다
    if method == "initialize":
        result = {"protocolVersion": (msg.get("params") or {}).get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}}, "serverInfo": {"name": "glossary", "version": "1.0.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = msg.get("params") or {}
        if params.get("name") != "lookup_term":
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "unknown tool"}}
        text, is_error = lookup(str((params.get("arguments") or {}).get("term", "")))
        result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        reply = handle(json.loads(line))
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
