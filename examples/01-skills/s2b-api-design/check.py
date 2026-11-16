"""s2b 검증: 라우터형 SKILL.md + references/ 구성 + (선택) 모델이 pagination.md 를 읽고 그 규칙을 적용하는지."""
import json
import re
import shutil
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, skill_loaded  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402  (이 폴더의 복사본)
SKILL_DIR = HERE / ".opencode" / "skills" / "api-design"
OC = HERE / ".opencode"
had_oc_gitignore = (OC / ".gitignore").exists()
REFS = ("naming", "errors", "pagination", "versioning", "auth")

# 이 값들은 pagination.md 에만 있다. 모델의 일반 상식에서는 나오기 어려운 조합이다.
SECRET_RULE = "pg1_"


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


def read_marker(out: str, filename: str) -> bool:
    return any(line.lstrip().startswith("→ Read") and filename in line for line in out.splitlines())


try:
    skill_md = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for ref in REFS:
        path = SKILL_DIR / "references" / f"{ref}.md"
        check(f"references/{ref}.md 존재", path.exists())
        check(f"SKILL.md 가 references/{ref}.md 를 읽을 조건과 함께 언급",
              re.search(rf"\|[^|\n]+\|\s*`references/{ref}\.md`\s*\|", skill_md) is not None)
    pg = (SKILL_DIR / "references" / "pagination.md").read_text(encoding="utf-8")
    check("pagination.md 에 검사 가능한 규칙 (next_cursor, pg1_, 최대 100, 기본 25)",
          all(k in pg for k in ("next_cursor", SECRET_RULE, "**100**", "**25**")))
    check("규칙 값이 SKILL.md 본문에는 없음 (reference 를 읽어야만 알 수 있음)",
          SECRET_RULE not in skill_md and "next_cursor" not in skill_md)

    with Sandbox("s2b") as sb:
        skills = {s["name"]: s for s in sb.debug_skills(cwd=HERE, extra_env=pwd(HERE))}
        check("debug skill 에 api-design 표시", "api-design" in skills)
        desc = skills["api-design"]["description"]
        check("description 에 한국어 트리거 문구", "API 설계해줘" in desc, desc)
        check("debug skill 의 content 에도 pg1_ 가 없음", SECRET_RULE not in skills["api-design"]["content"])

        pg_path = SKILL_DIR / "references" / "pagination.md"
        llm, reqs = run_fake(sb, HERE, [("tool", "skill", {"name": "api-design"}),
                                        ("tool", "read", {"filePath": str(pg_path)}), "DONE"])
        check("가짜 LLM: 스킬 로드 + read 호출까지 3번의 요청", len(reqs) == 3, str(len(reqs)))
        if len(reqs) == 3:
            sysmsg = system_text(llm, reqs[0])
            check("시스템 프롬프트에 규칙 값(pg1_)이 없음", SECRET_RULE not in sysmsg and "<name>api-design</name>" in sysmsg)
            loaded = "\n".join(tool_texts(llm, reqs[1]))
            check("스킬 로드 결과: 라우팅 표 + references/ 파일 목록, 규칙 값은 아직 없음",
                  "references/pagination.md" in loaded and "pagination.md</file>" in loaded and SECRET_RULE not in loaded)
            check("pagination.md 를 read 한 뒤에야 pg1_ 가 모델에게 전달됨",
                  SECRET_RULE in "\n".join(tool_texts(llm, reqs[2])))

        if model_enabled():
            out = sb.run_model("주문 목록 조회 API 설계해줘 (페이지네이션 포함)", cwd=HERE, extra_env=pwd(HERE), timeout=240)
            model_check("모델이 api-design 스킬을 불러옴", out, skill_loaded(out, "api-design"))
            model_check("references/pagination.md 를 읽음 (→ Read 기록)", out, read_marker(out, "pagination.md"))
            model_check("naming.md 도 읽음 (모든 설계에서 먼저)", out, read_marker(out, "naming.md"))
            model_check("답변에 next_cursor 와 pg1_ 접두사 (규칙 적용)", out, "next_cursor" in out and SECRET_RULE in out)
            model_check("limit 기본 25 / 최대 100", out, re.search(r"\b25\b", out) is not None and re.search(r"\b100\b", out) is not None)
            model_check("offset/page 방식을 쓰지 않음", out, not re.search(r"[?&](offset|page|per_page)=", out))
            model_check("목록을 items 에 담음", out, '"items"' in out)
            skipped = [f for f in ("auth.md", "versioning.md") if not read_marker(out, f)]
            model_check(f"관련 없는 reference 는 읽지 않음 (안 읽은 것: {skipped})", out, len(skipped) == 2)
finally:
    if not had_oc_gitignore and (OC / ".gitignore").exists():
        (OC / ".gitignore").unlink()
    for name in ("node_modules", "package.json", "package-lock.json", "bun.lock"):
        p = OC / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()

finish()
