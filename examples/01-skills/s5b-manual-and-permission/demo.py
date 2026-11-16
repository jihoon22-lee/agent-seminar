"""스킬 자동 사용을 막고 사람이 직접 부르는 방법을 가짜 모델로 확인합니다 (모델·인터넷·쿼터 불필요).

    python demo.py

가짜 모델(mock_llm.py)은 프롬프트에 [[skill:이름]] 표식이 있으면 `skill` 도구를 그 이름으로 호출하는 척합니다.
그래서 "모델이 그 스킬을 목록에서 볼 수 있는가"와 "불러 보면 어떻게 되는가"를 매번 똑같이 재현할 수 있습니다.
Linux에서 `python` 명령이 없으면 `python3` 로 바꿔 실행하세요. (전체 실행 약 1~2분)
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import lab
from mock_llm import MockRun, mock_run

HERE = Path(__file__).resolve().parent


def make_project(parent: Path, name: str, skill_permission: dict | None, agent_overrides: dict | None = None) -> Path:
    """이 예제의 .opencode (스킬 + release 에이전트) 를 임시 폴더에 복사하고, 권한 설정만 바꿔 끼웁니다."""
    root = parent / name
    shutil.copytree(HERE / ".opencode", root / ".opencode", ignore=shutil.ignore_patterns("node_modules", "package*.json", "bun.lock", ".gitignore"))
    cfg: dict = {"$schema": "https://opencode.ai/config.json"}
    if skill_permission is not None:
        cfg["permission"] = {"skill": skill_permission}
    if agent_overrides:
        cfg["agent"] = agent_overrides
    (root / "opencode.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def outcome(run: MockRun, name: str) -> str:
    t = run.transcript
    if run.skill_loaded(name):
        return "로드됨"
    if "auto-rejecting" in t:
        return "ask → run 모드가 자동 거절"
    if "prevents you from using" in t:
        return "deny 규칙에 막힘"
    if "not found" in t:
        return "못 찾음"
    return "?"


def run_all(sb: lab.Sandbox, verbose: bool = True) -> dict[str, MockRun]:
    results: dict[str, MockRun] = {}

    def show(key: str, label: str, run: MockRun, name: str) -> None:
        results[key] = run
        if verbose:
            seen = "보임" if name in run.listed else "안 보임"
            print(f"  - {label}\n      모델 목록에서 {seen} / 모델이 skill 도구로 부르면: {outcome(run, name)}", flush=True)

    if verbose:
        print("== 1. 이 예제의 설정 그대로 (permission.skill = {'*': allow, 'deploy-*': deny})")
    for key, name, label in [
        ("plain", "team-glossary", "team-glossary (아무 제한 없음)"),
        ("flags", "nightly-cleanup", "nightly-cleanup (frontmatter 플래그만 있음)"),
        ("nodesc", "scratch-notes", "scratch-notes (description 없음)"),
        ("deny", "deploy-checklist", "deploy-checklist (permission deny)"),
    ]:
        show(key, label, mock_run(sb, HERE, f"[[skill:{name}]] 실행해 줘"), name)

    with tempfile.TemporaryDirectory(prefix="s5b-") as tmp:
        tmp_path = Path(tmp)
        if verbose:
            print("\n== 2. 에이전트별 규칙")
        show("agent_release", "release 에이전트 (agent 파일이 deploy-* 허용)",
             mock_run(sb, HERE, "[[skill:deploy-checklist]] 실행해 줘", agent="release"), "deploy-checklist")
        proj = make_project(tmp_path, "build-deny", {"*": "allow"}, {"build": {"permission": {"skill": {"deploy-*": "deny"}}}})
        show("agent_build_deny", "build 에이전트에만 deny",
             mock_run(sb, proj, "[[skill:deploy-checklist]] 실행해 줘"), "deploy-checklist")
        show("agent_plan_ok", "같은 설정에서 plan 에이전트",
             mock_run(sb, proj, "[[skill:deploy-checklist]] 실행해 줘", agent="plan"), "deploy-checklist")

        if verbose:
            print("\n== 3. 규칙 순서와 ask")
        proj = make_project(tmp_path, "wrong-order", {"deploy-*": "deny", "*": "allow"})
        show("wrong_order", "순서를 거꾸로: deploy-* deny 다음에 * allow",
             mock_run(sb, proj, "[[skill:deploy-checklist]] 실행해 줘"), "deploy-checklist")
        proj = make_project(tmp_path, "ask", {"*": "allow", "deploy-*": "ask"})
        show("ask_auto", "deploy-* ask + opencode run --auto",
             mock_run(sb, proj, "[[skill:deploy-checklist]] 실행해 줘", auto=True), "deploy-checklist")
        show("ask_noauto", "deploy-* ask + opencode run (--auto 없음)",
             mock_run(sb, proj, "[[skill:deploy-checklist]] 실행해 줘", auto=False), "deploy-checklist")

    if verbose:
        print("\n== 4. 사람이 직접 부르기: opencode run --command deploy-checklist 프로덕션 v2.3")
    run = mock_run(sb, HERE, command="deploy-checklist", command_args=["프로덕션", "v2.3"])
    results["command"] = run
    if verbose:
        has_body = "DEPLOY-CHECKLIST-V3" in run.first_user_text
        has_args = run.first_user_text.rstrip().endswith("프로덕션 v2.3")
        print(f"  deny 상태인데도 스킬 본문이 사용자 메시지로 들어감: {has_body}, 인자가 끝에 붙음: {has_args}")
        print(f"  (이때 모델은 skill 도구를 쓰지 않았음: 도구 호출 표식 없음 = {'→ Skill' not in run.transcript})")
    return results


def main() -> int:
    with lab.Sandbox() as sb:
        run_all(sb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
