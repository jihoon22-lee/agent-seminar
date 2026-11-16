"""s1a 검증: 스킬 발견 + (선택) 모델이 스킬을 읽고 컨벤션에 맞는 메시지를 쓰는지."""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, skill_loaded  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402  (이 폴더의 복사본)
SANDBOX = HERE / "sandbox"
PY = sys.executable


def run_fake(sb, cwd, script):
    """진짜 모델 대신 가짜 LLM 서버(fake_llm.py)를 붙여 opencode 를 실행하고, 모델이 받은 요청을 돌려준다.
    script 의 ("tool", 이름, 인자) 는 '모델이 그 도구를 호출한 것처럼' 흉내 낸다. 모델 한도·무작위성이 없다."""
    with FakeLLM(script=script) as llm:
        sb.opencode(["run", "-m", "fake/echo", "--auto", "테스트"], cwd, timeout=180,
                    extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "PWD": str(cwd)})
        return llm, llm.main_requests()


def system_text(llm, request):
    return "\n".join(llm.message_text(m) for m in request["messages"] if m["role"] == "system")


def tool_texts(llm, request):
    return [llm.message_text(m) for m in request["messages"] if m["role"] == "tool"]


def pwd(path):
    """octest 는 cwd 만 바꾸고 환경 변수 PWD 는 그대로 둔다. opencode 는 PWD 를 보므로 같이 맞춘다."""
    return {"PWD": str(path)}


# SKILL.md 에 적힌 1행 규칙과 같은 정규식
CONVENTION = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9-]+\))?: .{1,50}$"
)
# 모델이 코드 블록·글머리표 안에 넣어도 찾을 수 있도록 앞쪽 장식은 허용
LINE_WITH_DECOR = re.compile(
    r"^[\s>*`\-]*((feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9-]+\))?: .{1,50})[\s`]*$",
    re.M,
)

def _force_remove(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)  # Windows: .git 안의 읽기 전용 파일
    func(path)


had_oc_gitignore = (HERE / ".opencode" / ".gitignore").exists()

try:
    # 1. 규칙 파일 자체 점검 (모델 없이)
    skill_md = (HERE / ".opencode/skills/commit-message/SKILL.md").read_text(encoding="utf-8")
    check("SKILL.md 에 정규식이 그대로 적혀 있음", CONVENTION.pattern in skill_md)
    check("좋은 메시지는 정규식을 통과", bool(CONVENTION.match("fix(pricing): 할인율 범위 검증 추가")))
    check("나쁜 메시지는 정규식에서 걸러짐",
          not CONVENTION.match("Fixed bug in pricing.") and not CONVENTION.match("feature(x): y"))

    # 2. prepare.py 가 만든 저장소 상태
    proc = subprocess.run([PY, str(HERE / "prepare.py")], capture_output=True, text=True, encoding="utf-8")
    check("prepare.py 실행", proc.returncode == 0, proc.stderr)
    staged = subprocess.run(["git", "diff", "--staged", "--name-only"], cwd=SANDBOX,
                            capture_output=True, text=True, encoding="utf-8").stdout.split()
    check("스테이징된 파일 2개", sorted(staged) == ["shop/pricing.py", "tests/test_pricing.py"], str(staged))
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=SANDBOX,
                            capture_output=True, text=True, encoding="utf-8").stdout.strip()
    check("브랜치 이름에 이슈 번호", branch == "fix/42-negative-price", branch)
    check(".opencode 가 sandbox 로 복사됨", (SANDBOX / ".opencode/skills/commit-message/SKILL.md").exists())

    with Sandbox("s1a") as sb:
        # 3. opencode 가 스킬을 발견하는가
        for label, cwd in (("예제 폴더", HERE), ("sandbox", SANDBOX)):
            skills = {s["name"]: s for s in sb.debug_skills(cwd=cwd, extra_env=pwd(cwd))}
            check(f"debug skill 에 commit-message 표시 ({label})",
                  "commit-message" in skills and str(cwd) in skills["commit-message"]["location"])
        desc = skills["commit-message"]["description"]
        check("description 에 한국어 트리거 문구", "커밋 메시지 작성해줘" in desc, desc)

        # 4. 모델: 스킬 로드 + 형식 준수
        # 3-1. 가짜 LLM: 모델이 무엇을 받는지 (모델 없이, 항상 같은 결과)
        llm, reqs = run_fake(sb, SANDBOX, [("tool", "skill", {"name": "commit-message"}), "DONE"])
        check("가짜 LLM: 두 번의 요청이 오고 스킬 도구 호출이 처리됨", len(reqs) == 2, str(len(reqs)))
        if len(reqs) == 2:
            sysmsg = system_text(llm, reqs[0])
            check("모델의 시스템 프롬프트 <available_skills> 에 이름과 한국어 description 이 있음",
                  "<name>commit-message</name>" in sysmsg and "커밋 메시지 작성해줘" in sysmsg)
            check("본문(규칙 전체)은 스킬을 불러오기 전에는 시스템 프롬프트에 없음", "허용 type" not in sysmsg)
            body = "\n".join(tool_texts(llm, reqs[1]))
            check("스킬을 불러오면 도구 결과로 본문이 전달됨", '<skill_content name="commit-message">' in body and "허용 type" in body)

        if model_enabled():
            out = sb.run_model("스테이징된 변경으로 커밋 메시지 작성해줘", cwd=SANDBOX, extra_env=pwd(SANDBOX), timeout=240)
            model_check("모델이 commit-message 스킬을 불러옴", out, skill_loaded(out, "commit-message"))
            m = LINE_WITH_DECOR.search(out)
            model_check("출력에 컨벤션 정규식에 맞는 1행이 있음", out, bool(m))
            # 시드 커밋은 컨벤션이 아니므로, 맞는 1행이 있다면 스킬 덕분이다.
            model_check("fix 타입이고 브랜치에서 찾은 Refs: #42 가 있음", out,
                        bool(m) and m.group(2) == "fix" and re.search(r"^[\s>*`\-]*Refs: #42\b", out, re.M) is not None)
            model_check("git commit 을 멋대로 실행하지 않음", out,
                        subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=SANDBOX, capture_output=True,
                                       text=True, encoding="utf-8").stdout.strip() == "1")
finally:
    shutil.rmtree(SANDBOX, onerror=_force_remove) if SANDBOX.exists() else None
    stray = HERE / ".opencode" / ".gitignore"
    if stray.exists() and not had_oc_gitignore:
        stray.unlink()  # opencode 가 자동으로 만든 파일
    for name in ("node_modules", "package.json", "package-lock.json", "bun.lock"):
        p = HERE / ".opencode" / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()

finish()
