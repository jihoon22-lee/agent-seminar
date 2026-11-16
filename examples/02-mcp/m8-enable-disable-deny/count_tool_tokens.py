"""MCP 도구가 컨텍스트를 얼마나 차지하는지 어림해 본다 (표준 라이브러리만 사용).

opencode.json 의 mcp 항목마다 서버를 stdio 로 직접 띄워 tools/list 를 받고,
도구 이름 + 설명 + 입력 스키마(JSON)의 글자 수를 센다. 토큰 수는 글자 수 / 4 로 어림한다
(영어 기준 관례이고, 한글은 글자당 토큰이 더 많아 실제로는 더 클 수 있다).

모델에게는 "켜져 있는 도구 정의 전부"가 **매 요청마다** 붙는다. 그래서 쓰지 않는 도구도 대화가
길어질수록 계속 비용을 낸다. 아래 표의 '요청당' 숫자가 그 값이다.

    python count_tool_tokens.py                  # 이 폴더의 opencode.json
    python count_tool_tokens.py path/to/opencode.json
"""
import fnmatch
import json
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

TOKENS_PER_CHAR = 1 / 4


def fetch_tools(entry, base_dir, timeout=20):
    """local MCP 서버를 띄워 initialize → tools/list 로 도구 정의 목록을 받는다."""
    command = list(entry["command"])
    if command[0] in ("python", "python3"):
        command[0] = sys.executable  # Linux 에 `python` 이 없어도 동작하도록
    proc = subprocess.Popen(command, cwd=base_dir, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                            env={**__import__("os").environ, **entry.get("environment", {})})
    try:
        def call(mid, method, params=None):
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())

        call(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "count_tool_tokens", "version": "0"}})
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        return call(2, "tools/list")["result"]["tools"]
    finally:
        proc.kill()


def tool_size(tool):
    """(설명 글자 수, 스키마 글자 수, 이름 글자 수)"""
    return (len(tool.get("description", "")),
            len(json.dumps(tool.get("inputSchema", {}), ensure_ascii=False)),
            len(tool["name"]))


def rules_from_config(config):
    """(패턴, 동작) 목록을 적용 순서대로 모은다. 옛 단축형 tools:{패턴:bool} 이 먼저, 그 다음 permission 순서대로."""
    rules = [(p, "allow" if on else "deny") for p, on in (config.get("tools") or {}).items()]
    perm = config.get("permission")
    if isinstance(perm, dict):
        rules += [(p, v) for p, v in perm.items() if isinstance(v, str)]
    return rules


def is_denied(full_name, rules):
    """마지막으로 일치한 규칙이 이긴다 (opencode permission 과 같은 방식). 일치하는 규칙이 없으면 허용."""
    state = "allow"
    for pattern, action in rules:
        if fnmatch.fnmatch(full_name, pattern):
            state = action
    return state == "deny"


def opencode_tool_name(server, tool):
    return f"{server}_{tool}"  # opencode 가 모델에게 보여 주는 이름


def analyse(config, base_dir):
    """서버별 분석 결과 목록. 각 항목: name, enabled, tools[{name, full, chars, hidden}]"""
    rules = rules_from_config(config)
    result = []
    for name, entry in (config.get("mcp") or {}).items():
        if entry.get("type") != "local" or "command" not in entry:
            continue
        tools = fetch_tools(entry, base_dir)
        rows = []
        for t in tools:
            full = opencode_tool_name(name, t["name"])
            d, s, n = tool_size(t)
            rows.append({"name": t["name"], "full": full, "chars": d + s + n, "desc_chars": d,
                         "hidden": is_denied(full, rules)})
        result.append({"name": name, "enabled": entry.get("enabled", True), "tools": rows})
    return result


def main():
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).with_name("opencode.json")).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    servers = analyse(config, path.parent)
    print(f"설정: {path}")
    print("규칙(적용 순서, 마지막 일치가 이김): " + (", ".join(f"{p}={a}" for p, a in rules_from_config(config)) or "없음") + "\n")
    print(f"{'server':<8}{'state':<5}{'tools':>6}{'desc_chars':>11}{'def_chars':>10}{'~tokens':>8}   sent to the model")
    total_sent = 0
    for s in servers:
        chars = sum(t["chars"] for t in s["tools"])
        desc = sum(t["desc_chars"] for t in s["tools"])
        sent_tools = [t for t in s["tools"] if not t["hidden"]] if s["enabled"] else []
        sent_chars = sum(t["chars"] for t in sent_tools)
        total_sent += sent_chars
        state = "on" if s["enabled"] else "off"
        print(f"{s['name']:<8}{state:<5}{len(s['tools']):>6}{desc:>11}{chars:>10}{int(chars * TOKENS_PER_CHAR):>8}"
              f"   {len(sent_tools)} tools, ~{int(sent_chars * TOKENS_PER_CHAR)} tokens per request")
    print(f"\n합계: 모델에게 가는 MCP 도구 정의 ≈ {int(total_sent * TOKENS_PER_CHAR)} 토큰 (매 요청마다)")
    print("\n가장 큰 도구 5개 (full name = 모델이 보는 이름):")
    allrows = [(t["chars"], s["name"], t["full"], s["enabled"], t["hidden"]) for s in servers for t in s["tools"]]
    for chars, server, full, enabled, hidden in sorted(allrows, reverse=True)[:5]:
        note = "서버 꺼짐" if not enabled else ("규칙으로 숨김" if hidden else "전달됨")
        print(f"  {full:<24}{int(chars * TOKENS_PER_CHAR):>5} tokens  ({note})")


if __name__ == "__main__":
    main()
