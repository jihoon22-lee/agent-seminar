# S1a 커밋 메시지 스킬

> 구성: SKILL.md 한 장(스크립트 없음) | 난이도: ★☆☆ | 필요: opencode 1.19.5, Python 3.10+, git | 슬라이드: 스킬 — 가장 단순한 형태

## 무엇을 보여 주나

스킬은 `SKILL.md` 파일 한 장만으로 만들 수 있다. 이 예제는 "우리 팀 커밋 메시지는 이렇게 쓴다"는 규칙을 Markdown으로 적어 두고, 에이전트가 필요한 순간(커밋 메시지를 요청받았을 때)에만 그 규칙을 읽어 오게 한다.
규칙을 매번 프롬프트에 붙여 넣는 대신 한 번 적어 두면, 누가 요청하든 같은 형식의 메시지가 나온다.

## 실무에서는

- **새로 합류한 팀원 온보딩**: "커밋 규칙 문서를 읽어 오세요" 대신 저장소에 스킬을 넣어 두면, 문서를 읽지 않은 사람도 에이전트에게 메시지를 맡기는 것만으로 규칙을 지킨다.
- **리뷰어 부담 줄이기**: `fix: 수정`, `update`, `asdf` 같은 메시지를 리뷰 코멘트로 고쳐 달라고 요청하는 일이 줄어든다.
- **자동화와 연결**: 1행이 `type(scope): 요약` 형식이면 changelog·릴리스 노트 도구, `commitlint` 같은 훅이 그대로 동작한다. 스킬이 만든 메시지를 훅이 한 번 더 검사하는 구성이 흔하다.
- **이슈 추적**: 브랜치 이름(`fix/42-...`)에서 이슈 번호를 꺼내 `Refs: #42`를 붙이게 하면, 이슈와 커밋의 연결이 사람 손을 거치지 않는다.

## 파일 구성

```
s1a-commit-message/
├── README.md
├── check.py                                 자동 검증 (스킬 발견, 형식, 선택적으로 모델 실행)
├── fake_llm.py                              가짜 LLM 서버. check.py 가 모델 없이 opencode 의 요청을 기록·재현하는 데 씀
├── prepare.py                               실습용 git 저장소 sandbox/ 생성
└── .opencode/skills/commit-message/
    └── SKILL.md                             커밋 규칙 (frontmatter name/description + 본문)
```

`prepare.py`를 실행하면 생기는 `sandbox/`(git에는 올라가지 않음):

```
sandbox/
├── .git/                    커밋 1개 + 브랜치 fix/42-negative-price
├── .opencode/               위 .opencode 를 그대로 복사한 것
├── shop/pricing.py          [스테이징됨] 할인율 범위 검증 추가 (버그 수정)
└── tests/test_pricing.py    [스테이징됨] 새 테스트
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 아래 `opencode run`에 `-m opencode/big-pickle`(무료 모델)을 붙여 보세요.

1. 실습용 저장소를 만든다.

   PowerShell:
   ```powershell
   cd examples\01-skills\s1a-commit-message
   python prepare.py
   cd sandbox
   ```

   Linux bash (`python` 명령이 없으면 `python3`로 바꾸세요):
   ```bash
   cd examples/01-skills/s1a-commit-message
   python3 prepare.py
   cd sandbox
   ```

2. 스킬이 보이는지 확인한다.

   ```
   opencode debug skill
   ```

   JSON 목록에 `commit-message`가 있고 `location`이 `sandbox/.opencode/skills/commit-message/SKILL.md`를 가리키면 된다.
   (`customize-opencode`는 opencode에 내장된 스킬이다.)

3. opencode를 실행하고 프롬프트를 입력한다.

   ```
   opencode
   ```

   ```
   스테이징된 변경으로 커밋 메시지 작성해줘
   ```

   한 번에 실행하려면:

   ```
   opencode run "스테이징된 변경으로 커밋 메시지 작성해줘"
   opencode run -m opencode/big-pickle --auto "스테이징된 변경으로 커밋 메시지 작성해줘"
   ```

4. 메시지가 마음에 들면 직접 커밋한다. 스킬은 "커밋까지 해줘"라고 하지 않는 한 `git commit`을 실행하지 않는다.

## 기대 결과

`opencode run`으로 `opencode/big-pickle` 모델을 실행한 실제 출력이다(출력 앞부분이 최종 답변, 뒷부분이 도구 실행 기록이다. 모델 출력은 매번 조금씩 다르다).

````
```
fix(pricing): 할인율 범위 검증 추가

음수나 100 초과 할인율이 들어오면 음수 가격이나 잘못된 금액이 계산되던
문제를 막기 위해 percent 가 0~100 인지 확인하도록 했다.
경계값 검증을 테스트로 함께 추가했다.

Refs: #42
```

브랜치 `fix/42-negative-price`에서 이슈 번호 42를 가져왔습니다.


> build · big-pickle

→ Skill "commit-message"

$ git diff --staged
...(diff 생략)

$ git branch --show-current && git log -5 --oneline
fix/42-negative-price
bce49a9 initial pricing module
````

눈여겨볼 점은 세 가지다.

- `→ Skill "commit-message"`: 모델이 스킬을 불러왔다는 표시다.
- 1행이 `fix(...)`: 규칙의 type 표에 있는 값이다. 시드 커밋 메시지(`initial pricing module`)는 규칙을 따르지 않으므로, 형식이 맞는 것은 스킬 덕분이다.
- `Refs: #42`: 번호는 프롬프트에 없었다. 스킬 본문이 "브랜치 이름에서 찾아라"고 했기 때문에 모델이 `git branch --show-current`를 실행해 얻었다.

## 동작 원리

1. **발견**: opencode는 시작할 때 프로젝트의 `.opencode/skills/<이름>/SKILL.md`를 찾아 frontmatter의 `name`과 `description`만 읽는다. `opencode debug skill`이 보여 주는 목록이 이것이다. `description`이 없으면 모델에게 제시되지 않는다.
2. **제시**: 모델은 대화를 시작할 때 "사용 가능한 스킬 목록(이름 + description)"만 본다. 본문(규칙 전체)은 아직 보지 않는다. 그래서 `description`에 **무엇을 하는 스킬인지**와 **사용자가 실제로 칠 말**("커밋 메시지 작성해줘")을 같이 적어야 한다. 이 예제의 description에는 한국어 표현이 여러 개 들어 있다.
3. **로드**: 프롬프트가 description과 맞으면 모델이 내장 `skill` 도구를 호출해 본문을 읽는다. 실행 기록의 `→ Skill "commit-message"` 줄이 그 순간이다.
4. **실행**: 본문에 적힌 순서대로 모델이 `git diff --staged`, `git branch --show-current`, `git log`를 실행하고, 형식 규칙(type 표, 50자 제한, 꼬리말)에 맞춰 답을 쓴다.
5. **규칙 고정**: SKILL.md에는 1행 정규식이 적혀 있고, 이 예제의 `check.py`가 같은 정규식으로 모델 출력을 검사한다. "규칙을 말로만 쓰지 말고 검사할 수 있는 형태로 적어 두기"가 좋은 스킬 작성 요령이다.

## 직접 바꿔 보기

- `sandbox/.opencode/skills/commit-message/SKILL.md`(PowerShell 경로 `sandbox\.opencode\skills\commit-message\SKILL.md`)의 type 표에 `deps`(의존성 갱신)를 추가하고, 정규식에도 같은 값을 넣은 다음 `requirements.txt`를 수정해 스테이징하고 다시 요청해 보자. **예제 폴더의 원본 `.opencode/skills/...`를 고치면 아무것도 바뀌지 않는다.** 데모는 `sandbox/` 안의 사본으로 실행되기 때문이다. 원본을 고쳤다면 `prepare.py`를 다시 실행해 사본을 갱신한다(이때 sandbox/가 새로 만들어지므로 스테이징도 다시 한다).
- 꼬리말 규칙을 `Refs: #42` 대신 `Closes #42`로 바꾸고, 브랜치 이름을 `git branch -m feature/7-login`으로 바꿔 번호가 따라 바뀌는지 확인해 보자.
- (역시 sandbox 안의 사본에서) `description`에서 "커밋 메시지 작성해줘" 같은 문구를 전부 지우고(`팀 규칙` 같은 모호한 말만 남기고) 같은 프롬프트를 던져 보자. 스킬이 로드되는지 실행 기록의 `→ Skill` 줄로 확인하자. description이 왜 중요한지 확인하는 가장 빠른 방법이다.

## 주의할 점 / 문제 해결

- **`sandbox/`에서 실행해야 한다.** 이 저장소의 폴더에서 바로 `opencode`를 실행하면 상위의 세미나 저장소(git 루트)가 프로젝트로 잡히고, 스테이징된 변경도 없다. 모델이 "스테이징된 변경이 없습니다"라고 답한다면 위치를 의심하자.
- **`.opencode/`가 있는 폴더에서는** opencode가 시작할 때 `@opencode-ai/plugin`을 npm에서 설치하려 시도하고, 성공하면 `.opencode/` 안에 `package.json`, `node_modules/`, `.gitignore`가 생긴다(모두 git에서 제외). 이 예제에는 플러그인(`.opencode/plugins/*.js`)이 없어서, 레지스트리에 닿지 않는 환경에서도 눈에 띄는 멈춤은 없었다(연결을 거부하는 레지스트리로 측정: `opencode debug skill` 약 2초, `opencode run` 약 4초. TUI는 확인하지 못했다). 설치 시도 자체는 일어난다. 같은 환경에서 `.opencode/plugins/*.js`가 있는 폴더(P1~P8 등)는 시작할 때마다 약 70초 멈춘다(새 환경의 맨 처음 시작은 약 130초). 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있다.
- **`prepare.py`는 몇 번이든 다시 실행해도 된다.** `sandbox/`를 지우고 처음부터 만든다. Windows에서 `sandbox/`를 손으로 지울 때 `.git` 안의 파일이 읽기 전용이라 거부되면 `Remove-Item -Recurse -Force sandbox`를 쓴다.
- **Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요.** (`check.py`는 어느 쪽이든 동작한다.)
- **모델이 형식을 어길 때**: 요약이 50자를 넘거나 본문이 빠졌다면, 어긴 출력을 보여 주며 "SKILL.md의 규칙을 다시 읽고 고쳐줘"라고 하면 대개 고친다. 근본적인 해결은 규칙 문장을 더 구체적으로(예시와 함께) 쓰는 것이다.
