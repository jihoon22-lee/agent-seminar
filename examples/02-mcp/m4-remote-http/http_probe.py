#!/usr/bin/env python3
"""http_probe.py - 원격 MCP 서버(Streamable HTTP)와 오가는 HTTP 요청/응답을 날것 그대로 출력한다.

먼저 다른 터미널에서 서버를 켜 둔다:
    PowerShell:  $env:API_TOKEN = "demo-token-123"; python server.py --http
    Linux bash:  API_TOKEN=demo-token-123 python3 server.py --http

그다음 이 스크립트를 실행한다 (표준 라이브러리 urllib만 사용):
    PowerShell:  $env:DEMO_TOKEN = "demo-token-123"; python http_probe.py
    Linux bash:  DEMO_TOKEN=demo-token-123 python3 http_probe.py

옵션:  --url http://127.0.0.1:3917/mcp   --token <토큰, 기본은 환경 변수 DEMO_TOKEN>
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")  # Windows 기본 인코딩(cp949) 회피


def exchange(title, method, url, token, body=None):
    """요청 하나를 보내고 요청/응답을 사람이 읽는 HTTP 모양으로 출력한다."""
    headers = {"Accept": "application/json, text/event-stream"}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")  # 본문은 UTF-8 바이트
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"

    path = "/" + url.split("/", 3)[3]
    print(f"\n== {title}")
    print(f"  > {method} {path} HTTP/1.1")
    for key, value in headers.items():
        shown = "Bearer ***" if key == "Authorization" else value  # 토큰은 화면에 찍지 않는다
        print(f"  > {key}: {shown}")
    if data:
        print(f"  > \n  > {data.decode('utf-8')}")

    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:
            status, reason, resp_headers, payload = resp.status, resp.reason, resp.headers, resp.read()
    except urllib.error.HTTPError as err:  # 4xx/5xx도 응답이다
        status, reason, resp_headers, payload = err.code, err.reason, err.headers, err.read()

    print(f"  < HTTP {status} {reason}")
    for key in ("Content-Type", "Content-Length", "Allow", "WWW-Authenticate"):
        if resp_headers.get(key):
            print(f"  < {key}: {resp_headers.get(key)}")
    if payload:
        print(f"  < \n  < {payload.decode('utf-8')}")
    else:
        print("  < (본문 없음)")
    return status


def main():
    parser = argparse.ArgumentParser(description="원격 MCP 서버와의 HTTP 교환을 그대로 보여 준다")
    parser.add_argument("--url", default="http://127.0.0.1:3917/mcp")
    parser.add_argument("--token", default=os.environ.get("DEMO_TOKEN", "demo-token-123"))
    args = parser.parse_args()
    url, token = args.url, args.token

    try:
        exchange("1. 토큰 없이 요청 -> 401 (서버가 문전박대)", "POST", url, None,
                 {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        exchange("2. 틀린 토큰 -> 401", "POST", url, "wrong-token",
                 {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        exchange("3. initialize -> 200, 본문은 JSON-RPC 응답 (stdio의 한 줄과 같은 내용)", "POST", url, token,
                 {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "http_probe", "version": "0"}}})
        exchange("4. 알림(id 없음) -> 202 Accepted, 본문 없음", "POST", url, token,
                 {"jsonrpc": "2.0", "method": "notifications/initialized"})
        exchange("5. tools/list -> 200", "POST", url, token, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        exchange("6. tools/call (한글 결과) -> 200", "POST", url, token,
                 {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "lookup_term", "arguments": {"term": "롤백"}}})
        exchange("7. GET -> 405 (이 서버는 서버 푸시용 SSE 스트림을 제공하지 않는다)", "GET", url, token)
    except urllib.error.URLError as err:
        sys.exit(f"\n서버에 접속하지 못했습니다: {err.reason}\n다른 터미널에서 `python server.py --http` 로 서버를 먼저 켜세요.")
    print("\n정리: stdio의 JSON 한 줄이 HTTP POST 본문 하나로 바뀌었을 뿐, 메시지 내용은 같다.")


if __name__ == "__main__":
    main()
