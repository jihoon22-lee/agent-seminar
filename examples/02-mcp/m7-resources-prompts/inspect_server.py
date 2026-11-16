"""실행 중인 `opencode serve` 에게 MCP 프롬프트(슬래시 명령)와 리소스 목록을 물어본다.

    opencode serve --port 4096        # 이 폴더에서 (다른 터미널)
    python inspect_server.py http://127.0.0.1:4096

TUI 가 `/` 와 `@` 자동완성에 보여 주는 목록이 바로 이 두 API 의 응답이다.
  GET /command               → source 가 "mcp" 인 항목이 MCP 프롬프트
  GET /experimental/resource → MCP 리소스 (키는 "<서버>:<URI>")
"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")


def http_json(method, url, body=None, timeout=300):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def mcp_commands(base):
    return [c for c in http_json("GET", base + "/command") if c.get("source") == "mcp"]


def mcp_resources(base):
    return http_json("GET", base + "/experimental/resource")


if __name__ == "__main__":
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4096").rstrip("/")
    print("== MCP 프롬프트 → 슬래시 명령 (GET /command, source=mcp)")
    for c in mcp_commands(base):
        print(f"  /{c['name']:<28} hints={c.get('hints')}  {c.get('description')}")
    print("== MCP 리소스 (GET /experimental/resource)")
    for key, r in mcp_resources(base).items():
        print(f"  {r['uri']:<30} client={r['client']}  name={r['name']}  mime={r.get('mimeType')}")
