"""s1c 검증: 스킬 발견, 노트·.gitignore 점검 + (선택) 모델이 노트로 포스트모템 파일을 만드는지."""
import json
import os
import re
import shutil
import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, skill_loaded  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402  (이 폴더의 복사본)
OC = HERE / ".opencode"
OUT = HERE / "postmortems"
had_oc_gitignore = (OC / ".gitignore").exists()
had_out = OUT.exists()


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


try:
    notes = (HERE / "notes" / "incident-notes.md").read_text(encoding="utf-8")
    check("노트에 사건 날짜가 있음", "2026-08-14" in notes)
    check("노트에 담당 미정 항목이 있음 (모델이 지어내지 않는지 볼 수 있음)", "담당 미정" in notes)
    check("example 의 .gitignore 가 postmortems/ 를 무시",
          "postmortems/" in (HERE / ".gitignore").read_text(encoding="utf-8").split())

    git = shutil.which("git")
    if git:
        probe = subprocess.run([git, "check-ignore", "-q", "postmortems/2026-08-14-x.md"], cwd=HERE)
        check("git check-ignore: postmortems/ 아래 파일은 무시됨", probe.returncode == 0)

    with Sandbox("s1c") as sb:
        skills = {s["name"]: s for s in sb.debug_skills(cwd=HERE, extra_env=pwd(HERE))}
        check("debug skill 에 postmortem 표시", "postmortem" in skills)
        desc = skills["postmortem"]["description"]
        check("description 에 한국어 트리거 문구", "포스트모템 써줘" in desc, desc)
        body = skills["postmortem"]["content"]
        check("본문에 대화형/문서 모드와 저장 경로 규칙이 있음",
              all(k in body for k in ("대화형 모드", "문서 모드", "postmortems/YYYY-MM-DD-<slug>.md", "한 번에 질문 하나")))

        llm, reqs = run_fake(sb, HERE, [("tool", "skill", {"name": "postmortem"}), "DONE"])
        check("가짜 LLM: 스킬 도구 호출이 처리됨", len(reqs) == 2, str(len(reqs)))
        if len(reqs) == 2:
            sysmsg = system_text(llm, reqs[0])
            check("시스템 프롬프트에 이름과 한국어 description 이 있고 모드 규칙 본문은 없음",
                  "<name>postmortem</name>" in sysmsg and "포스트모템 써줘" in sysmsg and "한 번에 질문 하나" not in sysmsg)
            body = "\n".join(tool_texts(llm, reqs[1]))
            check("스킬을 불러오면 두 모드와 저장 규칙이 전달됨", "대화형 모드" in body and "postmortems/YYYY-MM-DD-<slug>.md" in body)

        if model_enabled():
            out = sb.run_model("notes/incident-notes.md 로 포스트모템 작성해줘", cwd=HERE, extra_env=pwd(HERE), timeout=240)
            model_check("모델이 postmortem 스킬을 불러옴", out, skill_loaded(out, "postmortem"))
            files = sorted(OUT.glob("*.md")) if OUT.exists() else []
            good = [f for f in files if re.fullmatch(r"2026-08-14-[a-z0-9]+(-[a-z0-9]+)*\.md", f.name)]
            model_check(f"postmortems/2026-08-14-<slug>.md 가 만들어짐 ({[f.name for f in files]})", out, len(good) == 1)
            if good:
                doc = good[0].read_text(encoding="utf-8")
                for heading in ("영향", "타임라인", "근본 원인", "잘된 점", "아쉬운 점", "액션 아이템"):
                    model_check(f"문서에 '{heading}' 섹션", out, re.search(rf"^#+ .*{heading}", doc, re.M) is not None)
                model_check("5 whys 가 3단계 이상 (번호 목록의 '왜')", out,
                            len(re.findall(r"^\s*\d+\.\s*왜", doc, re.M)) >= 3)
                dates = re.findall(r"\b20\d\d-\d\d-\d\d\b", doc.split("액션 아이템")[-1])
                model_check(f"액션 아이템 구역에 기한(YYYY-MM-DD) 3개 이상 ({len(dates)}개)", out, len(dates) >= 3)
                model_check("담당 미정 항목을 지어내지 않고 표시함 (확인 필요/미정)", out,
                            re.search(r"확인 필요|미정|TBD", doc.split("액션 아이템")[-1]) is not None)
                model_check("노트 사실 반영: 4,200건과 15:26 복구", out, "4,200" in doc or "4200" in doc)
finally:
    if not had_out and OUT.exists():
        shutil.rmtree(OUT, ignore_errors=True)
    if not had_oc_gitignore and (OC / ".gitignore").exists():
        (OC / ".gitignore").unlink()
    for name in ("node_modules", "package.json", "package-lock.json", "bun.lock"):
        p = OC / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()

finish()
