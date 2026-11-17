"""C6 데모: 같은 지시문을 명령과 스킬로 각각 두었을 때, 모델이 받는 요청에 무엇이 들어가는지 비교한다.

가짜 모델(fake_llm.py)을 쓰므로 인터넷도 계정도 필요 없고, 실제 ~/.config/opencode 도 건드리지 않는다.
    python demo.py         (Linux 에서 python 이 없으면 python3 demo.py)
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from lab import body_of, run_fake, skill_entry, system_text, user_texts  # noqa: E402
from octest import Sandbox  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

command_body = body_of((HERE / ".opencode/command/finish.md").read_text(encoding="utf-8")).strip()
skill_body = body_of((HERE / ".opencode/skills/finish-plan/SKILL.md").read_text(encoding="utf-8")).strip()
MARK = "PR 단위로 나눠서"  # 지시문 본문에만 있는 구절

with Sandbox("c6-demo") as sb:
    # 1) 명령도 스킬도 부르지 않고 평범하게 한 번 말을 건다
    _, llm, reqs = run_fake(sb, HERE, ["안녕"])
    sysmsg = system_text(llm, reqs[0])
    whole = str(reqs[0])  # 시스템 프롬프트, 사용자 메시지, 도구 정의 전부
    entry = skill_entry(sysmsg, "finish-plan")
    print("[1] 아무것도 부르지 않았을 때 모델이 받은 요청")
    print(f"    시스템 프롬프트 전체: {len(sysmsg)}자")
    nd = "".join(re.findall(r"<(?:name|description)>(.*?)</(?:name|description)>", entry, re.S))
    print(f"    스킬 finish-plan 항목: 이름+설명 {len(nd)}자 (파일 경로 <location> 까지 포함하면 {len(entry)}자, 경로는 설치 위치마다 다름)")
    print("      <- 이 항목은 어떤 요청에든 들어 있다")
    print(f"    스킬 본문 길이: {len(skill_body)}자  요청에 본문이 있는가: {skill_body[:30] in whole}")
    print(f"    명령 /finish 본문 길이: {len(command_body)}자  요청에 본문이 있는가: {command_body[:30] in whole}")
    print(f"    '{MARK}' 구절이 요청에 있는가: {MARK in whole}  (스킬 항목에도 없음)")
    print()

    # 2) 명령을 부른다
    _, llm, reqs = run_fake(sb, HERE, ["--command", "finish"])
    msgs = user_texts(llm, reqs[0])
    print("[2] opencode run --command finish 로 불렀을 때 모델이 받은 사용자 메시지")
    print(f"    사용자 메시지 {len(msgs)}개, 길이 {len(msgs[0])}자, 명령 본문과 같은가: {msgs[0].strip() == command_body}")
    print("    --- 받은 내용 ---")
    for line in msgs[0].splitlines():
        print("    " + line)
    print()

    # 3) 스킬은 모델이 고른다: 가짜 모델이 skill 도구를 부른 것처럼 흉내
    _, llm, reqs = run_fake(sb, HERE, ["계획대로 끝까지 진행해 줘"], script=[("tool", "skill", {"name": "finish-plan"}), "DONE"])
    tool_msgs = [llm.message_text(m) for m in reqs[1]["messages"] if m["role"] == "tool"]
    print("[3] 스킬은 모델이 skill 도구로 불러야 본문이 들어온다 (가짜 모델이 부른 것으로 흉내)")
    print(f"    두 번째 요청의 도구 결과에 본문이 있는가: {any(MARK in t for t in tool_msgs)}")
