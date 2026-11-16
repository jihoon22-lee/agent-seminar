# 출처와 변경 사항

이 스킬은 작성자가 실제 개발에서 매일 쓰는 `workthrough` 스킬(MIT 라이선스)을 opencode용으로 옮긴 것이다.
저작권 고지와 라이선스 전문은 `LICENSE.txt`에 그대로 두었다.

원본에서 바꾼 부분(이 세미나 자료에 맞추기 위한 최소한의 변경):

1. `SKILL.md`의 `description` 끝에 한국어 요청 문구를 덧붙였다. 원문 영어 문장은 그대로다.
2. `SKILL.md`에 들어 있던 "Example Workthrough Structure" 블록(약 50줄)을 지우고, `TEMPLATE.md`와 `EXAMPLES.md`를 **언제** 읽을지 적은 "Supporting Files" 절로 바꿨다. 원본 `SKILL.md`는 두 파일을 언급하지 않아서, 모델이 파일 이름은 볼 수 있어도 언제 읽어야 하는지는 알 방법이 없었다.
3. "세션이 끝날 때 자동으로 실행된다"는 문장을 "사용자가 기록을 요청하거나 작업을 마친 직후에 불러온다"로 바꿨다. opencode에는 세션 종료 시점의 자동 실행이 없고, 스킬은 모델이 description을 보고 고른다.
4. `TEMPLATE.md`, `EXAMPLES.md`, `LICENSE.txt`는 원본과 동일하다. 원본의 `README.md`와 `QUICKSTART.md`는 다른 도구 기준의 안내문이라 가져오지 않았다.

이 파일은 모델이 읽을 필요가 없으므로 `SKILL.md`에서 언급하지 않는다.
