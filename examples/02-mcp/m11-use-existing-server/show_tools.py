#!/usr/bin/env python3
"""show_tools.py - 남이 만든 MCP 서버를 켜기 전에 "무엇을 내놓는지"부터 본다 (표준 라이브러리만 사용).

두 단계로 보여 준다.

  1. 서버가 내놓는 도구: opencode.json 의 서버를 직접 띄워 tools/list 를 받는다.
     도구 이름, 설명 글자 수, 입력 스키마 글자 수, 서버가 스스로 붙인 읽기 전용 표시(readOnlyHint).
  2. 모델이 실제로 받는 도구: 가짜 LLM(fake_llm.py)을 모델로 지정해 opencode 를 한 번 실행하고,
     opencode 가 모델에게 보낸 요청의 tools 배열을 읽는다. permission 으로 막은 도구는 여기서 빠진다.
     opencode 는 octest.Sandbox 로 격리해서 실행한다 (내 전역 설정·세션 기록을 건드리지 않는다).

    python show_tools.py                 # 이 폴더의 opencode.json 그대로
    python show_tools.py --no-limit      # permission(막기) 규칙을 뺀 설정으로 비교
    python show_tools.py --raw           # 1단계만 (opencode 없이)

서버를 처음 받을 때는 인터넷(npm/PyPI 미러)이 필요하다. 레지스트리에 3초 안에 닿지 않으면 그 서버는 "건너뜀"으로
표시하고 계속한다 (받아 둔 캐시로 시도해 보려면 --no-probe).
"""
import argparse
import fnmatch
import json
import pathlib
import subprocess
import sys
import tempfile
import os
import shutil
import threading
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))

BUILTIN = {"bash", "edit", "glob", "grep", "read", "skill", "task", "todowrite", "webfetch", "write", "websearch", "list",
           "apply_patch", "question", "invalid", "list_mcp_resources", "read_mcp_resource", "list_mcp_resource_templates"}


def http_ok(url, timeout=3.0):
    """URL 에 HTTP 응답이 오는가 (401/404 같은 오류 응답도 '서버는 살아 있음'으로 본다)."""
    try:
        urllib.request.urlopen(urllib.request.Request(url), timeout=timeout).close()
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:  # noqa: BLE001 - 연결 거부, DNS 실패, 시간 초과 모두 '닿지 않음'
        return False


def npm_registry_reachable():
    """npm 이 쓰는 레지스트리(npm config get registry)에 3초 안에 닿는가. 반환: (가능 여부, 주소 또는 사유)."""
    npm = shutil.which("npm")
    if not npm or not shutil.which("npx"):
        return False, "(npm/npx 없음)"
    try:
        url = subprocess.run([npm, "config", "get", "registry"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False, "(npm config 실패)"
    return url.startswith("http") and http_ok(url), url


def uv_index_reachable():
    """uv 가 실제로 쓰는 패키지 인덱스에 닿는가. uv 에게 hatchling 의 버전 목록을 받아 보게 해서 판정한다.

    UV_DEFAULT_INDEX / UV_INDEX_URL / uv.toml 의 index 설정은 uv 가 알아서 적용한다.
    pip 설정(PIP_INDEX_URL, pip.conf)은 uv 가 읽지 않으므로 보지 않는다. 8초 안에 끝나지 않으면 닿지 않는 것으로 본다.
    """
    uv = shutil.which("uv")
    if not uv or not shutil.which("uvx"):
        return False, "(uv/uvx 없음)"
    label = os.environ.get("UV_DEFAULT_INDEX") or os.environ.get("UV_INDEX_URL") or "uv 기본값(uv.toml 이 없으면 https://pypi.org/simple)"
    env = dict(os.environ, UV_HTTP_RETRIES="0", UV_HTTP_TIMEOUT="3")
    try:
        proc = subprocess.run([uv, "pip", "compile", "--no-cache", "-q", "-"], input=b"hatchling\n", capture_output=True, timeout=8, env=env, cwd=str(HERE))
    except (OSError, subprocess.TimeoutExpired):
        return False, label
    return proc.returncode == 0, label


NET_ERROR_WORDS = ("error sending request", "dns error", "failed to lookup", "tcp connect", "connection refused", "timed out", "client error (connect)",
                   "failed to fetch", "enotfound", "econnrefused", "etimedout", "eai_again", "econnreset", "fetch failed", "네트워크 오류")


def network_failure(text):
    """서버가 시작하지 못한 이유가 네트워크 문제로 보이는가 (레지스트리 확인을 통과한 뒤에도 중간에 끊길 수 있다)."""
    low = (text or "").lower()
    return any(w in low for w in NET_ERROR_WORDS)


def registry_for(command):
    """서버 명령이 어느 레지스트리를 쓰는지: npx -> npm, uvx -> uv 인덱스, 그 밖(로컬 실행)은 None."""
    return {"npx": npm_registry_reachable, "uvx": uv_index_reachable}.get(pathlib.Path(command[0]).stem)


def size(obj):
    """모델에게 가는 JSON 글자 수 (한글도 1글자로 센다)."""
    return len(json.dumps(obj, ensure_ascii=False))


def list_server_tools(command, cwd=HERE, timeout=90):
    """서버를 띄워 initialize -> tools/list. 반환: (도구 목록, 오류 메시지 또는 None)."""
    try:
        proc = subprocess.Popen([shutil.which(command[0]) or command[0], *command[1:]], cwd=str(cwd), stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # Windows의 npx는 npx.cmd라 전체 경로가 필요
    except OSError as exc:
        return [], f"실행 불가: {exc}"
    timer = threading.Timer(timeout, proc.kill)
    timer.start()
    try:
        def rpc(msg_id, method, params=None):
            msg = {"jsonrpc": "2.0", "id": msg_id, "method": method, **({"params": params} if params is not None else {})}
            proc.stdin.write(json.dumps(msg).encode() + b"\n")
            proc.stdin.flush()
            while True:
                line = proc.stdout.readline().decode("utf-8", "replace")
                if not line:
                    raise RuntimeError(proc.stderr.read().decode("utf-8", "replace") or "서버가 응답 없이 끝났다")
                msg = json.loads(line)
                if msg.get("id") == msg_id:
                    return msg

        rpc(1, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "show_tools", "version": "0"}})
        proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        proc.stdin.flush()
        return rpc(2, "tools/list")["result"]["tools"], None
    except Exception as exc:  # noqa: BLE001 - 안내 메시지로 바꿔 보여 준다
        text = str(exc).strip()
        if not text:
            return [], "알 수 없는 오류"
        last = text.splitlines()[-1][:200]
        # npm 은 원인(ECONNREFUSED 등)을 앞쪽 줄에 쓰고 마지막 줄에는 로그 위치만 적는다: 전체에서 판정해 표시를 붙인다
        return [], ("(네트워크 오류) " + last) if network_failure(text) and not network_failure(last) else last
    finally:
        timer.cancel()
        proc.kill()
        proc.wait()


def is_denied(permission, full_name):
    """permission 규칙을 위에서 아래로 훑어 마지막으로 일치한 값이 deny 인가 (M8: 마지막 일치가 이긴다)."""
    verdict = None
    for pattern, action in permission.items():
        if fnmatch.fnmatch(full_name, pattern):
            verdict = action
    return verdict == "deny"


def model_tools(project):
    """project 폴더의 opencode.json 으로 가짜 LLM 에 opencode run 을 붙여, 모델이 받은 tools 배열을 돌려준다."""
    from fake_llm import FakeLLM
    from octest import Sandbox
    with Sandbox("m11-tools") as sb, FakeLLM() as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
        proc = sb.opencode(["run", "-m", "fake/echo", "hi"], project, timeout=180, extra_env=env)
        main = llm.main_requests()
        if not main:
            raise RuntimeError("모델 요청이 없었다:\n" + proc.stdout + proc.stderr)
        return [t["function"] for t in main[-1]["tools"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-limit", action="store_true", help="permission 규칙을 뺀 설정으로 본다")
    ap.add_argument("--no-probe", action="store_true", help="레지스트리 확인(3초)을 건너뛰고 바로 서버를 띄운다 (받아 둔 캐시로 시도할 때)")
    ap.add_argument("--raw", action="store_true", help="서버가 내놓는 도구만 보고 끝낸다 (opencode 를 실행하지 않음)")
    args = ap.parse_args()

    config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
    permission = {} if args.no_limit else config.get("permission", {})
    servers = {n: s for n, s in config["mcp"].items() if s.get("enabled", True)}

    print("== 1. 서버가 내놓는 도구 (tools/list)")
    offered = {}
    skipped = []
    for name, server in servers.items():
        print(f"\n[{name}] {' '.join(server['command'])}")
        probe = None if args.no_probe else registry_for(server["command"])
        if probe:
            reachable, where = probe()
            if not reachable:
                print(f"  건너뜀: 패키지 레지스트리({where})에 3초 안에 닿지 않는다. 미러를 지정하거나 (npm: npm config set registry <주소>, "
                      "uv: UV_DEFAULT_INDEX=<주소>) 받아 둔 캐시로 시도하려면 --no-probe")
                skipped.append(name)
                continue
        tools, err = list_server_tools(server["command"])
        if err:
            print(f"  시작 실패: {err}")
            continue
        offered[name] = tools
        print(f"  {'도구':<28}{'설명':>6}{'스키마':>7}  읽기전용표시  막힘")
        for t in tools:
            hint = (t.get("annotations") or {}).get("readOnlyHint")
            mark = "예" if hint else ("아니오" if hint is False else "없음")
            blocked = "deny" if is_denied(permission, f"{name}_{t['name']}") else ""
            print(f"  {t['name']:<28}{len(t.get('description', '')):>6}{size(t.get('inputSchema', {})):>7}  {mark:<10}  {blocked}")
        writers = [t["name"] for t in tools if (t.get("annotations") or {}).get("readOnlyHint") is not True]
        if writers:
            print(f"  -> 읽기 전용이 아닌 도구 {len(writers)}개: {', '.join(writers)}")
    total_tools = sum(len(t) for t in offered.values())
    total_size = sum(size({"name": t["name"], "description": t.get("description", ""), "parameters": t.get("inputSchema", {})})
                     for ts in offered.values() for t in ts)
    print(f"\n서버 합계: 도구 {total_tools}개, 이름+설명+스키마 약 {total_size}자 (≈ {total_size // 4} 토큰)")

    if args.raw:
        return
    print("\n== 2. 모델이 실제로 받는 도구 (가짜 LLM 이 받은 요청)" + ("  [--no-limit: permission 규칙 제외]" if args.no_limit else ""))
    project = HERE
    tmp = None
    if args.no_limit or skipped:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="m11-tools-"))
        if args.no_limit:
            config.pop("permission", None)
        for name in skipped:  # 닿지 않는 레지스트리의 서버는 opencode 시작 때 멈춰 있지 않도록 끈다
            config["mcp"][name]["enabled"] = False
        servers = {n: sv for n, sv in servers.items() if n not in skipped}
        (tmp / "opencode.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        if (HERE / "sandbox").is_dir():
            shutil.copytree(HERE / "sandbox", tmp / "sandbox")
        project = tmp
    try:
        tools = model_tools(project)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    mcp_tools = [t for t in tools if t["name"] not in BUILTIN]
    for name in servers:
        mine = sorted(t["name"] for t in mcp_tools if t["name"].startswith(name + "_"))
        print(f"  {name:<6} {len(mine):>2}개  {', '.join(mine)}")
    mcp_size = sum(size(t) for t in mcp_tools if any(t["name"].startswith(n + "_") for n in servers))
    print(f"  (내장 도구 {len([t for t in tools if t['name'] in BUILTIN])}개는 opencode 가 원래 주는 것)")
    n_mcp = len([t for t in mcp_tools if any(t["name"].startswith(n + "_") for n in servers)])
    print(f"모델에게 가는 MCP 도구: {n_mcp}개, 정의 JSON {mcp_size}자 (≈ {mcp_size // 4} 토큰) — 매 요청마다 반복해서 전송")


if __name__ == "__main__":
    main()
