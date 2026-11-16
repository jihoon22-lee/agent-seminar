"""모델이 실제로 받는 도구 목록을 눈으로 확인한다 (표준 라이브러리만 사용).

`opencode debug agent build` 는 권한 규칙(deny 등)은 보여 주지만 MCP 도구 목록은 보여 주지 않는다.
그래서 가짜 LLM 서버(fake_llm.py)를 모델로 지정하고, opencode 가 보낸 요청 본문의 `tools` 배열을 그대로 읽는다.
진짜 모델·인터넷·계정이 필요 없고 결과가 항상 같다.

    python show_model_tools.py                       # 기본(build) 에이전트
    python show_model_tools.py --agent reviewer      # reviewer 에이전트
    python show_model_tools.py --overlay overlays/legacy-on.json                 # 설정 조각(JSON 파일)을 얹어서 비교
    python show_model_tools.py --overlay '{"mcp":{"legacy":{"enabled":true}}}'   # 인라인 JSON 도 가능 (PowerShell 에서는 따옴표가 까다로우니 파일 권장)

opencode 는 임시 폴더로 격리해서 실행한다. 내 전역 설정의 MCP 서버가 섞이지 않고, 세션 기록도 남지 않는다.
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402

BUILTIN = {"bash", "edit", "glob", "grep", "read", "skill", "task", "todowrite", "webfetch", "write", "websearch", "list",
           "apply_patch", "question", "invalid", "list_mcp_resources", "read_mcp_resource", "list_mcp_resource_templates"}


def model_tools(cwd=HERE, agent=None, overlay=None, opencode=None, env=None):
    """opencode run 한 번을 가짜 LLM 에 붙여, 모델이 받은 tools 배열 [{name, description, parameters}] 을 돌려준다."""
    opencode = opencode or shutil.which("opencode") or "opencode"
    with FakeLLM() as llm:
        config = llm.provider_config()
        config.update(overlay or {})
        run_env = dict(env or os.environ)
        run_env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
        run_env["PWD"] = str(cwd)  # opencode run 은 PWD 환경변수로 프로젝트 폴더를 정한다
        cmd = [opencode, "run", "-m", "fake/echo"] + (["--agent", agent] if agent else []) + ["hi"]
        proc = subprocess.run(cmd, cwd=str(cwd), env=run_env, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=180)
        main = llm.main_requests()
        if not main:
            raise RuntimeError("모델 요청이 없었다:\n" + proc.stdout + proc.stderr)
        return [t["function"] for t in main[-1]["tools"]]


def isolated_env(root):
    """opencode 의 설정·데이터·캐시 폴더를 임시 폴더로 돌린 환경 변수. 내 전역 설정과 세션 기록을 건드리지 않는다."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("OPENCODE_CONFIG")}
    for name in ("CONFIG", "DATA", "CACHE", "STATE"):
        path = pathlib.Path(root) / name.lower()
        path.mkdir(parents=True, exist_ok=True)
        env[f"XDG_{name}_HOME"] = str(path)
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "1"
    env["OPENCODE_DISABLE_EXTERNAL_SKILLS"] = "1"
    return env


def mcp_servers(cwd=HERE):
    config = json.loads((pathlib.Path(cwd) / "opencode.json").read_text(encoding="utf-8"))
    return list(config.get("mcp", {}))


def group(tools, servers):
    """도구 이름을 내장 / 서버별로 나눈다 (MCP 도구 이름은 <서버>_<도구>)."""
    groups = {"(내장·기타)": []}
    for t in tools:
        name = t["name"]
        owner = next((s for s in servers if name.startswith(s + "_")), None)
        groups.setdefault(owner or "(내장·기타)", []).append(name)
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent")
    ap.add_argument("--overlay", help="OPENCODE_CONFIG_CONTENT 로 얹을 설정 조각: JSON 문자열 또는 JSON 파일 경로")
    args = ap.parse_args()
    overlay = None
    if args.overlay:
        text = args.overlay.strip()
        overlay = json.loads(text if text.startswith("{") else pathlib.Path(args.overlay).read_text(encoding="utf-8"))
    sandbox = tempfile.mkdtemp(prefix="m8-tools-")
    try:
        tools = model_tools(agent=args.agent, overlay=overlay, env=isolated_env(sandbox))
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    groups = group(tools, mcp_servers())
    size = sum(len(json.dumps(t, ensure_ascii=False)) for t in tools)
    print(f"에이전트: {args.agent or 'build(기본)'}   모델이 받은 도구: {len(tools)}개")
    if not any(k for k in groups if k != "(내장·기타)"):
        print("!! 이 예제의 MCP 서버(docs/ops/legacy) 도구가 하나도 없습니다. `opencode mcp list` 로 연결 상태를 확인하세요 "
              "(Linux 에서 `python` 명령이 없으면 failed 입니다).")
    for owner, names in groups.items():
        print(f"  {owner:<8} {len(names):>2}개  {', '.join(sorted(names))}")
    mcp_size = sum(len(json.dumps(t, ensure_ascii=False)) for t in tools if t["name"] not in BUILTIN)
    print(f"도구 정의 JSON 전체 {size}자 (그중 MCP 도구 {mcp_size}자 ≈ {mcp_size // 4} 토큰)")


if __name__ == "__main__":
    main()
