"""s2c 검증: 스킬·템플릿·예시 구성 + (선택) 모델이 기존 번호를 보고 0002 로 ADR 을 만드는지."""
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
SKILL_DIR = HERE / ".opencode" / "skills" / "adr"
SANDBOX = HERE / "sandbox"
OC = HERE / ".opencode"
PY = sys.executable
had_oc_gitignore = (OC / ".gitignore").exists()
SECTIONS = ("맥락", "결정", "대안", "결과")


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


def read_marker(out: str, filename: str) -> bool:
    return any(line.lstrip().startswith("→ Read") and filename in line for line in out.splitlines())


try:
    template = (SKILL_DIR / "templates" / "adr-template.md").read_text(encoding="utf-8")
    check("템플릿에 네 섹션", all(re.search(rf"^## {s}", template, re.M) for s in SECTIONS))
    examples = sorted((SKILL_DIR / "examples").glob("0001-*.md"))
    check("examples/0001-*.md 가 하나 있음", len(examples) == 1)
    if examples:
        ex = examples[0].read_text(encoding="utf-8")
        check("예시가 템플릿 구조를 따름", all(re.search(rf"^## {s}", ex, re.M) for s in SECTIONS)
              and ex.startswith("# 0001. "))
    skill_md = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    check("SKILL.md 가 템플릿·예시 경로와 docs/adr/NNNN-<slug>.md 를 언급",
          all(k in skill_md for k in ("templates/adr-template.md", "examples/0001-", "docs/adr/NNNN-<slug>.md")))
    check("example 의 .gitignore 가 docs/adr/ 를 무시", "docs/adr/" in (HERE / ".gitignore").read_text(encoding="utf-8").split())
    git = shutil.which("git")
    if git:
        probe = subprocess.run([git, "check-ignore", "-q", "docs/adr/0002-x.md"], cwd=HERE)
        check("git check-ignore: docs/adr/ 아래 생성물은 무시됨", probe.returncode == 0)

    proc = subprocess.run([PY, str(HERE / "prepare.py")], capture_output=True, text=True, encoding="utf-8")
    check("prepare.py 실행", proc.returncode == 0, proc.stderr)
    check("sandbox/docs/adr/ 에 0001 하나", [p.name for p in (SANDBOX / "docs" / "adr").glob("*.md")]
          == ["0001-use-postgresql-for-order-store.md"])

    with Sandbox("s2c") as sb:
        for label, cwd in (("예제 폴더", HERE), ("sandbox", SANDBOX)):
            skills = {s["name"]: s for s in sb.debug_skills(cwd=cwd, extra_env=pwd(cwd))}
            check(f"debug skill 에 adr 표시 ({label})", "adr" in skills and str(cwd) in skills["adr"]["location"])
        desc = skills["adr"]["description"]
        check("description 에 한국어 트리거 문구", "ADR로 남겨줘" in desc, desc)

        tpl_path = SKILL_DIR / "templates" / "adr-template.md"
        llm, reqs = run_fake(sb, SANDBOX, [("tool", "skill", {"name": "adr"}),
                                           ("tool", "read", {"filePath": str(tpl_path)}), "DONE"])
        check("가짜 LLM: 스킬 로드 + read 호출까지 3번의 요청", len(reqs) == 3, str(len(reqs)))
        if len(reqs) == 3:
            sysmsg = system_text(llm, reqs[0])
            check("시스템 프롬프트에 이름과 description 만 있음", "<name>adr</name>" in sysmsg and "나쁜 점" not in sysmsg)
            loaded = "\n".join(tool_texts(llm, reqs[1]))
            check("스킬 로드 결과: 본문 + templates/ · examples/ 파일 목록",
                  "adr-template.md</file>" in loaded and "0001-use-postgresql-for-order-store.md</file>" in loaded)
            check("템플릿을 read 하면 양식이 전달됨", "## 맥락" in "\n".join(tool_texts(llm, reqs[2])))

        if model_enabled():
            out = sb.run_model("메시지 큐로 Kafka 대신 RabbitMQ를 쓰기로 한 결정을 ADR로 남겨줘",
                               cwd=SANDBOX, extra_env=pwd(SANDBOX), timeout=240)
            model_check("모델이 adr 스킬을 불러옴", out, skill_loaded(out, "adr"))
            files = sorted(p.name for p in (SANDBOX / "docs" / "adr").glob("*.md"))
            new = [f for f in files if f != "0001-use-postgresql-for-order-store.md"]
            model_check(f"docs/adr/0002-<slug>.md 가 만들어짐 ({files})", out,
                        len(new) == 1 and re.fullmatch(r"0002-[a-z0-9]+(-[a-z0-9]+)*\.md", new[0]) is not None)
            if new:
                doc = (SANDBOX / "docs" / "adr" / new[0]).read_text(encoding="utf-8")
                model_check("제목 줄이 '# 0002. ' 로 시작", out, doc.startswith("# 0002. "))
                model_check("템플릿의 네 섹션이 모두 있음", out, all(re.search(rf"^## {s}", doc, re.M) for s in SECTIONS))
                model_check("RabbitMQ 와 Kafka 가 모두 등장", out, "RabbitMQ" in doc and "Kafka" in doc)
                model_check("상태 Accepted 와 날짜 형식", out,
                            re.search(r"^- 상태: Accepted", doc, re.M) is not None
                            and re.search(r"^- 날짜: \d{4}-\d\d-\d\d$", doc, re.M) is not None)
                model_check("'나쁜 점' 이 비어 있지 않음", out,
                            re.search(r"### 나쁜 점·감수할 것\s*\n+\s*- \S", doc) is not None)
            old = (SANDBOX / "docs" / "adr" / "0001-use-postgresql-for-order-store.md").read_text(encoding="utf-8")
            model_check("기존 0001 은 수정되지 않음", out, old == examples[0].read_text(encoding="utf-8"))
            model_check("템플릿을 읽음 (→ Read 기록)", out, read_marker(out, "adr-template.md"))
            model_check("docs/adr 에 이미 ADR 이 있으므로 예시 파일은 읽지 않음", out, not read_marker(out, "0001-use-postgresql"))
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
