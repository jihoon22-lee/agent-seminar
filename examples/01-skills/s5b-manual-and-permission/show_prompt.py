"""모델이 "처음부터" 보는 스킬 목록을 그대로 보여 줍니다 (모델·인터넷 불필요, 매번 같은 결과).

    python show_prompt.py            # 이 폴더의 프로젝트 기준
    python show_prompt.py <폴더>     # 다른 opencode 프로젝트 폴더 기준

원리: 127.0.0.1 에 가짜 모델 서버(mock_llm.py)를 띄우고 `opencode run -m mock/m hello` 를 한 번 실행합니다.
opencode 가 그 서버로 보낸 요청 본문에서 system 프롬프트의 <available_skills> 블록과 도구 목록을 꺼내 출력합니다.
Linux에서 `python` 명령이 없으면 `python3` 로 바꿔 실행하세요.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import lab
from mock_llm import mock_run


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    with lab.Sandbox() as sb:
        run = mock_run(sb, target, "hello")
    print(f"프로젝트 폴더: {target}")
    print(f"모델에게 간 도구: {', '.join(run.tool_names)}")
    m = re.search(r"Skills provide specialized.*?</available_skills>", run.system_prompt, re.S)
    print()
    print(m.group(0) if m else "(system 프롬프트에 스킬 목록이 없습니다)")
    print()
    print("스킬 본문은 위 블록에 없습니다. 모델이 skill 도구를 호출해야 비로소 본문이 대화에 들어옵니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
