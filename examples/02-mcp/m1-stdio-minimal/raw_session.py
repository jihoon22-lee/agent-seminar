#!/usr/bin/env python3
"""raw_session.py - MCP 서버와 오가는 JSON 줄을 날것 그대로 출력한다.

opencode가 하는 일을 사람이 손으로 흉내 낸다: server.py를 자식 프로세스로 띄우고,
표준 입력으로 JSON 한 줄을 보내고, 표준 출력에서 JSON 한 줄을 읽는다. 그게 전부다.

    python raw_session.py                  # server.py와 대화
    python raw_session.py ../m3-env-config/server.py   # 다른 stdio 서버에도 쓸 수 있다
"""
import json
import subprocess
import sys
import threading
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # Windows 기본 인코딩(cp949) 회피

HERE = Path(__file__).resolve().parent
SERVER = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "server.py"

# 보낼 메시지들. (설명, 메시지, 응답을 기다리는가)
SCRIPT = [
    ("1. 첫 인사: 프로토콜 버전과 기능을 맞춘다",
     {"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                 "clientInfo": {"name": "raw_session", "version": "0"}}}, True),
    ("2. 알림: 인사 끝. id가 없으므로 서버는 답장하지 않는다",
     {"jsonrpc": "2.0", "method": "notifications/initialized"}, False),
    ("3. 도구 목록 요청 - 모델이 보게 될 이름/설명/스키마",
     {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, True),
    ("4. 도구 호출 (성공)",
     {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
      "params": {"name": "lookup_term", "arguments": {"term": "ADR"}}}, True),
    ("5. 도구 호출 (용어집에 없는 용어) -> 오류가 아니라 isError:true 결과",
     {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
      "params": {"name": "lookup_term", "arguments": {"term": "카나리아 배포"}}}, True),
    ("6. 도구 호출 (없는 도구 이름) -> JSON-RPC 오류 -32602",
     {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
      "params": {"name": "delete_everything", "arguments": {}}}, True),
    ("7. 모르는 method -> JSON-RPC 오류 -32601",
     {"jsonrpc": "2.0", "id": 6, "method": "resources/list"}, True),
    ("8. ping",
     {"jsonrpc": "2.0", "id": 7, "method": "ping"}, True),
]


def pump_stderr(stream):
    """서버가 stderr로 쓰는 로그는 프로토콜과 섞이지 않는다. 별도 스레드로 모아 보여 준다."""
    for raw in iter(stream.readline, b""):
        print(f"      [서버 stderr] {raw.decode('utf-8', 'replace').rstrip()}", flush=True)


def main():
    proc = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(SERVER.parent),
    )
    threading.Thread(target=pump_stderr, args=(proc.stderr,), daemon=True).start()
    print(f"서버 실행: {sys.executable} {SERVER.name}\n")

    for title, message, wants_reply in SCRIPT:
        print(f"== {title}")
        line = json.dumps(message, ensure_ascii=False)
        print(f"  >> {line}")
        # 바이트로 직접 쓴다: 운영체제 기본 인코딩의 영향을 받지 않도록 UTF-8 + "\n" 고정
        proc.stdin.write(line.encode("utf-8") + b"\n")
        proc.stdin.flush()
        if wants_reply:
            reply = proc.stdout.readline().decode("utf-8").rstrip("\r\n")
            print(f"  << {reply}")
        else:
            print("  (답장 없음)")
        print()

    proc.stdin.close()  # stdin을 닫는 것이 곧 "대화 끝". 서버는 스스로 종료한다.
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    print(f"서버 종료 코드: {proc.returncode}")
    print("\n정리: MCP는 결국 JSON 한 줄을 보내고 JSON 한 줄을 받는 것이다.")


if __name__ == "__main__":
    main()
