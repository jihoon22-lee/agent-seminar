# S2a workthrough: 보조 파일을 필요할 때만 읽는 실제 스킬

> 구성: SKILL.md + TEMPLATE.md + EXAMPLES.md + LICENSE.txt | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, git | 슬라이드: 스킬 — 점진적 공개(progressive disclosure)

## 무엇을 보여 주나

이 스킬은 예제용으로 만든 것이 아니라 작성자가 **실제로 매일 쓰는** `workthrough`(작업 기록 문서 작성 스킬, MIT 라이선스)를 opencode용으로 옮긴 것이다.
여기서 보려는 것은 **점진적 공개**다. 스킬 폴더에는 파일이 네 개 있지만, 에이전트는 먼저 `SKILL.md`(149줄)만 읽고, 빈 양식 `TEMPLATE.md`(118줄)는 문서를 쓰기 직전에, 완성 예시 `EXAMPLES.md`(405줄)는 사용자가 예시를 원할 때만 읽는다. 쓰지 않을 내용을 대화에 올리지 않는 것이 핵심이다.

## 실무에서는

- **작업 기록을 남기는 습관**: 버그 수정이나 기능 구현이 끝난 뒤 "이 변경 작업을 workthrough로 기록해줘" 한 줄로 변경 파일, 코드 조각, 검증 결과(테스트 출력)가 담긴 문서가 만들어진다. 작성자는 이 문서를 PR 설명, 인수인계, 같은 문제가 다시 생겼을 때의 검색 대상으로 쓴다.
- **팀 온보딩**: 신규 팀원이 "예전에 이 모듈을 왜 이렇게 바꿨지?"를 `workthrough/` 폴더의 날짜순 문서로 따라갈 수 있다.
- **긴 참고 자료를 가진 스킬 설계의 본보기**: 양식, 예시, 용어집처럼 길지만 가끔만 필요한 자료는 별도 파일로 빼고, `SKILL.md`에서 "언제 읽을지"만 적는다. 팀 위키를 스킬로 옮길 때 그대로 쓰는 패턴이다.
- **오픈소스 스킬을 가져다 쓰는 법**: 이 예제처럼 라이선스 파일을 그대로 두고, 바꾼 점을 `NOTICE.md`에 적어 두면 다음 사람이 원본과의 차이를 알 수 있다.

## 왜 파일을 나누면 컨텍스트가 절약되나

모델이 한 번에 볼 수 있는 대화 길이(컨텍스트)는 한정되어 있고, 읽은 내용은 그 대화가 끝날 때까지 계속 자리를 차지한다.

| 파일 | 크기 | 언제 컨텍스트에 올라오나 |
| --- | --- | --- |
| `description` (SKILL.md 머리말) | 약 1KB | 항상. 스킬 목록의 한 줄로 |
| `SKILL.md` 본문 | 5.0KB, 149줄 | 스킬이 선택되었을 때 |
| `TEMPLATE.md` | 2.5KB, 118줄 | 문서를 쓰기 직전 |
| `EXAMPLES.md` | 11.8KB, 405줄 | 사용자가 예시를 원할 때만 |

모든 내용을 `SKILL.md` 하나에 넣었다면 기록을 요청할 때마다 약 19KB가 올라온다. 나누면 보통은 약 7.6KB(`SKILL.md` + `TEMPLATE.md`)면 된다. 예시를 읽은 대화는 그만큼 커지지만, 그 부담은 예시가 필요한 대화만 진다.
스킬이 많아질수록 차이가 커진다. 스킬 열 개가 각각 20KB짜리 자료를 가진다고 해도, 이 구조라면 평소 대화에는 열 개의 description(각 1KB 안팎)만 올라온다.

## 파일 구성

```
s2a-workthrough/
├── README.md
├── check.py                               자동 검증
├── prepare.py                             샘플 프로젝트 sandbox/ 생성 (커밋 1개 + 아직 커밋하지 않은 버그 수정)
└── .opencode/skills/workthrough/
    ├── SKILL.md                           본문: 언제 쓰나, 문서 구조, 저장 위치, 보조 파일을 읽을 조건
    ├── TEMPLATE.md                        빈 양식 (문서를 쓰기 직전에 읽는다)
    ├── EXAMPLES.md                        버그 수정·기능·리팩터링 완성 예시 (예시가 필요할 때만 읽는다)
    ├── LICENSE.txt                        원본 MIT 라이선스 (그대로)
    └── NOTICE.md                          출처와 원본에서 바꾼 점 (모델은 읽지 않는다)
```

`prepare.py`가 만드는 샘플 프로젝트 `sandbox/`(git에는 올라가지 않음):

```
sandbox/
├── todo/store.py          할 일 목록 클래스. complete() 가 번호를 한 칸 어긋나게 처리하던 버그를 고친 상태(미커밋)
├── tests/test_store.py    회귀 테스트 3개 추가 (미커밋)
├── .opencode/             위 스킬 복사본
└── workthrough/           (스킬이 만들어 내는 문서, 처음에는 없음)
```

## 출처와 라이선스, 원본에서 바꾼 점

원본 스킬은 MIT 라이선스이며 저작권 고지가 `LICENSE.txt`에 그대로 들어 있다. opencode용으로 옮기면서 바꾼 것은 다음뿐이다(`NOTICE.md`에도 같은 내용이 있다).

1. `description`의 영어 문장은 그대로 두고 끝에 한국어 요청 문구("workthrough로 기록해줘" 등)를 덧붙였다.
2. 원본 `SKILL.md`는 문서 양식을 약 50줄 안에 직접 적고 있었고 `TEMPLATE.md`/`EXAMPLES.md`를 언급하지 않았다. 이 블록을 지우고 "두 파일을 **언제** 읽는가"를 적은 `Supporting Files` 절로 바꿨다. **이 변경이 이 예제의 핵심이다.** 스킬을 불러오면 모델은 폴더의 파일 목록을 받지만, 그 파일을 *언제* 읽어야 하는지는 `SKILL.md`가 말해 주지 않으면 알 수 없다.
3. "세션 끝에 자동으로 실행된다"는 문장을 "사용자가 요청하거나 작업을 마친 직후에 불러온다"로 바꿨다. opencode에는 세션 종료 시점의 자동 실행이 없고, 모델이 `description`을 보고 고른다.
4. 원본의 `README.md`, `QUICKSTART.md`는 다른 도구 기준의 안내라 가져오지 않았다. `TEMPLATE.md`, `EXAMPLES.md`, `LICENSE.txt`는 원본과 동일하다.

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 `-m opencode/big-pickle`(무료 모델)을 붙이세요.

1. 샘플 프로젝트를 만든다.

   PowerShell:
   ```powershell
   cd examples\01-skills\s2a-workthrough
   python prepare.py
   cd sandbox
   git status --short
   ```

   Linux bash (`python` 명령이 없으면 `python3`로 바꾸세요):
   ```bash
   cd examples/01-skills/s2a-workthrough
   python3 prepare.py
   cd sandbox
   git status --short
   ```

   수정된 파일 두 개(`todo/store.py`, `tests/test_store.py`)가 보이면 된다.

2. opencode를 실행하고 요청한다.

   ```
   opencode
   ```

   ```
   이 변경 작업을 workthrough로 기록해줘
   ```

   한 번에 실행하려면 `opencode run "이 변경 작업을 workthrough로 기록해줘"` (무료 모델: `opencode run -m opencode/big-pickle --auto "..."`).

3. 실행 기록에서 어떤 파일을 읽었는지 확인한다. `→ Skill "workthrough"`, `→ Read ...TEMPLATE.md`는 나오고 `EXAMPLES.md`는 나오지 않는 것이 정상이다.

4. 만들어진 `workthrough/YYYY-MM-DD-*.md`를 열어 본다.

5. 예시를 읽게 만들어 보자. `prepare.py`를 다시 실행한 뒤 이렇게 요청한다.

   ```
   이 변경 작업을 workthrough로 기록해줘. 작성 예시 문서를 참고해서 비슷한 수준으로 써줘.
   ```

   이번에는 `EXAMPLES.md`도 읽는다.

## 기대 결과

**실제 모델 실행 결과는 이 문서에 싣지 못했다.** 이 예제의 모델 확인을 시도했을 때 무료 모델 응답이 오지 않았다(과부하, 이후 사용량 소진). 따라서 "모델이 `TEMPLATE.md`는 읽고 `EXAMPLES.md`는 읽지 않는다"는 동작은 **미검증**이다. `python check.py --model`이 이를 확인하도록 작성되어 있으니 모델이 가능할 때 실행해 보자. 기대하는 실행 기록의 모양은 이렇다.

```
→ Skill "workthrough"
→ Read .../TEMPLATE.md
(... git diff, 테스트 실행 ...)
← Write workthrough/YYYY-MM-DD-....md
```

모델 없이 확인된 것(`python check.py`, Linux와 Windows에서 통과)은 다음과 같다. 가짜 LLM 서버가 opencode가 모델에게 보낸 요청을 기록해서 확인한다.

- 시스템 프롬프트의 `<available_skills>`에는 `workthrough`의 이름, description, 위치만 있고 본문(`Supporting Files` 절 등)은 없다.
- `skill` 도구 결과에는 SKILL.md 본문, `Base directory for this skill: ...`, 그리고 아래 파일 목록이 들어 있다.

```
<skill_files>
<file>.../workthrough/TEMPLATE.md</file>
<file>.../workthrough/EXAMPLES.md</file>
...
</skill_files>
```

- 이 시점의 도구 결과에는 `TEMPLATE.md`와 `EXAMPLES.md`의 *내용*이 없다(예: "Issues Encountered" 절, "Example 2: Feature Implementation").
- 모델이 `read`로 `TEMPLATE.md`를 연 뒤의 요청에서야 그 내용이 들어온다.

즉 파일을 나눈 효과(읽기 전에는 컨텍스트에 올라오지 않음)는 확인되었고, 모델이 *읽기로 결정하는지*가 미검증이다.

## 동작 원리

1. **발견**: opencode는 시작 시 `.opencode/skills/workthrough/SKILL.md`의 `name`과 `description`을 시스템 프롬프트의 `<available_skills>` 목록에 넣어 모델에게 알린다(본문은 넣지 않는다). `opencode debug skill`의 `content` 필드는 SKILL.md 본문만 담고, `TEMPLATE.md`나 `EXAMPLES.md`의 내용은 들어 있지 않다.
2. **선택**: "이 변경 작업을 workthrough로 기록해줘"가 description(영어 문장 + 한국어 문구)과 맞아서 모델이 `skill` 도구를 호출한다. 실행 기록에 `→ Skill "workthrough"`가 찍힌다. 도구 결과로 본문, 스킬 폴더의 절대 경로("Base directory"), 그리고 폴더 안 파일 목록(`<skill_files>`, 일부만 표본으로 제공)이 모델에게 전달된다. `TEMPLATE.md`/`EXAMPLES.md`의 *내용*은 아직 없다. `check.py`는 가짜 LLM 서버로 이 요청 내용을 직접 확인한다.
3. **본문이 길잡이 역할을 한다**: `Supporting Files` 절이 "TEMPLATE.md는 문서를 쓰기 직전에 읽어라", "EXAMPLES.md는 사용자가 예시를 원하거나 상세 수준을 정하기 어려울 때만 읽어라"라고 말한다. 모델은 그 지시를 따라 `Read` 도구로 해당 파일을 연다(`→ Read .../TEMPLATE.md`).
4. **그 사이에 일어나는 일**: SKILL.md의 지시대로 모델은 변경 내용을 모으고(`git diff`), 검증 결과를 얻기 위해 테스트를 실행한 뒤, 양식 순서에 맞춰 `workthrough/` 폴더에 문서를 쓴다.
5. **읽지 않은 파일은 대화에 없다**: 단순 요청에서 `EXAMPLES.md`는 읽히지 않으므로 그 11.8KB는 컨텍스트에 올라오지 않는다.

## 직접 바꿔 보기

- `SKILL.md`의 `Supporting Files` 절을 지우고 `prepare.py`를 다시 실행해 같은 요청을 해 보자. 모델이 `TEMPLATE.md`를 읽는지 실행 기록으로 확인하면, "본문이 말해 주지 않으면 읽지 않는다"는 것을 직접 볼 수 있다.
- `Supporting Files` 절에서 `EXAMPLES.md`의 조건(`only if ...`)을 "항상 읽는다"로 바꾸면 어떤 차이가 생기는지 실행 기록으로 비교해 보자.
- `TEMPLATE.md`에 팀 고유 절(예: `## 롤백 방법`)을 추가하고 다시 기록을 요청해 보자. 같은 양식이 문서에 반영된다.

## 주의할 점 / 문제 해결

- **`sandbox/`에서 실행해야 한다.** 그래야 `git diff`에 샘플 변경이 보인다. 이 폴더(`s2a-workthrough/`)에서 바로 실행하면 상위 세미나 저장소의 변경을 기록하려 한다.
- **모델이 보조 파일을 읽지 않을 수도 있다.** 모델 출력은 확률적이다. TEMPLATE.md를 읽지 않고 쓰는 일도 있다. 그럴 때는 "TEMPLATE.md를 읽고 그 양식으로 써줘"라고 하면 된다. 스킬 본문이 파일 이름과 읽을 조건을 분명히 적을수록 읽는 빈도가 올라간다.
- **같은 이름의 스킬이 이미 있다면**: 다른 곳(전역 폴더 등)에 `workthrough` 스킬이 있으면 이름이 겹친다. `opencode debug skill`의 `location`으로 어느 쪽이 쓰였는지 확인하자.
- **`.opencode/`가 있는 폴더에서 처음 실행하면** opencode가 `.opencode/` 안에 `package.json`, `node_modules/`, `.gitignore`를 자동으로 만든다(`@opencode-ai/plugin` 설치). 인터넷이나 패키지 미러에 접근할 수 없으면 첫 시작이 약 1분 이상 멈춘 것처럼 보일 수 있다.
- **Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요.** 모델이 테스트를 돌릴 때 `python`이 없으면 스스로 `python3`로 바꿔 실행하는 경우가 많다.
