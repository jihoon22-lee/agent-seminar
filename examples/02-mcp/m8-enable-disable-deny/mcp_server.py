"""m8 — 도구 묶음이 다른 세 가지 MCP 서버를 하나의 파일로 흉내 낸다 (표준 라이브러리만 사용).

    python mcp_server.py --profile docs     # 문서 검색 서버
    python mcp_server.py --profile ops      # 운영 서버: 쓸 만한 도구 2개 + noisy_* 도구 4개
    python mcp_server.py --profile legacy   # 예전 서버: 도구가 많고 설명이 길다

stdio JSON-RPC (줄 단위). stdout 에는 MCP 메시지만, 로그는 stderr 로.
도구를 실제로 실행하면 "이 도구는 데모용이라 아무것도 하지 않는다"는 문장을 돌려준다.
"""
import argparse
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

LONG = ("이 도구는 예전 시스템과의 호환을 위해 남겨 둔 것이다. 인자를 그대로 전달하고 결과를 가공 없이 돌려준다. "
        "호출 전에 반드시 대상 환경(dev/stage/prod)을 확인하고, 실패하면 재시도하지 말고 담당자에게 알린다. " * 3)


def tool(name, description, props=None):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": props or {}}}


PROFILES = {
    "docs": [
        tool("lookup", "데모 문서에서 키워드를 찾아 한 줄 요약을 돌려준다.", {"keyword": {"type": "string"}}),
        tool("outline", "문서의 목차를 돌려준다.", {"doc": {"type": "string"}}),
    ],
    "ops": [
        tool("status", "서비스 상태를 한 줄로 돌려준다 (데모: 항상 healthy).", {"service": {"type": "string"}}),
        tool("restart", "서비스를 재시작한다 (데모: 실제로는 아무것도 하지 않음).", {"service": {"type": "string"}}),
        tool("noisy_trace_dump", "내부 트레이스 전체를 덤프한다. " + LONG),
        tool("noisy_heap_dump", "힙 덤프를 만든다. " + LONG),
        tool("noisy_thread_dump", "스레드 덤프를 만든다. " + LONG),
        tool("noisy_gc_stats", "GC 통계를 돌려준다. " + LONG),
    ],
    "legacy": [tool(f"op_{i:02d}", f"예전 작업 {i}번. " + LONG, {"arg": {"type": "string"}}) for i in range(1, 13)],
}


def handle(msg, tools, name):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}}, "serverInfo": {"name": name, "version": "0.1.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": tools}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": f"[{name}] {params.get('name')} 실행됨 (데모: 아무 일도 하지 않음)"}]}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found: " + str(method)}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=sorted(PROFILES), required=True)
    args = ap.parse_args()
    tools = PROFILES[args.profile]
    print(f"[{args.profile}] started, {len(tools)} tools", file=sys.stderr, flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        out = handle(json.loads(line), tools, args.profile)
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
