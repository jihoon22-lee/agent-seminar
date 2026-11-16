"""두 변형에서 "모델이 처음부터 보는 것"을 나란히 보여 줍니다 (모델·인터넷 불필요, 매번 같은 결과).

    python show_prompt.py

127.0.0.1 에 가짜 모델 서버(mock_llm.py)를 띄우고 변형 폴더마다 `opencode run -m mock/m hello` 를 한 번씩 실행합니다.
opencode 가 그 서버로 보낸 요청의 system 프롬프트에서 <available_skills> 블록만 꺼내 출력합니다.
Linux에서 `python` 명령이 없으면 `python3` 로 바꿔 실행하세요.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import lab
from mock_llm import mock_run

HERE = Path(__file__).resolve().parent


def main() -> int:
    with lab.Sandbox() as sb:
        for variant in ("variant-bad", "variant-good"):
            run = mock_run(sb, HERE / variant, "hello")
            block = re.search(r"<skill>\s*<name>team-glossary</name>.*?</skill>", run.system_prompt, re.S)
            print(f"===== {variant}: 모델의 system 프롬프트 속 team-glossary 항목")
            print(block.group(0).replace(str(HERE), "<예제 폴더>") if block else "(없음)")
            print(f"  → 본문('TEAM-GLOSSARY-BODY')이 system 프롬프트에 들어 있는가: {'TEAM-GLOSSARY-BODY' in run.system_prompt}")
            print()
        print("두 변형은 본문이 완전히 같고 description 한 줄만 다릅니다. 모델이 '이 스킬을 열어 볼지'를")
        print("판단하는 재료는 위 항목(이름 + description + 위치)이 전부입니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
