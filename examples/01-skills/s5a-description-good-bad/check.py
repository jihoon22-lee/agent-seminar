"""s5a 검증: 같은 스킬 본문, 다른 description.

하드 체크(모델 없음): 두 변형 발견, 본문 동일, 모델 system 프롬프트에는 description 만 들어감(가짜 모델로 확인).
모델 체크(--model): good 변형에서 팀 용어 질문이 스킬을 여는지 1번 확인하고, bad 변형 결과는 참고용으로만 출력.
비율 비교는 compare.py 가 합니다 (check.py 에서는 하지 않음).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))

from octest import MODEL_UNAVAILABLE, RATE_LIMIT_RE, DEFAULT_MODEL, Sandbox, check, finish, model_check, model_enabled

import lab
from mock_llm import mock_run

BAD, GOOD = HERE / "variant-bad", HERE / "variant-good"


class Box:
    """octest.Sandbox 를 lab/mock_llm 이 기대하는 모양으로 감싼다 (opencode run 이 PWD 를 보기 때문에 PWD 를 맞춰 준다)."""

    def __init__(self, sb: Sandbox) -> None:
        self.sb, self.bin, self.env, self.root = sb, sb.bin, sb.env, sb.root

    def opencode(self, args, cwd, overlay=None, timeout=180, extra_env=None):
        return lab.run_opencode(self.bin, self.env, args, cwd, overlay=overlay, timeout=timeout,
                                extra_env=extra_env, scratch=self.root)


def only_glossary(sb: Sandbox, cwd: Path) -> list[dict]:
    return [s for s in sb.debug_skills(cwd) if s["name"] != "customize-opencode"]


def ask(box: Box, cwd: Path, prompt: str) -> str:
    out = lab.run_model(box, prompt, cwd, DEFAULT_MODEL)
    return MODEL_UNAVAILABLE + "\n" + out if (RATE_LIMIT_RE.search(out) or out.startswith("<<timeout>>")) else out


with Sandbox("s5a") as sb:
    box = Box(sb)
    bad, good = only_glossary(sb, BAD), only_glossary(sb, GOOD)

    check("variant-bad 에 team-glossary 하나만 보임", [s["name"] for s in bad] == ["team-glossary"], str(bad))
    check("variant-good 에 team-glossary 하나만 보임", [s["name"] for s in good] == ["team-glossary"], str(good))
    check("각 변형은 자기 폴더의 스킬을 봄 (형제 폴더끼리 섞이지 않음, 중첩 git init 불필요)",
          bad and good and "variant-bad" in bad[0]["location"] and "variant-good" in good[0]["location"])
    check("변형 폴더 안에 .git 이 없음 (저장소 안에 중첩 저장소를 만들지 않음)",
          not (BAD / ".git").exists() and not (GOOD / ".git").exists())
    check("두 변형의 스킬 본문은 완전히 같음", bad and good and bad[0]["content"] == good[0]["content"])
    bad_desc, good_desc = bad[0]["description"], good[0]["description"]
    check("bad description 은 짧고 막연함 ('도움' 뿐, 트리거 말 없음)",
          "도움" in bad_desc and len(bad_desc) < 30 and not any(w in bad_desc for w in ("용어", "약어", "뭐야")), bad_desc)
    check("good description 은 무엇(용어 사전)과 언제(팀 용어/약어/뭐야)를 함께 말함",
          all(w in good_desc for w in ("용어", "약어", "~가 뭐야", "사용한다")), good_desc)

    # 가짜 모델로 "모델이 처음부터 받는 것"을 확인
    run_bad = mock_run(box, BAD, "hello")
    run_good = mock_run(box, GOOD, "hello")
    for tag, run, desc in (("bad", run_bad, bad_desc), ("good", run_good, good_desc)):
        check(f"{tag}: system 프롬프트에 team-glossary 의 description 이 그대로 들어 있음",
              f"<description>{desc}</description>" in run.system_prompt)
        check(f"{tag}: system 프롬프트에 스킬 본문은 없음 (이름·description·위치뿐)", "TEAM-GLOSSARY-BODY" not in run.system_prompt)
    loaded = mock_run(box, GOOD, "[[skill:team-glossary]] 블루문이 뭐야?")
    check("skill 도구를 호출해야 비로소 본문이 대화에 들어옴",
          loaded.skill_loaded("team-glossary") and "TEAM-GLOSSARY-BODY" in loaded.tool_result, loaded.tool_result)

    # 실제 모델 (선택): 같은 프롬프트를 두 변형에 한 번씩
    if model_enabled():
        prompt = "우리 팀에서 쓰는 '블루문'이 정확히 뭐야?"
        out_good = ask(box, GOOD, prompt)
        model_check("실제 모델: good description 이면 팀 용어 질문에서 team-glossary 를 엶",
                    out_good, 'Skill "team-glossary"' in out_good)
        out_bad = ask(box, BAD, prompt)
        if not out_bad.startswith(MODEL_UNAVAILABLE):
            opened = 'Skill "team-glossary"' in out_bad
            print(f"[INFO] 참고용: bad description 에서는 같은 질문에 스킬을 {'열었음' if opened else '열지 않았음'}"
                  " (비율은 compare.py 로 여러 번 재야 의미가 있음)")
# octest.Sandbox 는 Windows 에서 읽기 전용 git 객체 파일을 못 지우고 폴더를 남기므로 한 번 더 정리한다
lab.rmtree_force(sb.root)
finish()
