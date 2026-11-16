"""s2a 검증: 스킬 발견, 보조 파일 구성 + (선택) 모델이 TEMPLATE.md 는 읽고 EXAMPLES.md 는 필요할 때만 읽는지."""
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
SKILL_DIR = HERE / ".opencode" / "skills" / "workthrough"
SANDBOX = HERE / "sandbox"
OC = HERE / ".opencode"
PY = sys.executable
had_oc_gitignore = (OC / ".gitignore").exists()


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


def _force_remove(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)  # Windows: .git 안의 읽기 전용 파일
    func(path)


def prepare() -> bool:
    proc = subprocess.run([PY, str(HERE / "prepare.py")], capture_output=True, text=True, encoding="utf-8")
    return proc.returncode == 0


def read_markers(out: str, filename: str) -> bool:
    """실행 기록에 `→ Read .../filename` 줄이 있는가."""
    return any(line.lstrip().startswith("→ Read") and filename in line for line in out.splitlines())


try:
    # 1. 파일 구성
    for name in ("SKILL.md", "TEMPLATE.md", "EXAMPLES.md", "LICENSE.txt", "NOTICE.md"):
        check(f"{name} 존재", (SKILL_DIR / name).exists())
    lic = (SKILL_DIR / "LICENSE.txt").read_text(encoding="utf-8")
    check("LICENSE.txt 는 MIT 전문", lic.startswith("MIT License") and "Permission is hereby granted" in lic)
    skill_md = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    sizes = {n: len((SKILL_DIR / n).read_bytes()) for n in ("SKILL.md", "TEMPLATE.md", "EXAMPLES.md")}
    check(f"SKILL.md 가 보조 파일(TEMPLATE+EXAMPLES)보다 작음 {sizes}",
          sizes["SKILL.md"] < sizes["TEMPLATE.md"] + sizes["EXAMPLES.md"])
    check("SKILL.md 가 두 보조 파일을 읽는 조건과 함께 언급",
          "TEMPLATE.md" in skill_md and "EXAMPLES.md" in skill_md and "only if" in skill_md)
    other_tools = ["Clau" + "de", "Cur" + "sor", "Co" + "dex"]  # 다른 에이전트 전용 표현이 남아 있지 않은지
    check("SKILL.md 에 다른 도구 이름이 없음", not any(name in skill_md for name in other_tools))

    # 2. 샘플 프로젝트
    check("prepare.py 실행", prepare())
    status = subprocess.run(["git", "status", "--short"], cwd=SANDBOX, capture_output=True,
                            text=True, encoding="utf-8").stdout.split("\n")
    changed = sorted(l[3:] for l in status if l.strip())
    check("커밋하지 않은 변경 2개", changed == ["tests/test_store.py", "todo/store.py"], str(changed))
    tests = subprocess.run([PY, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=SANDBOX,
                           capture_output=True, text=True, encoding="utf-8")
    check("수정 후 샘플 테스트가 통과", tests.returncode == 0, tests.stderr)
    shutil.rmtree(SANDBOX, onerror=_force_remove)

    with Sandbox("s2a") as sb:
        skills = {s["name"]: s for s in sb.debug_skills(cwd=HERE, extra_env=pwd(HERE))}
        check("debug skill 에 workthrough 표시", "workthrough" in skills)
        desc = skills["workthrough"]["description"]
        check("description 에 한국어 트리거 문구", "workthrough로 기록해줘" in desc, desc)
        check("본문(content)에는 TEMPLATE 의 'Issues Encountered' 절이 없음 (보조 파일은 로드 전)",
              "Issues Encountered" not in skills["workthrough"]["content"])

        template_path = SKILL_DIR / "TEMPLATE.md"
        llm, reqs = run_fake(sb, HERE, [("tool", "skill", {"name": "workthrough"}),
                                        ("tool", "read", {"filePath": str(template_path)}), "DONE"])
        check("가짜 LLM: 스킬 로드 + read 호출까지 3번의 요청", len(reqs) == 3, str(len(reqs)))
        if len(reqs) == 3:
            sysmsg = system_text(llm, reqs[0])
            check("시스템 프롬프트에는 workthrough 의 이름과 description 만 있음",
                  "<name>workthrough</name>" in sysmsg and "Supporting Files" not in sysmsg)
            loaded = "\n".join(tool_texts(llm, reqs[1]))
            check("스킬 로드 결과: SKILL.md 본문 + 보조 파일 목록(<skill_files>)",
                  "Supporting Files" in loaded and "TEMPLATE.md</file>" in loaded and "EXAMPLES.md</file>" in loaded)
            check("스킬 로드 결과에 TEMPLATE/EXAMPLES 의 내용은 없음 (읽기 전까지 컨텍스트에 안 올라옴)",
                  "Issues Encountered" not in loaded and "Example 2: Feature Implementation" not in loaded)
            after_read = "\n".join(tool_texts(llm, reqs[2]))
            check("read 로 TEMPLATE.md 를 읽으면 그때 내용이 들어옴", "Issues Encountered" in after_read)

        if model_enabled():
            # 2-1. 단순 요청: SKILL.md + TEMPLATE.md 만
            check("prepare.py (모델 실행용)", prepare())
            out = sb.run_model("이 변경 작업을 workthrough로 기록해줘", cwd=SANDBOX, extra_env=pwd(SANDBOX), timeout=240)
            model_check("모델이 workthrough 스킬을 불러옴", out, skill_loaded(out, "workthrough"))
            docs = sorted((SANDBOX / "workthrough").glob("*.md")) if (SANDBOX / "workthrough").exists() else []
            model_check(f"workthrough/YYYY-MM-DD-*.md 가 만들어짐 ({[d.name for d in docs]})", out,
                        any(re.fullmatch(r"\d{4}-\d\d-\d\d-.+\.md", d.name) for d in docs))
            if docs:
                text = docs[0].read_text(encoding="utf-8")
                model_check("문서에 Overview / Changes Made / Verification 섹션", out,
                            all(re.search(rf"^#+ .*{h}", text, re.M | re.I) for h in ("Overview", "Changes Made", "Verification")))
                model_check("문서가 실제 변경(number - 1)을 언급", out, "number - 1" in text or "number-1" in text)
            model_check("TEMPLATE.md 를 읽음 (보조 파일 로드)", out, read_markers(out, "TEMPLATE.md"))
            model_check("EXAMPLES.md 는 읽지 않음 (필요 없으면 안 읽는다)", out, not read_markers(out, "EXAMPLES.md"))

            # 2-2. 예시를 요청하면 EXAMPLES.md 까지
            check("prepare.py (두 번째 실행용)", prepare())
            out2 = sb.run_model("이 변경 작업을 workthrough로 기록해줘. 작성 예시 문서를 참고해서 비슷한 수준으로 써줘.",
                                cwd=SANDBOX, extra_env=pwd(SANDBOX), timeout=240)
            model_check("예시를 요청하면 EXAMPLES.md 도 읽음", out2, read_markers(out2, "EXAMPLES.md"))
finally:
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX, onerror=_force_remove)
    if not had_oc_gitignore and (OC / ".gitignore").exists():
        (OC / ".gitignore").unlink()
    for name in ("node_modules", "package.json", "package-lock.json", "bun.lock"):
        p = OC / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()

finish()
