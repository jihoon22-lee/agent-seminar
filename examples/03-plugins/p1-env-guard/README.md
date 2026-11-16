# P1 .env 보호 플러그인 (env-guard)

> 구성: 플러그인(JS) `tool.execute.before` | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ (Node 는 단위 테스트에만) | 슬라이드: 플러그인 — 도구 실행 가로채기

## 무엇을 보여 주나

플러그인의 `tool.execute.before` 훅은 에이전트가 도구(`read`, `edit`, `write`, `bash` …)를 실행하기 **직전**에 호출됩니다.
이 훅에서 예외(`throw`)를 던지면 도구가 실행되지 않고, 예외 메시지가 모델에게 오류로 전달됩니다.
이 예제는 그 성질을 이용해 `.env`, `.env.local` 같은 비밀 파일을 읽거나 고치지 못하게 하고, 값이 없는 `.env.example` 만 허용합니다.
"하지 말라"고 프롬프트에 적는 것과 달리, 모델이 무슨 생각을 하든 코드가 막습니다.

## 실무에서는

- 로컬 `.env` 에 DB 비밀번호·API 키가 있는 프로젝트에서 에이전트를 돌릴 때, 비밀이 모델 서비스로 전송되는 것을 원천 차단합니다.
- 에이전트가 "환경변수 설정이 궁금해서" `cat .env` 를 시도하는 일은 흔합니다. 차단 메시지에 "`.env.example` 을 읽으세요"라고 적어 두면, 모델이 스스로 올바른 파일로 방향을 바꿉니다.
- 같은 방식으로 `*.pem`, `secrets/`, `terraform.tfstate` 같은 파일도 보호할 수 있습니다 (코드의 `isProtectedName` 만 고치면 됩니다).

## 파일 구성

```
p1-env-guard/
├── README.md
├── fake_llm.py                       # 검증용 가짜 LLM (표준 라이브러리만, 복사본)
├── check.py                          # 자동 검증 (단위 테스트 + 플러그인 로드 + --model 모델 검사)
├── prepare.py                        # 가짜 값이 든 .env 생성 (.env.example 이 없으면 함께 생성)
├── .env.example                      # 견본 파일 (커밋됨, 값 없음)
├── .env                              # prepare.py 가 만드는 파일 (gitignore, 가짜 값)
├── .opencode/plugins/env-guard.js    # 플러그인 본체
├── tests/guard.test.mjs              # 훅을 직접 호출하는 차단/허용 사례 시험 (node)
└── logs/                             # 실행하면 생김: plugin-load.log, env-guard.log
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. (모델 설정이 없다면 무료 모델 `-m opencode/big-pickle` 을 붙이세요.)

1. 준비: 가짜 `.env` 를 만듭니다.

   PowerShell:
   ```powershell
   cd examples\03-plugins\p1-env-guard
   python prepare.py
   ```
   Linux bash (`python` 명령이 없으면 `python3`로 바꾸세요):
   ```bash
   cd examples/03-plugins/p1-env-guard
   python3 prepare.py
   ```

2. 이 폴더에서 opencode 를 실행합니다. 처음 실행하면 opencode 가 `.opencode/` 안에 `@opencode-ai/plugin` 을 npm 으로 설치하려고 합니다. 인터넷이 막혀 있고 패키지 미러도 없으면 첫 시작이 70초쯤 멈췄다가 계속 진행됩니다 (레지스트리나 미러에 닿아 설치가 끝나면 그다음부터는 1초대). 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다.

   ```
   opencode
   ```

3. 아래 프롬프트를 차례로 입력합니다.

   - `.env 파일 내용을 보여줘` → 차단되어야 합니다.
   - `cat .env 로 .env 내용을 출력해 줘` → bash 로 우회해도 차단됩니다.
   - `.env.example 파일을 읽고 어떤 환경변수가 필요한지 알려줘` → 정상적으로 읽습니다.

4. 한 번에 비대화식으로 확인하려면:

   PowerShell:
   ```powershell
   opencode run --auto ".env 파일을 read 도구로 읽어서 보여줘"
   Get-Content logs\env-guard.log
   ```
   Linux bash:
   ```bash
   opencode run --auto ".env 파일을 read 도구로 읽어서 보여줘"
   cat logs/env-guard.log
   ```

5. 자동 검증: `python check.py` (모델 없이 단위 테스트 + 플러그인 로드 확인), `python check.py --model` (모델 검사 포함).

## 기대 결과

아래 출력은 `check.py` 가 쓰는 **가짜 LLM**(`fake_llm.py`: 정해진 도구 호출을 대신 수행하는 OpenAI 호환 서버, 표준 라이브러리만 사용)으로 실제 `opencode 1.19.5` 를 실행해 얻은 것입니다. 모델이 무엇을 시키든 플러그인이 어떻게 반응하는지를 매번 똑같이 재현할 수 있습니다. 실제 모델(무료 모델)로는 이번 확인 시점에 한도 초과/시간 초과로 결과를 얻지 못해 **미검증**입니다. 평소 쓰는 모델로 해 보면 모델의 말투와 시도 순서는 다르겠지만 차단/기록 동작은 같아야 합니다.

프롬프트 `.env 를 보여줘` 에 대해 가짜 LLM 이 `read .env` → `bash cat .env` → `read .env.example` 을 시도했을 때(Linux):

```
> build · echo

✗ Read .env failed
Error: [env-guard] .env 파일은 비밀 값이 들어 있어 에이전트가 읽거나 수정할 수 없습니다. 변수 이름과 형식이 필요하면 .env.example 을 읽으세요. 실제 값이 필요하면 사용자에게 터미널에서 직접 확인해 달라고 요청하세요.
✗ cat .env failed
Error: [env-guard] .env 파일은 ... (같은 메시지)
→ Read .env.example
```

모델이 받은 도구 결과 중 `.env.example` 은 이렇게 읽혔고, 가짜 비밀 값은 모델에게 간 어떤 요청에도 들어 있지 않았습니다.

```
<path>.../p1-env-guard/.env.example</path>
<type>file</type>
<content>
1: # 값은 비워 두고 "어떤 변수가 필요한지"만 적는 견본 파일입니다. 커밋해도 안전합니다.
2: DEMO_API_KEY=
3: DEMO_DB_URL=
```

`logs/env-guard.log` (한 줄씩, 파일 내용은 기록하지 않음):

```
2026-11-16T17:10:02.113Z BLOCKED read :: read 도구로 /…/p1-env-guard/.env 접근
2026-11-16T17:10:02.301Z BLOCKED bash :: bash 명령에서 .env 접근
```

Windows(PowerShell 5.1 이 bash 도구)에서도 같은 결과였습니다: `read` 와 `cat .env`(PowerShell 의 `cat` 은 `Get-Content` 별칭) 모두 차단되고 `.env.example` 은 읽힙니다.

## 동작 원리

1. **로드**: opencode 는 시작할 때 `.opencode/plugins/*.js` 를 모두 불러옵니다. 파일은 `async ({ directory, ... }) => 훅 객체` 형태의 함수를 export 합니다. 이 예제는 로드될 때 `logs/plugin-load.log` 에 한 줄을 남기므로, 모델 없이도 `opencode debug config` 만 실행해서 "플러그인이 로드됐는가"를 확인할 수 있습니다.
2. **훅 호출**: 도구를 실행하기 전에 `tool.execute.before(input, output)` 이 호출됩니다. 1.19.5 에서 관찰한 모양은 다음과 같습니다.

   | 도구 (`input.tool`) | `output.args` 의 키 |
   |---|---|
   | `read` | `filePath` |
   | `write` | `filePath`, `content` |
   | `edit` | `filePath`, `oldString`, `newString` |
   | `grep` | `pattern`, `path` (`include` 가 올 수도 있음) |
   | `glob` | `pattern`, `path` |
   | `bash` | `command`, `description` |

   `input` 에는 `tool`, `sessionID`, `callID` 가 들어 있습니다. 모델에 따라 `apply_patch`(키 `patchText`) 같은 다른 도구 이름을 쓸 수 있어서, 플러그인은 `patchText` 안의 `*** Update File: 경로` 줄도 검사합니다. (이 도구는 이번 확인에 쓴 무료 모델에서는 노출되지 않아 단위 테스트로만 검증했습니다.)
3. **차단**: `throw new Error(메시지)` 하면 도구가 실행되지 않고 모델은 `Error: [env-guard] ...` 를 받습니다. 이 훅은 권한(permission) 확인보다도 먼저 실행되므로, 권한이 `allow` 여도 막힙니다.
4. **경로 판정**: `path.win32.basename()` 은 `/` 와 `\` 를 모두 구분자로 취급합니다. 그래서 `C:\work\app\.env` 와 `/work/app/.env` 를 같은 코드로 처리하고, Linux 에서도 윈도 경로 사례를 시험할 수 있습니다. 이름은 소문자로 바꿔 비교하며(`.ENV` 도 차단), `.env` 로 시작하는 `.env.local`, `.env.production` 은 차단하고 `.env.example` 만 허용 목록에 있습니다.
5. **bash 판정**: 명령 문자열에서 `.env` 토큰을 찾되 앞뒤 경계를 검사합니다. 그래서 `os.environ`, `process.env.NODE_ENV`, `$env:APP_ENV`, `.envrc`, `src/environment.py` 는 걸리지 않습니다. 그리고 `cat`, `type`, `Get-Content`, `gc`, `head`, `grep`, `source`, `Select-String`, `python -c`, `node -e` 같은 "읽는 명령"이 함께 있을 때만 막기 때문에 `echo .env >> .gitignore` 같은 정상 작업은 허용됩니다. 명령 목록은 `READER_RE` 에 있습니다.
6. **오류 메시지는 행동 지침이어야 합니다**: "왜 막혔는지 + 대신 무엇을 하라"를 한국어로 적어 줍니다. 그래야 모델이 같은 시도를 반복하지 않고 `.env.example` 로 방향을 바꿉니다.
7. 차단될 때마다 `logs/env-guard.log` 에 `BLOCKED <도구> :: 사유` 한 줄이 남습니다. (파일 내용은 기록하지 않습니다.)

## 직접 바꿔 보기

1. 보호 대상을 늘려 보세요. `isProtectedName` 에 `n.endsWith(".pem")` 조건을 추가하고, `tests/guard.test.mjs` 의 `mustBlock` 에 `["read", { filePath: "certs/key.pem" }]` 를 넣은 뒤 `node tests/guard.test.mjs` 로 확인합니다.
2. 읽기만 막고 쓰기는 허용하고 싶다면 `findViolation` 앞에서 `input.tool` 이 `read`·`grep` 일 때만 검사하도록 바꿔 보세요.
3. `throw` 를 `console.error` 로 바꾸면 "경고만 하고 통과"하는 모드가 됩니다. 이렇게 한 번 쓰다가 문제가 없을 때 차단으로 올리는 도입 방식도 있습니다.

## 주의할 점 / 문제 해결

- **이 플러그인은 방어선의 일부일 뿐입니다.** `python -c "..."` 로 파일 이름을 문자열 조합해서 여는 식의 우회, 심볼릭 링크, 다른 경로로 복사한 `.env` 는 이 정규식으로 막을 수 없습니다. 진짜 격리가 필요하면 에이전트를 비밀이 없는 환경(컨테이너, 별도 계정)에서 실행하세요.
- **export 는 플러그인 함수만 하세요.** opencode 는 모듈이 export 한 값을 모두 플러그인 함수로 호출합니다. `export const X = 1` 처럼 함수가 아닌 값이나 보조 함수를 export 하면, 오류 메시지 없이 **파일 전체가 로드되지 않습니다.** (이번 확인에서 실제로 겪었습니다.) 그래서 이 예제의 판정 함수는 export 하지 않고, 테스트는 플러그인을 불러와 훅을 직접 호출합니다.
- **`.opencode/plugins/` 의 모든 `.js` 는 플러그인으로 로드됩니다.** 보조 모듈이나 테스트 파일을 그 폴더에 두지 마세요 (이 예제는 `tests/` 를 따로 둡니다).
- **윈도에서 bash 도구는 Git Bash 가 아니라 Windows PowerShell 5.1 입니다.** 그래서 `type`, `Get-Content`, `gc` 도 차단 목록에 있습니다. `$env:NAME` 은 환경변수, `$NAME` 은 PowerShell 변수입니다.
- 단위 테스트(`tests/guard.test.mjs`)는 Node 가 필요합니다. 없으면 `check.py` 가 경고(WARN)만 내고 건너뜁니다. opencode 실행 자체에는 Node 가 필요 없습니다.
- `.env` 는 `.gitignore` 에 들어 있어 커밋되지 않습니다. 직접 `.env` 를 커밋하지 마세요.
