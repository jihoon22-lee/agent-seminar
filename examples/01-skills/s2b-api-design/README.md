# S2b API 설계 스킬: SKILL.md가 길잡이가 되는 구조

> 구성: SKILL.md(라우터) + references/ 파일 5개 | 난이도: ★★☆ | 필요: opencode 1.19.5 | 슬라이드: 스킬 — 참조 파일 라우팅

## 무엇을 보여 주나

팀의 API 설계 규칙은 이름, 오류, 페이지네이션, 버전, 인증으로 나뉘고 하나하나가 길다. 이 규칙을 전부 `SKILL.md`에 넣으면 목록 조회 API 하나를 설계하는 데도 인증·버전 규칙까지 모두 읽게 된다.
이 예제의 `SKILL.md`는 **목차(라우터)** 다. "무엇을 설계할 때 어느 파일을 읽어라"만 적고, 실제 규칙은 `references/`의 파일에 둔다. 모델은 요청에 필요한 파일만 열어 본다.

## 실무에서는

- **규칙이 많은 팀 가이드를 스킬로 옮길 때**: API 설계, 데이터베이스 마이그레이션 규칙, 프런트엔드 컴포넌트 가이드처럼 분야별로 길어지는 문서를 주제별 파일로 나누고 `SKILL.md`는 목차로 둔다. 문서가 커져도 `SKILL.md`는 짧게 유지된다.
- **규칙 소유권 분리**: 인증 규칙은 보안 담당이, 페이지네이션 규칙은 API 팀이 고친다. 파일이 나뉘어 있으면 수정이 서로 부딪치지 않고, 변경 이력도 주제별로 남는다.
- **리뷰 기준의 일관성**: 설계 리뷰에서 "우리 규칙에는 커서가 `next_cursor`로 되어 있다"는 지적이 반복되던 것을, 설계 단계에서 에이전트가 처음부터 따르게 한다.
- **신규 팀원의 첫 API**: 규칙 문서를 다 읽기 전에도 에이전트와 함께 설계하면 팀 규칙에 맞는 초안이 나온다.

## 파일 구성

```
s2b-api-design/
├── README.md
├── check.py                                    자동 검증
├── fake_llm.py                                 가짜 LLM 서버. check.py 가 모델 없이 opencode 의 요청을 기록·재현하는 데 씀
└── .opencode/skills/api-design/
    ├── SKILL.md                                라우터: 어떤 요청에 어떤 파일을 읽는지 표로 안내
    └── references/
        ├── naming.md                           이름·ID·금액·시각 형식
        ├── pagination.md                       커서 방식, limit 기본 25 / 최대 100, next_cursor, pg1_ 접두사
        ├── errors.md                           오류 본문 형식, 상태 코드 표
        ├── versioning.md                       /v1 접두사, 폐기 일정
        └── auth.md                             Bearer 토큰, 스코프, 401/403/404 규칙
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 `-m opencode/big-pickle`(무료 모델)을 붙이세요.

1. 이 예제 폴더로 이동하고 스킬이 보이는지 확인한다.

   PowerShell:
   ```powershell
   cd examples\01-skills\s2b-api-design
   opencode debug skill
   ```

   Linux bash:
   ```bash
   cd examples/01-skills/s2b-api-design
   opencode debug skill
   ```

2. opencode를 실행하고 요청한다.

   ```
   opencode
   ```

   ```
   주문 목록 조회 API 설계해줘 (페이지네이션 포함)
   ```

   한 번에 실행하려면 `opencode run "주문 목록 조회 API 설계해줘 (페이지네이션 포함)"` (무료 모델: `opencode run -m opencode/big-pickle --auto "..."`).

3. 두 가지를 확인한다.
   - 실행 기록에 `→ Read .../references/pagination.md`가 있는가
   - 답변이 아래 "확인할 규칙"을 지켰는가

### 확인할 규칙 (`pagination.md`에만 있는 내용)

모델이 규칙 파일을 읽었는지는 답변에 팀 고유 규칙이 보이는지로 판별할 수 있다. 이 값들은 일반 상식이 아니라 이 팀의 규칙이다.

| 규칙 | 값 |
| --- | --- |
| 방식 | 커서만. `page`/`offset` 금지 |
| `limit` | 기본 25, 최대 100, 초과 시 400 + `limit_too_large` |
| 응답 목록 키 | `items` (`data` 아님) |
| 다음 커서 | `next_cursor`, 값은 항상 `pg1_` 접두사 |
| 끝 | `next_cursor: null`, `has_more: false` |

## 기대 결과

**실제 모델 실행 결과는 이 문서에 싣지 못했다.** 모델 확인을 시도했을 때 무료 모델 응답이 오지 않았다(과부하, 이후 사용량 소진). 그래서 "모델이 `pagination.md`를 읽고 `pg1_`를 답변에 쓴다"는 동작은 **미검증**이다. `python check.py --model`이 아래 항목을 확인하도록 작성되어 있다: `→ Read .../pagination.md` 기록, 답변의 `next_cursor`와 `pg1_`, `items` 키, `offset`/`page` 미사용, `auth.md`·`versioning.md` 미열람.

모델 없이 확인된 것(`python check.py`, Linux와 Windows에서 통과)은 다음과 같다. 가짜 LLM 서버로 모델이 받는 요청을 기록해서 본 결과다.

- 시스템 프롬프트에는 `api-design`의 이름과 description만 있고 규칙 값(`pg1_`)은 없다.
- `skill` 도구 결과에는 라우팅 표(본문), 스킬 폴더 경로, `references/`의 파일 목록이 들어 있고 규칙 값은 아직 없다.

```
Base directory for this skill: .../.opencode/skills/api-design
Relative paths in this skill (e.g., scripts/, reference/) are relative to this base directory.
Note: file list is sampled.

<skill_files>
<file>.../api-design/references/auth.md</file>
<file>.../api-design/references/pagination.md</file>
...
</skill_files>
```

- `pagination.md`를 `read`한 다음 요청에서야 `pg1_`가 모델에게 전달된다.

따라서 모델이 파일을 읽기만 하면 규칙이 반영되는 경로는 확인되었고, 모델이 *읽기로 결정하는지*가 미검증이다.

## 동작 원리

1. **스킬이 선택된다**: description의 "API 설계해줘", "목록 조회 API", "페이지네이션 넣어서 설계" 같은 문구가 요청과 맞아서 모델이 스킬을 불러온다. 이때 대화에 올라오는 것은 `SKILL.md` 본문(짧은 목차)뿐이다. `opencode debug skill`의 `content`에도 `pg1_`나 `next_cursor`는 없다. 이 사실은 `check.py`가 가짜 LLM 서버로 모델이 받는 요청을 직접 열어 확인한다(스킬 로드 결과에는 `pg1_`가 없고, `pagination.md`를 `read`한 뒤에야 들어온다).
2. **본문이 어느 파일을 읽을지 알려 준다**: 본문의 표가 "여러 건을 돌려주는 목록·검색 API가 있다 → `references/pagination.md`"라고 말한다. 모델은 이 줄을 근거로 `Read` 도구로 파일을 연다. 실행 기록의 `→ Read .../pagination.md`가 그 순간이다.
3. **읽은 규칙이 답변에 반영된다**: 파일 안의 `pg1_`, 기본 25 / 최대 100 같은 값이 답변에 나타난다. 일반 지식에서는 나오기 어려운 값이므로, 이것이 파일을 읽었다는 증거가 된다.
4. **필요 없는 파일은 읽지 않는다**: 본문의 규칙 1("해당하는 행의 파일만 읽는다")과 표 덕분에, 인증이나 버전 이야기가 없는 요청에서는 `auth.md`, `versioning.md`가 열리지 않는다.

### 왜 본문에 "어느 파일을, 언제" 읽는지 적어야 하나

- 모델은 시작할 때 스킬의 이름과 description만 안다. 스킬을 불러오면 본문과 함께 폴더의 파일 목록(`<skill_files>`)을 받지만, 이 목록은 **일부만 뽑은 표본**("file list is sampled")이고 "어떤 요청에 어느 파일"인지는 알려 주지 않는다.
- 파일 이름을 볼 수 있어도 `SKILL.md`가 읽으라고 하지 않으면 읽을 이유가 없다. "참고: references/ 폴더 참조"처럼 막연한 문장도 약하다. 어떤 요청일 때 어느 파일인지를 표로 적어야 안정적으로 읽힌다.
- 반대로 "항상 모든 파일을 읽어라"라고 쓰면 나눈 의미가 없다. 조건을 붙여야 점진적 공개의 이점(컨텍스트 절약)이 생긴다.
- 경로는 SKILL.md가 있는 폴더 기준 상대 경로로 적는다. 스킬을 불러올 때 도구 결과에 "Base directory for this skill: <절대 경로>"와 "Relative paths in this skill (e.g., scripts/, reference/) are relative to this base directory."라는 안내가 함께 오므로 이 표현으로 충분하다.

## 직접 바꿔 보기

- `SKILL.md`의 라우팅 표에서 `pagination.md` 행을 지우고 같은 요청을 해 보자. 모델이 `pg1_`와 `items` 없이 일반적인 페이지네이션(예: `data`, `offset`)으로 답하는지 확인한다. 규칙 파일이 폴더에 있어도 길잡이가 없으면 읽히지 않는다.
- `references/pagination.md`의 `limit` 최대값을 100에서 50으로 바꾸고 같은 요청을 해 보자. 답변의 값이 따라 바뀐다. 규칙을 고치려면 파일 하나만 고치면 된다.
- 새 주제 파일 `references/idempotency.md`를 만들고 라우팅 표에 행을 추가해 보자. "결제 API 설계해줘"로 읽히는지 확인한다.
- "주문 목록 조회 API 설계해줘. 인증과 오류 응답도 포함해줘"처럼 요청을 넓히면 `auth.md`, `errors.md`까지 읽는지 실행 기록으로 확인하자.

## 주의할 점 / 문제 해결

- **파일 읽기가 항상 일어나지는 않는다.** 모델에 따라 라우팅 표를 건너뛰고 일반 지식으로 답할 수 있다. 이때는 답변에 `pg1_`가 없다. 표의 "읽을 파일" 열을 굵게 하거나, 본문 맨 위에 "규칙은 읽은 파일에 적힌 것만 따른다"를 두는 것(이 예제가 그렇게 한다)이 도움이 된다.
- **`.opencode/`가 있는 폴더에서는** opencode가 시작할 때 `@opencode-ai/plugin`을 npm에서 설치하려 시도하고, 성공하면 `.opencode/` 안에 `package.json`, `node_modules/`, `.gitignore`가 생긴다(모두 git에서 제외). 이 예제에는 플러그인(`.opencode/plugins/*.js`)이 없어서, 레지스트리에 닿지 않는 환경에서도 눈에 띄는 멈춤은 없었다(연결을 거부하는 레지스트리로 측정: `opencode debug skill` 약 2초, `opencode run` 약 4초. TUI는 확인하지 못했다). 설치 시도 자체는 일어난다. 같은 환경에서 `.opencode/plugins/*.js`가 있는 폴더(P1~P8 등)는 시작할 때마다 약 70초 멈춘다(새 환경의 맨 처음 시작은 약 130초). 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있다.
- **이 규칙은 가상의 팀 규칙이다.** 실제 서비스의 API 설계 가이드가 아니므로 규칙 값(`pg1_` 등)을 그대로 쓰지 말고 팀의 규칙으로 바꿔 쓰자.
