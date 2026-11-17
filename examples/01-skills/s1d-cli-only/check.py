"""s1d 검증: 스크립트 없는 스킬(SKILL.md 한 장)의 명령이 실제 git 저장소에서 의도대로 동작하는지.

- SKILL.md 의 명령 블록이 bash 와 PowerShell 5.1 에서 같은 모양으로 쓸 수 있는 단순한 한 줄 명령인지 (정적 검사)
- 가짜 모델이 스킬을 불러 SKILL.md 의 명령을 그대로 실행하면 병합된 브랜치만 지워지는지
Windows(PowerShell 5.1) 실행은 이 검사가 하지 않는다. 정적 검사는 사용하지 않는 문법이 없음을 보일 뿐이다.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, skill_loaded  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare  # noqa: E402
from fake_llm import FakeLLM  # noqa: E402

SKILL = HERE / ".opencode/skills/branch-cleanup/SKILL.md"
skill_md = SKILL.read_text(encoding="utf-8")
EXPECT_DELETED = ["chore/deps", "feature/login", "fix/typo"]
EXPECT_KEPT = ["feature/current", "main", "wip/search"]


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)


def branches(cwd):
    return sorted(line.strip("* +").strip() for line in git(cwd, "branch").stdout.splitlines() if line.strip())


def fenced_commands(text: str) -> list[str]:
    """``` 블록 안의 비어 있지 않은 줄들."""
    out, inside = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
        elif inside and line.strip():
            out.append(line.strip())
    return out


def pwd(path):
    return {"PWD": str(path)}


tmp_root = pathlib.Path(tempfile.mkdtemp(prefix="s1d-"))
had_oc_gitignore = (HERE / ".opencode" / ".gitignore").exists()
try:
    # 1. SKILL.md 정적 검사
    cmds = fenced_commands(skill_md)
    check("SKILL.md 는 name: branch-cleanup 과 description 을 가짐",
          re.search(r"^name: branch-cleanup$", skill_md, re.M) is not None and re.search(r"^description: .*병합된 브랜치 정리해줘", skill_md, re.M) is not None)
    check("명령 블록의 모든 줄이 `git ` 으로 시작하는 한 줄 명령", len(cmds) == 5 and all(c.startswith("git ") for c in cmds), str(cmds))
    banned = ["&&", "||", "|", ";", "$", "`", "xargs", ">", "<", "%"]
    # <이름> 은 사람이 읽는 자리표시자다 (실행 전에 브랜치 이름으로 바뀜). 나머지 문자만 검사한다.
    banned_found = [(c, b) for c in cmds for b in banned if b in c.replace("<이름>", "NAME")]
    check("명령 줄에 &&, ||, 파이프, ;, $(), 백틱, xargs, 리다이렉트, $ 가 없음 (bash 와 PowerShell 5.1 에서 같은 모양)", not banned_found, str(banned_found))
    check("강제 삭제 옵션(대문자 D)이 SKILL.md 어디에도 없음", "-D" not in skill_md and "--delete --force" not in skill_md)
    check("삭제 명령은 `git branch -d <이름>` 한 가지뿐", [c for c in cmds if " -d" in c or "--delete" in c] == ["git branch -d <이름>"])
    check("목록 명령이 `git branch --merged main` 으로 SKILL.md 에 적혀 있음", "git branch --merged main" in cmds)
    check("규칙: main·현재 브랜치(*)·다른 작업 폴더(+)를 지우지 않는다고 적혀 있음",
          all(s in skill_md for s in ("`main` 과 지금 체크아웃한 브랜치는 절대 지우지 않는다", "`*` 로 시작", "`+` 로 시작")))
    check("스크립트 파일이 없음 (SKILL.md 한 장)", [p.name for p in SKILL.parent.iterdir()] == ["SKILL.md"])

    # 2. prepare.py
    # 예제 폴더의 sandbox/ 는 README 를 따라 하는 사람이 쓰는 곳이라 건드리지 않는다. 임시 폴더에 같은 저장소를 만들어 검사한다.
    SANDBOX = tmp_root / "sandbox"
    proc = subprocess.run([sys.executable, str(HERE / "prepare.py"), str(SANDBOX)], capture_output=True, text=True, encoding="utf-8")
    check("prepare.py 실행", proc.returncode == 0, proc.stderr)
    check("sandbox 브랜치 6개, 현재 브랜치 feature/current",
          branches(SANDBOX) == sorted(EXPECT_DELETED + EXPECT_KEPT) and git(SANDBOX, "branch", "--show-current").stdout.strip() == "feature/current",
          str(branches(SANDBOX)))
    merged = sorted(l.strip("* +").strip() for l in git(SANDBOX, "branch", "--merged", "main").stdout.splitlines())
    check("`git branch --merged main` = 삭제 대상 3 + main + 현재 브랜치 (wip/search 는 없음)",
          merged == sorted(EXPECT_DELETED + ["main", "feature/current"]), str(merged))
    check("작업 트리가 깨끗함 (스킬이 첫 커밋에 포함됨)", git(SANDBOX, "status", "--short").stdout.strip() == "")
    forced = git(SANDBOX, "branch", "-d", "wip/search")
    check("병합되지 않은 브랜치는 `git branch -d` 가 스스로 거절함 (그래서 강제 삭제가 필요 없음)",
          forced.returncode != 0 and "not fully merged" in forced.stderr and "wip/search" in branches(SANDBOX), forced.stderr)
    shutil.rmtree(SANDBOX, onerror=prepare._force_remove)
    prepare.build(SANDBOX)

    with Sandbox("s1d") as sb:
        # 3. 스킬 발견
        for label, cwd in (("예제 폴더", HERE), ("sandbox", SANDBOX)):
            skills = {s["name"]: s for s in sb.debug_skills(cwd=cwd, extra_env=pwd(cwd))}
            check(f"debug skill 에 branch-cleanup 표시 ({label})", "branch-cleanup" in skills and str(cwd) in skills["branch-cleanup"]["location"])
        check("description 에 한국어 트리거 문구", "병합된 브랜치 정리해줘" in skills["branch-cleanup"]["description"])

        # 4. 가짜 모델이 스킬을 불러 SKILL.md 의 명령을 그대로 실행한다. 4번 단계는 모델이 목록을 읽고 고르는 일을 흉내 낸다.
        list_merged = [c for c in cmds if "--merged" in c][0]
        delete_tpl = [c for c in cmds if " -d " in c][0]
        victims = []
        for line in git(SANDBOX, *list_merged.split()[1:]).stdout.splitlines():
            name = line.strip()
            if line.startswith(("*", "+")) or name == "main":  # SKILL.md 규칙 2
                continue
            victims.append(name)
        check("SKILL.md 규칙대로 목록에서 main, `*`, `+` 줄을 빼면 삭제 대상은 정확히 3개", sorted(victims) == EXPECT_DELETED, str(victims))
        script = [("tool", "skill", {"name": "branch-cleanup"})]
        script += [("tool", "bash", {"command": c, "description": "branch cleanup"}) for c in cmds if " -d " not in c and c != "git branch"]
        script += [("tool", "bash", {"command": delete_tpl.replace("<이름>", v), "description": "delete merged branch"}) for v in victims]
        script += [("tool", "bash", {"command": "git branch", "description": "verify"}), "DONE"]
        with FakeLLM(script=script) as llm:
            res = sb.opencode(["run", "-m", "fake/echo", "병합된 브랜치 정리해줘"], SANDBOX, timeout=240,
                              extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "PWD": str(SANDBOX)})
            reqs = llm.main_requests()
            sysmsg = "\n".join(llm.message_text(m) for m in reqs[0]["messages"] if m["role"] == "system")
            tool_out = [llm.message_text(m) for m in reqs[-1]["messages"] if m["role"] == "tool"]
        check("가짜 모델: 요청 수 9 = 스크립트 길이 (스킬 1 + 조회 3 + 삭제 3 + 확인 1 + 마무리 1)", len(reqs) == len(script) == 9, f"{len(reqs)} vs {len(script)} {res.stderr[-200:]}")
        check("모델의 시스템 프롬프트에는 이름과 description 만 있고 본문 규칙은 없음",
              "<name>branch-cleanup</name>" in sysmsg and "강제 삭제 옵션" not in sysmsg)
        check("스킬을 불러오면 도구 결과로 본문이 전달됨", any('<skill_content name="branch-cleanup">' in t and "git branch -d" in t for t in tool_out), str(tool_out)[:200])
        check("도구 결과에 `Deleted branch ...` 가 삭제된 3개만큼 있음", sum(t.count("Deleted branch") for t in tool_out) == 3, str(tool_out)[-400:])
        left = branches(SANDBOX)
        check("결과: 병합된 3개는 사라지고 main, 현재 브랜치, 병합 안 된 wip/search 는 남음", left == EXPECT_KEPT, str(left))
        check("현재 브랜치는 그대로 feature/current", git(SANDBOX, "branch", "--show-current").stdout.strip() == "feature/current")
        check("스킬이 쓴 모든 명령 중 `-D` 나 push·remote 가 없음",
              not any(re.search(r"-D\b|push|remote", c) for c in [x["command"] for x in (s[2] for s in script if isinstance(s, tuple) and s[1] == "bash")]))

        # 5. 실제 모델 (soft)
        if model_enabled():
            prepare.build(SANDBOX)
            out = sb.run_model("병합된 브랜치 정리해줘", cwd=SANDBOX, extra_env=pwd(SANDBOX), timeout=300)
            model_check("모델이 branch-cleanup 스킬을 불러옴", out, skill_loaded(out, "branch-cleanup"))
            model_check("병합된 3개만 지워지고 main·현재·wip/search 는 남음", out, branches(SANDBOX) == EXPECT_KEPT)
finally:
    shutil.rmtree(tmp_root, onerror=prepare._force_remove) if tmp_root.exists() else None
    stray = HERE / ".opencode" / ".gitignore"
    if stray.exists() and not had_oc_gitignore:
        stray.unlink()
    for name in ("node_modules", "package.json", "package-lock.json", "bun.lock"):
        p = HERE / ".opencode" / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()

finish()
