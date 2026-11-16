"""고장 3 — 시작이 느리다.

시작하는 데 시간이 오래 걸리는 서버(큰 모델·인덱스 로딩, 첫 실행 시 패키지 다운로드 등)는
opencode 의 연결 제한 시간 안에 initialize 에 답하지 못해 'failed' 가 된다.
SLOW_START_SECONDS 환경변수(기본 8초)만큼 기다린 뒤에야 입력을 읽기 시작한다.
(덤) SLOW_CALL_SECONDS 를 주면 tools/call 도 그만큼 느려진다 — 도구 호출 제한 시간 실험용.
"""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

delay = float(os.environ.get("SLOW_START_SECONDS", "8"))
print(f"[slow_start] {delay}초 동안 준비하는 척한다", file=sys.stderr, flush=True)
time.sleep(delay)  # BUG: 무거운 초기화를 initialize 응답 전에 끝내려 한다 → 연결 제한 시간 초과
print("[slow_start] 준비 끝", file=sys.stderr, flush=True)

TOOLS = [{"name": "greet", "description": "이름을 받아 한국어로 인사한다.",
          "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}]


def handle(msg):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "slow-start", "version": "0.1"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        time.sleep(float(os.environ.get("SLOW_CALL_SECONDS", "0")))
        result = {"content": [{"type": "text", "text": f"안녕하세요, {params['arguments']['name']}님!"}]}
    else:
        result = {}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


for line in sys.stdin:
    if line.strip():
        out = handle(json.loads(line))
        if out is not None:
            print(json.dumps(out, ensure_ascii=False), flush=True)
