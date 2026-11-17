# 5. 문제 해결

이 문서는 각 예제 README의 "주의할 점 / 문제 해결"을 한곳에 모은 증상 → 원인 → 해결 표입니다. 위쪽 표는 영역별(설정, 스킬, MCP, 플러그인, 종합), 아래쪽에는 Windows에서만 생기는 문제와 "모델이 안 움직일 때"를 따로 모았습니다.
모든 내용은 **opencode 1.19.5** 기준입니다.

먼저 이 네 명령으로 대부분의 원인이 보입니다. 설정은 시작할 때 한 번만 읽으므로 **고친 뒤에는 opencode를 다시 시작**하세요.

| 증상 | 명령 |
|---|---|
| 키 오타, 다른 파일이 덮어쓴 값 | `opencode debug config` |
| 스킬이 안 보인다 | `opencode debug skill` |
| MCP 서버가 안 붙는다 | `opencode mcp list` (`--print-logs` 로 로그 보기) |
| 권한 규칙이 의도와 다르다 | `opencode debug agent build` |

## 설정 ([1장](01-config.md))

| 증상 | 원인 | 해결 |
|---|---|---|
| 플러그인을 등록했는데 안 불린다. 권한이나 스킬 경로 설정이 안 먹는다 | 최상위 키 오타(`plugins`, `permision`, `"skills": {"path": ...}`)는 오류 없이 버려진다. 공식 문서의 다음 버전 형식 중 `plugins`도 1.19.5에서는 오류 없이 무시된다(`mcp.servers`와 `"disabled": true`는 예전 형식으로 바꿔 읽으므로 동작한다) | `opencode debug config`에 키가 실제로 남았는지 확인. `$schema`를 넣어 편집기가 미리 경고하게 한다. 문서를 볼 때 버전을 확인 |
| `Configuration is invalid`로 시작이 안 된다 | `mcp` 항목 안의 오타, 또는 잘못된 권한 값(`"permission": {"bash": "maybe"}` → `Expected PermissionActionConfig`) | 메시지가 가리키는 키를 고친다 |
| `Configuration is invalid ... bad file reference ... does not exist` | `{file:경로}`의 파일이 없다 (`enabled: false` 항목이어도 시작 거부) | 파일을 만들거나(예제: `python prepare.py`) 경로를 고친다. 상대 경로는 **설정 파일이 있는 폴더** 기준 |
| `Config file at ... is not valid JSON(C)` | JSON 문법 오류 (주석과 끝 쉼표는 허용) | 메시지의 줄 번호 확인 |
| 서버가 인증에 실패한다. 토큰이 비어 있다 | `{env:NAME}`이 미설정이면 오류 없이 **빈 문자열**. 환경 변수는 opencode를 실행한 셸에서 읽는다 | 같은 터미널에서 설정하고 opencode를 다시 시작. 서버가 실제로 받은 값을 확인(C2의 `received.json`) |
| 서버가 `${DEMO_TOKEN}` 글자 그대로 받는다 | `${}` 셸 문법은 치환되지 않는다 | `{env:DEMO_TOKEN}` |
| `debug config`에서 `***`인데 값이 설정됐는지 모르겠다 | 마스킹은 이름 기반이고, 미설정도 이름이 비밀스러우면 `***` | 서버 쪽에서 값을 확인하게 한다 |
| `debug config` 출력에 비밀번호가 그대로 보인다 | `DATABASE_URL`, `ACCESS_KEY`, `AUTH`, `PASS`, `TOKEN_PATH` 같은 이름은 마스킹되지 않는다 | 이름을 `..._TOKEN`(끝), `..._SECRET`, `..._PASSWORD`, `..._API_KEY`로 짓는다. 출력을 공유하기 전에 확인 |
| 예상 밖의 설정 값이 보인다 | git 저장소가 아닌 폴더에서는 상위 폴더의 `opencode.json`까지 병합된다 | `git init`으로 경계를 만들거나 `OPENCODE_DISABLE_PROJECT_CONFIG=1` |
| `OPENCODE_CONFIG`로 지정했는데 프로젝트 값이 이긴다 | 그 파일은 전역 위, 프로젝트 아래의 층이다 | 정상 동작. 프로젝트보다 강하게 얹으려면 `OPENCODE_CONFIG_CONTENT` |
| 전역 `permission.bash` 규칙이 통째로 사라졌다 | 프로젝트에서 `"bash": "allow"`처럼 **객체를 문자열로** 바꾸면 병합이 멈추고 교체된다 | 객체로 유지하거나 의도한 것인지 확인 |
| 규칙이 먹지 않고 `*`가 이긴다 | 평가는 순서대로, **마지막 일치가 이긴다.** 구체적 예외를 `*` 앞에 쓴 경우 | `*`를 맨 앞에. `opencode debug agent build`로 순서 확인 |
| `rm *: deny`인데 파일이 지워졌다 | 패턴은 문자열 전체와 비교한다. `git rm -f`, `unlink`, `find -delete`, 스크립트 속 삭제는 못 잡는다 | 허용 목록 방식(`"*": "deny"`로 시작)이나 플러그인 가드 |
| `Tool bash is disabled for agent build` | `bash`의 모든 사용이 deny (예: 마지막 `*`가 deny) | 의도한 것인지 확인. 규칙 순서를 바꾼다 |
| `plan` 에이전트가 파일을 수정하려 한다 | 전역 `"edit": "ask"`가 plan의 기본 `edit deny` 뒤에 쌓여 ask가 된다 | `opencode debug agent plan`으로 확인하고 `edit` 규칙을 조정 |
| `opencode run`에서 `ask` 명령이 `auto-rejecting`으로 거절된다 | 비대화형이라 승인할 사람이 없다 | `--auto` (단 `deny`는 `--auto`로도 막힌다). 신뢰할 수 없는 프롬프트에는 `ask`가 아니라 `deny` |
| 격리 실행에서 모델 로그인이 없다 | 샌드박스는 `auth.json`과 전역 설정이 없다 | `-m opencode/big-pickle` 같은 무료 모델, 또는 필요한 설정을 `--global-config`로 |
| `OPENCODE_CONFIG_CONTENT`가 적용되지 않는다 | 프로세스 단위라 이미 떠 있는 opencode에는 안 먹는다. JSON이 깨졌거나 셸 따옴표 문제일 수 있다 | 새 프로세스로 실행. PowerShell은 바깥 작은따옴표, 안쪽 큰따옴표 |
| `--command 이름`이 `UnknownError ... Unexpected server error`로 끝나고 이름 얘기가 없다 (C6) | 없는 명령 이름이다. 종료 코드 1, 모델 호출 없음. `--print-logs`로 봐도 이름은 안 나온다 | `opencode debug config`의 `command`에서 이름 확인. 같은 이름이 `.md`와 `command` 키에 모두 있으면 `.md`가 이긴다 |
| 명령 인자 안의 큰따옴표가 깨져서 들어간다 (C6) | 인자 안의 큰따옴표는 모양이 깨진다. 공백이 있는 인자는 `$ARGUMENTS`에 따옴표가 붙고 `$1`은 뗀 값이다 | 따옴표가 필요한 값은 파일 경로로 넘기고 본문에서 읽게 한다 |
| `Error: Invalid URL` (C7) | `provider`의 `baseURL`로 쓴 `{env:}`가 미설정이라 오류 없이 빈 문자열이다. 서버에는 요청이 가지 않는다 | `opencode debug config`에서 `baseURL`이 비었는지 확인, 변수를 설정한 같은 터미널에서 실행. `--print-logs --log-level ERROR`로 어느 provider·모델인지 확인 |
| `Error: Incorrect API key provided`인데 키를 넣었다고 생각한다 (C7) | 키가 틀렸거나 `{env:}` 미설정이다. 미설정이면 `Authorization` 헤더 자체를 안 보내는데 화면 메시지는 같다. `debug config`의 `apiKey`는 값이 있든 없든 `***` | 서버 쪽 기록에서 `Authorization`이 있는지 확인. 화면만으로는 둘을 가를 수 없다 |
| 모델 서버가 꺼져 있는데 한참 멈췄다가 `Cannot connect to API: ECONNREFUSED` (C7) | 오류가 나오기까지 약 68초가 걸렸다(원인은 확인하지 못함) | 기다리면 메시지가 나온다. 서버 실행과 `baseURL` 확인 |
| `opencode models`에는 내 모델이 나오는데 질문하면 연결이 안 된다 (C7) | `opencode models`는 설정에 적힌 모델을 보여 줄 뿐 서버에 접속하지 않는다 | 실제로 한 번 질문해 보고 `--print-logs`로 본다 |
| `--agent 이름`으로 시작했는데 권한이 안 먹는다. 헤더가 `> build` (C8) | `--agent`에 `subagent`이거나 없는 이름을 주면 경고 한 줄과 함께 `build`로 실행한다. 종료 코드 0이라 조용히 넘어간다 | 실행 헤더 확인, `mode: primary`인지 확인, 이름의 오타 확인 |
| 읽기 전용으로 만든 에이전트가 파일을 고쳤다 (C8) | `edit`·`bash`만 막고 `task`가 열려 있으면 `task`로 부른 내장 `general`이 자기 권한으로 수정한다. 하위 작업은 부른 쪽의 제한을 물려받지 않는다 | 에이전트의 `permission`에 `task: deny` |
| `docs/**`만 허용한 에이전트가 `docs/` 파일도 거부된다 (C8) | 경로 규칙은 git 저장소 루트 기준 상대 경로다. `.git`이 없거나, 루트 아래 하위 폴더의 `sub/docs/...`는 `docs/**`에 걸리지 않는다 | 프로젝트 폴더를 git 저장소 루트로 둔다 |

## 스킬 ([2장](02-skills.md))

| 증상 | 원인 | 해결 |
|---|---|---|
| 스킬이 안 불린다 | description이 모호하다. 모델이 가진 단서는 이름, description, 위치뿐이다 | "무엇 + 언제 + 사용자가 칠 말 + 고유 단어". 프롬프트에 스킬 이름을 직접 넣으면 열린다 |
| 스킬을 건너뛰고 `grep`부터 한다 | 모델이 스킬을 고르는 단계는 확률적이다 | description을 다듬고, 데모처럼 실패하면 안 되는 자리에서는 이름을 직접 말한다 |
| `opencode debug skill`에 안 나온다 | 위치가 틀렸다 (`.opencode/skills/<이름>/SKILL.md`). 다른 폴더에서 실행했다 | 실행 폴더 확인. 프로젝트 스킬은 실행 폴더에서 git 루트까지 위로 올라가며 찾는다 |
| 스킬을 고쳤는데 반영이 안 된다 | 스킬은 시작할 때 한 번만 읽는다 | opencode를 다시 시작 |
| `debug skill`에는 있는데 모델이 못 본다 | `permission.skill`로 deny했거나 `description`이 없다. `debug skill`은 모델 목록이 아니다 | 모델이 받는 목록은 S5b의 `show_prompt.py`로 확인 |
| `disable-model-invocation: true`를 썼는데 모델이 쓴다 | 1.19.5에서는 효과가 없다. 에러도 경고도 없다 | `permission.skill`의 `deny`. 사람은 `/skills`나 `opencode run --command 이름` |
| `deny`를 썼는데 막히지 않는다 | 규칙 순서. `{"deploy-*": "deny", "*": "allow"}`는 `*`가 이긴다 | `*`를 먼저, 좁은 규칙을 뒤에 |
| 같은 이름의 스킬이 두 곳에 있다 | 이름 단위로 합쳐지는데 이기는 쪽이 경쟁이라 가끔 뒤집힌다 (`duplicate skill name` 경고) | 이름을 겹치지 않게 접두사(`team-`, `my-`) |
| `skills.paths`의 공용 스킬이 하위 폴더에서 사라진다 | 상대 경로는 설정 파일이 아니라 **opencode를 실행한 폴더** 기준. `skill path not found` 경고만 남고 멈추지 않는다 | `~/team-skills`나 절대 경로 |
| `skills.urls` 스킬이 갑자기 사라졌다 | 시작할 때마다 `index.json`을 가져오는데 실패하면 캐시가 있어도 그 URL의 스킬이 통째로 사라진다 | 서버가 살아 있는지 확인. 오프라인이 필요하면 `skills.paths` + git |
| `skills.urls` 내용을 바꿨는데 안 바뀐다 | `index.json`에 `version`이 없거나 안 바꿨다 | `version` 문자열을 바꾼다 |
| 스킬이 보조 파일을 읽지 않는다 | 본문이 "언제 어느 파일"을 분명히 말하지 않았다. 파일 목록 `<skill_files>`는 표본이다 | 본문에 조건과 파일 이름을 표로 적는다. 급하면 "TEMPLATE.md를 읽고 써 줘" |
| 스킬 스크립트가 Windows에서 실패한다 | `bash` 도구가 PowerShell 5.1이라 `&&`, `$변수`, `wc`, `head`가 안 된다 | `python <스킬 폴더>/scripts/x.py 인자` 한 줄. 아래 Windows 절 참고 |
| `python: command not found` (Linux) | Linux에는 `python`이 없고 `python3`만 있다 | `SKILL.md`에 "없으면 `python3`" 한 줄. 모델이 스스로 바꿔 쓰기도 한다 |
| 스크립트 결과의 한글이 깨진다 (Windows) | 기본 출력 인코딩이 cp949 | 스크립트가 stdout을 UTF-8로 고정 (`sys.stdout.reconfigure(encoding="utf-8")`) |
| 스킬 결과가 엉뚱한 저장소를 대상으로 한다 | 예제 폴더에서 바로 실행하면 상위 세미나 저장소(git 루트)가 프로젝트가 된다 | 예제가 안내하는 `sandbox/`에서 실행 (S1a, S2a, S3b, S3c 등) |
| `error: git not found`, 종료 코드 2 (S3b) | git이 PATH에 없다 | git 설치 |
| `branch-cleanup` 스킬이 멈추고 알린다 (S1d) | 기본 브랜치가 `main`이 아닌 저장소다(`SKILL.md` 규칙) | `SKILL.md`의 `main`을 모두 바꾼다 |
| 스크립트가 종료 코드 2와 `error: line N` (S4a) | CSV 형식이 틀렸다 (UTF-8, 헤더 `month,region,units,revenue`) | CSV를 고친다 |
| 스크립트가 `error: cannot parse 파일:줄` (S4b) | 분석 대상에 문법 오류가 있는 파일이 있다 | 해당 파일을 고치거나 하위 패키지 폴더만 지정 |
| 같은 날짜·slug로 다시 만들면 `-2` 파일이 생긴다 (S1c, S2c) | 스킬 규칙이 덮어쓰지 않도록 되어 있다 | 정상 동작. 다시 비교하려면 결과 폴더를 지우고 실행 |
| 가짜 토큰 문자열을 커밋했더니 push가 거절된다 | 토큰 모양 문자열은 secret scanning에 걸린다 | `demo-token-123` 같은 명백한 가짜 값을 쓰거나 실행 시점에 조립 (S3c) |
| TUI의 `/` 자동완성에 스킬이 안 나온다 | 1.19.5에서 스킬은 자동완성 목록에 나오지 않는다 (Linux에서 확인) | `/skills` 입력으로 선택창을 연다 |

## MCP ([3장](03-mcp.md))

| 증상 | 원인 | 해결 |
|---|---|---|
| `✗ ... failed — Operation timed out after 30000ms` | 서버 파일을 못 찾았다. `command`의 상대 경로는 **opencode를 실행한 폴더** 기준. 서버가 즉시 죽어도 표시는 30초 뒤에 나온다 | 예제 폴더에서 실행. `python server.py`를 직접 실행해 오류 확인 |
| `Executable not found in $PATH: "python"` (Linux) | `python` 명령이 없다 | `command`를 `["python3", "server.py"]`로. 가상환경이면 `.venv/bin/python` |
| `failed`인데 이유를 모르겠다 | stdout이 오염됐거나 서버가 죽었다. 서버의 stderr는 opencode 화면과 로그에 나오지 않는다 | 서버를 터미널에서 직접 실행해 첫 줄 확인. `opencode debug paths`의 `log` 폴더에서 `opencode.log` |
| `failed (Operation timed out)`이고 서버를 직접 실행하면 배너가 보인다 | 줄바꿈 없이 stdout에 쓴 글자가 다음 JSON 앞에 붙는다 | stdout에는 MCP 메시지만. 로그는 stderr |
| 시작이 느린 서버가 `failed` | 연결 제한 약 30초 초과 | 서버 항목에 `"timeout": 15000`(ms). 무거운 초기화는 첫 호출로 미룬다 |
| 도구 호출이 `MCP error -32001: Request timed out` | 호출 제한 약 60초 초과 | 서버 항목의 `timeout`, 또는 `experimental.mcp_timeout`을 늘린다 |
| `connected`인데 호출하면 `MCP error -32000: Connection closed`, 이후 `unavailable tool` | 서버가 호출 중 죽었다. 죽은 서버의 도구는 목록에서 빠진다. traceback은 어디에도 안 남는다 | 도구 실행을 `try/except`로 감싸 `isError: true` 반환. opencode를 다시 시작 |
| `connected`인데 한글이 `�ȳ��ϼ���` | 한국어 Windows(cp949)에서 서버 stdout 인코딩이 UTF-8이 아니다. Linux에서는 안 드러난다 | `sys.stdout.reconfigure(encoding="utf-8")` |
| 서버를 고쳤는데 반영이 안 된다 | 서버는 opencode 시작 때 띄운다 | opencode를 다시 시작 |
| 원격: `SSE error: Non-200 status code (401)` | 토큰이 틀렸다. 서버와 opencode가 다른 창의 환경 변수를 보고 있거나 값 끝에 공백이 붙었다 | 같은 값인지 확인, 환경 변수를 설정한 터미널에서 opencode 실행 |
| 원격: 인증 실패인데 `mcp list` 메시지가 비어 있다 | `oauth` 키가 없어 opencode가 OAuth 탐색을 한다 | 고정 토큰 서버에는 `"oauth": false` |
| 원격: 틀린 토큰이 `405`로 보인다 | 서버가 `GET`에 인증 없이 405를 준다 | 서버가 `GET`에도 토큰을 먼저 검사해 `401`을 준다 |
| 원격: `SSE error: ECONNREFUSED` | 서버가 꺼져 있거나 주소/포트가 다르다 | 서버 실행 확인, 포트 충돌(`Address already in use`)도 확인 |
| 원격: `Invalid MCP URL for "team-shared"` | `url`의 `{env:}`가 비어 있다 | 환경 변수를 설정한 같은 터미널에서 실행 |
| 원격 서버를 `0.0.0.0`으로 열었다 | 같은 네트워크의 모든 PC가 접속 가능, 예제는 평문 HTTP라 토큰이 보인다 | 방화벽으로 대역 제한, HTTPS 프록시, 사용자별 토큰 |
| 토큰이 없다는 도구 오류가 나는데 모델이 `bash`로 데이터를 읽는다 | 서버의 토큰 검사는 그 서버의 도구만 막는다 | `permission`/플러그인으로 파일 접근을 막는다. 민감한 데이터는 원격 서버 뒤에 |
| `pip` 설치 실패 (M2) | 인터넷이 막혀 있다 | 패키지 미러 주소를 지정 |
| `ModuleNotFoundError: mcp.server.fastmcp` | `mcp` 2.x에서 `FastMCP`가 `MCPServer`로 바뀌었다 | 새 코드는 `from mcp.server.mcpserver import MCPServer`, 옛 예제는 `mcp<2` |
| M2의 `opencode.json`이 없거나 틀린 OS용이다 | OS별 템플릿에서 복사한다. `.venv`는 OS마다 따로 만든다 | `python prepare.py`를 다시 실행 |
| `/runbooks:...` 명령이나 `@` 리소스가 안 나온다 (M7) | 서버가 `initialize`의 `capabilities`에 `prompts`/`resources`를 선언하지 않았다. 서버가 `failed`일 수도 있다 | `capabilities`에 선언, `mcp list`에서 `connected` 확인 |
| `opencode run`에서 리소스를 첨부할 수 없다 | `-f`는 로컬 파일 경로만 받는다. 메시지 속 `/명령`도 펼쳐지지 않는다 | TUI에서 `@`, 프롬프트는 `opencode run --command 서버:프롬프트 인자` |
| MCP 프롬프트가 사용자 입력을 검증하지 못한다 | 서버의 `prompts/get`에는 리터럴 `"$1"`이 온다. 치환은 opencode가 한다 | 인자를 본문에 그대로 끼우는 프롬프트만 쓴다 |
| 도구를 deny했는데 컨텍스트가 줄지 않는다 | `ask`는 목록에서 빠지지 않는다. 패턴이 `<서버>_<도구>` 기준이 아니다 | `deny`로, 이름은 합친 형태로. 규칙 순서(마지막 일치) 확인 |
| 파일 서버의 쓰기 도구를 deny했는데 모델이 프로젝트 파일을 고친다 (M11) | 막은 것은 MCP 도구뿐이다. 내장 `write`, `edit`, `bash`는 따로 있다 | 쓰기를 정말 막으려면 내장 도구도 deny(에이전트 권한) |
| `npx` 서버가 처음엔 `failed (Operation timed out after 30000ms)`인데 터미널에서 직접 실행하면 된다 (M10) | 첫 실행의 설치 시간이 시작 제한 30초를 넘었다(35초 지연 서버로 확인: 기본은 `failed`, `timeout: 60000`이면 `connected`) | 서버 항목에 `"timeout": 60000`. 미러 설정 확인 |
| `npx -y .`가 `ERR_MODULE_NOT_FOUND` (M10) | 로컬 폴더를 `npx`로 실행하면 `bin`만 연결하고 의존성을 설치하지 않는다 | 먼저 `npm install`, 또는 `npm pack`한 `.tgz`를 실행 |
| `npx -y /절대/경로/x.tgz`가 `Permission denied` (M10) | 절대 경로를 파일 실행 명령으로 해석한다 | `./x.tgz`, `--package=/절대/경로/x.tgz 패키지명`, `file:/절대/경로/x.tgz` |
| 파일 서버가 `sandbox`만 허용했는데 프로젝트 전체를 읽는다 (M11) | opencode가 `roots`로 프로젝트 폴더를 알려 주고, `--confine-roots` 없이는 서버가 명령줄 허용 폴더를 버리고 roots로 바꾼다 | `--confine-roots`를 붙이고 `list_allowed_directories`로 허용 범위를 직접 확인 |
| `uvx mcp-server-time==옛버전`이 `ImportError: cannot import name 'McpError'`로 죽는다 (M11) | 최상위만 고정해서 하위 의존성 `mcp`가 2.x로 설치됐다 | 호환되는 버전(`2026.11.11`)으로 올린다. 엄격하게 하려면 `uvx --exclude-newer <날짜>`나 잠금 파일(미시험) |
| `uvx --from .`로 띄운 서버가 고친 코드를 반영하지 않는다 (M12) | uv가 캐시된 빌드를 다시 쓴다. `__version__`을 올려도 마찬가지고 `--refresh-package`, `--reinstall-package`는 효과가 없었다 | `uvx --no-cache --from . ...` 또는 `pyproject.toml` 수정. 개발 중에는 `python -m` 경로 |
| 빈 캐시에서 `uvx --from .`가 `No solution found when resolving: hatchling>=1.27`로 실패한다 (M12) | 서버에 의존성이 없어도 빌드 백엔드를 인덱스에서 받아야 한다 | 인덱스나 미러 지정(`UV_DEFAULT_INDEX`). 의존성 없는 서버는 wheel 파일 배포로 피할 수 있다 |
| M10 서버에서 인자를 빼 호출했더니 `error.code -32602`가 아니라 `isError` 결과가 온다 | 공식 SDK는 인자 누락과 모르는 도구도 `isError: true` 결과로 돌려준다(본문에 `MCP error -32602: ...`) | 정상 동작. M1처럼 `error.code`로 가르던 코드는 SDK 위에서 쓸 수 없다 |
| 읽기 전용으로 감싼 CLI 도구가 파일을 만들었다 (M13) | 셸을 안 써도 값이 `-`로 시작하면 CLI가 옵션으로 읽는다. `git diff --stat`에 `--output=파일`을 넘기면 실제로 써진다 | `-`로 시작하는 값 거부, 경로 앞에 `--`. 한글 경로가 8진수로 나오면 `-c core.quotepath=false` |
| `["./bin/glossary-mcp"]`가 하위 폴더에서 실행하면 `failed` (M14) | 상대 경로는 설정 파일 위치가 아니라 opencode를 실행한 폴더 기준이다 | 프로젝트 폴더에서 실행하거나 절대 경로. `bin/glossary-mcp`가 있는지(빌드했는지) 확인 |
| 만든 실행 파일이 다른 Linux에서 안 돈다 (M14) | 기본 빌드는 동적 링크이고 필요한 glibc 심볼이 최대 `GLIBC_2.34`였다. 그보다 오래된 배포판에서는 실행되지 않을 가능성이 높다(실제로 돌려 보지는 않음). OS·CPU마다 따로 빌드해야 한다 | 정적 링크 `x86_64-unknown-linux-musl` 빌드(빌드와 `ldd`만 확인). `python build.py`가 종료 코드 2면 `cargo` 없음, 3이면 crates를 받을 수 없음 |
| 서버가 보낸 진행 알림이 화면에 안 보인다 (M15) | `notifications/progress`는 화면, 로그, `--format json` 어디에도 안 나온다. 대신 도구 호출 제한 시간을 늘려 준다 | 사용자에게 보여 줄 정보는 결과 text에 넣는다 |
| `structuredContent`로 준 값을 모델이 못 본다 / JSON 문자열로 본다 (M15) | `content`에 text가 있으면 모델은 text만 받는다. `content`가 비어 있으면 `structuredContent`를 JSON 문자열로 받는다. `outputSchema`는 모델에게 가지 않는다 | 중요한 결과는 `content`의 text에 넣고 출력 모양은 `description`에 글로 쓴다 |
| 서버가 `sampling`이나 `elicitation`을 요청하면 `-32601 Method not found` (M15) | opencode 1.19.5는 capabilities로 `{"roots": {}}`만 선언하고 그 둘을 거절한다 | 사용자에게 물어야 하면 도구 결과로 질문을 돌려주고 모델이 대신 묻게 한다 |
| 서버를 붙였더니 요청마다 토큰이 늘었다 | 도구 정의가 매 요청마다 전송된다. 12개짜리 서버 하나가 약 1,600 토큰 | 안 쓰는 서버는 `"enabled": false`, 안 쓰는 도구는 `permission` deny |
| `티켓 DB를 읽지 못했습니다` (M6) | `prepare.py`를 먼저 안 돌렸다 | `python prepare.py`. 날짜 결과가 비면 다시 실행해 기준일 갱신 |
| '지난주' 결과가 모델마다 다르다 | 모델이 지난 7일/지난 월~일 한 주로 다르게 해석한다 | `⚙` 줄의 `since`/`until` 확인, 근거 기간을 같이 말해 달라고 요청 |
| Windows에서 DB 파일이 안 지워진다 | 열린 연결이 남아 있으면 Windows는 파일 삭제를 못 한다 | 호출마다 `conn.close()` (`closing()`) |

## 플러그인 ([4장](04-plugins.md))

| 증상 | 원인 | 해결 |
|---|---|---|
| 플러그인이 아무 일도 안 한다. 화면에 오류도 없다 | 함수가 아닌 값(상수, 배열, 객체)을 export해서 **파일 전체가 로드되지 않았다**. `--print-logs`에는 `Plugin export is not a function`. (import·문법 오류는 그 로그에도 안 남는다) | export는 플러그인 함수만. 보조 함수도 export하면 플러그인으로 불리니 내보내지 않는다. 테스트는 훅을 직접 호출 |
| 플러그인이 로드됐는지 모르겠다 | 로드 실패(import/문법 오류)는 로그에도 안 남는다 | 플러그인 첫 줄에서 마커 파일에 쓴다. `opencode debug config`도 플러그인을 로드하므로 모델 없이 확인 가능. 초기화 예외는 `--print-logs`의 `failed to load plugin` |
| 플러그인에서 `@opencode-ai/plugin`을 import하는데 도구가 사라진다 | 설치가 실패했다 (레지스트리에 못 닿음). 오류 메시지 없이 사라진다 | `opencode --print-logs`에서 `background dependency install failed` 확인. 패키지 미러 지정 |
| 시작할 때마다 약 70초 멈춘다 (새 환경의 첫 시작은 약 130초) | 플러그인이 있는 `.opencode/`는 `@opencode-ai/plugin`을 npm에서 설치하려 하는데 레지스트리가 응답하지 않는다. 스킬만 있는 폴더는 거의 멈추지 않는다 | `~/.npmrc`의 `registry=` 또는 `npm_config_registry`. 프로젝트 루트 `.npmrc`는 적용되지 않는다 |
| 미러를 지정했는데도 `.opencode/` 설치가 안 된다 | 미러에 패키지나 의존 패키지가 없다 | 설치된 곳의 `.opencode/node_modules`를 복사. 단 전역 폴더 설치 지연(약 71초)은 남는다 |
| 플러그인을 고쳤는데 반영이 안 된다 | 시작할 때만 읽는다 | opencode를 다시 시작 |
| 같은 가드가 두 번 돈다. 로그가 두 줄이다 | 같은 플러그인이 전역과 프로젝트 두 곳에 있다 (파일 위치가 다르면 별개) | 한 곳에만 둔다 |
| 설정에 적은 플러그인이 안 불린다 | 키 이름을 `plugins`(복수형)로 썼다. 로컬 패키지 폴더는 `package.json`의 `main`이 없다 | `plugin`으로 고친다. `main`을 쓴다 |
| `--pure`로 하면 사라진다 | `--pure`는 외부 플러그인을 로드하지 않는다 | 의도한 동작. 플러그인이 원인인지 가를 때 쓴다 |
| 가드가 막지 않았는데 `rm -rf`가 실행됐다 | 가드 플러그인이 로드되지 않았다 | 시험은 `echo`로 문장만 출력해서. 먼저 로드 여부 확인 |
| 가드 규칙이 우회된다 | 정규식은 명령 문자열만 본다 (`python -c`, 파일 속 SQL, 심볼릭 링크) | 방어선의 일부로 쓰고 `permission`과 병행. 진짜 격리는 컨테이너나 별도 계정 |
| `git commit -m "rm -rf / 금지"`가 막힌다 | 정규식이 따옴표 안의 글자를 구분하지 않는다 | 규칙의 `unless`로 예외 추가 (P2) |
| 감사 로그가 비어 있다 | `tool.execute.after`는 성공한 호출만 기록한다. 차단된 호출은 `before`에서 직접 남겨야 한다 | 차단 기록은 `before`에서 |
| 로그 파일이 엉뚱한 폴더에 생긴다 | `directory`는 opencode를 실행한 폴더다 | 실행 폴더 확인 |
| 감사 로그에 비밀이 남았다 | 인자 일부가 그대로 기록된다 (X2는 300자) | 내용은 길이만 기록, 알려진 패턴은 가린다. 로그 폴더 권한 제한 |
| 알림이 안 울린다 | `opencode run`은 끝나면 자식 프로세스를 정리한다. 토스트는 Windows 방해 금지 설정이 켜져 있으면 안 보인다. WSL의 Linux용 opencode는 Windows 화면에 알림을 못 띄운다 | TUI나 `opencode serve`에서 확인. `notify.log`의 첫 줄(이벤트 수신)만 본다 |
| 알림이 두 번 온다 | `session.idle`과 `session.status`(idle)가 같은 순간에 모두 온다 | `session.idle`만 처리 |
| `permission.updated`/`permission.ask`가 안 온다 | SDK 타입에만 있다. 1.19.5는 `permission.asked`/`permission.replied` 이벤트를 보낸다. `permission.ask` 훅은 호출되지 않았다 | `event` 훅에서 `permission.asked`. 이벤트 이름은 직접 기록해 확인 |
| `shell.env`가 안 먹는다 | `bash` 도구가 호출될 때만 불린다. Windows 셸에서 `$APP_ENV`로 읽었다 | `$env:APP_ENV`로 읽거나 `python -c`로 확인. 내 터미널에는 적용되지 않는 것이 정상 |
| 압축 훅에서 압축이 실패한다 | `experimental.session.compacting` 안의 예외는 압축을 통째로 실패시킨다 | `try/catch`로 감싸 로그만 남긴다 |
| 압축 훅이 업데이트 뒤 아무 일도 안 한다 | 실험적 훅이라 이름/모양이 바뀔 수 있다 | `logs/compaction.log`가 늘어나는지 확인, `check.py` 재실행 |
| 시스템 프롬프트 주입 블록이 업데이트 뒤 사라졌거나 값이 오래됐다 (P12) | `experimental.chat.system.transform`은 이름이나 동작이 바뀔 수 있다. 값은 git 조회 캐시(기본 5초) 때문에 최대 그 시간 동안 실제와 다를 수 있다 | 예제의 `check.py` 재실행, `logs/context-injection.log` 확인. 정확해야 하는 판단은 실행 시점에 다시 확인 |
| `output.context`에 넣었는데 반영이 안 된다 | `output.prompt`를 설정하면 `context`는 무시된다 | 덧붙이기는 `context.push`만, 프롬프트 교체는 `prompt` |
| 커스텀 도구가 내장 도구를 바꿔 버렸다 | 내장과 같은 이름으로 등록하면 덮어쓴다 | 겹치지 않는 이름 |
| 플러그인 파일 옆에 둔 보조 파일/테스트가 로드되어 오류가 난다 | `.opencode/plugins/`의 모든 `.js`가 플러그인으로 로드된다 | 보조 모듈과 테스트는 그 폴더 밖(`tests/`) |
| `node tests/...`가 안 돈다 | Node가 없다. `check.py`는 경고만 내고 건너뛴다 | opencode 실행에는 Node가 필요 없다. 단위 테스트에만 필요 |
| X2: 가드가 `bash`의 쓰기를 못 막는다 | 가드는 `write`/`edit`/`apply_patch`만 검사한다 | `permission`을 함께 쓴다 |
| after 훅에서 예외를 던졌더니 파일은 써졌는데 모델은 실패로 받고 같은 일을 다시 시도한다 (P9) | `tool.execute.after`는 파일이 이미 써지고 formatter까지 끝난 뒤에 불린다. throw하면 모델은 던진 메시지만 받는다 | after 훅 전체를 `try/catch`로 감싸고 로그만 남긴다 |
| `formatter`가 파일을 고쳤는데 모델이 모른다. 다음 `edit`가 맞지 않는다 (P9) | 내장 formatter는 모델에게 알리지 않고, 깨진 JSON 같은 실패도 조용히 건너뛴다 | 모델이 읽어야 할 검사 결과는 `tool.execute.after`로 도구 결과에 붙인다 |
| main 브랜치에서 `git commit`이 `[branch-guard:protected-branch]`로 막힌다 (P10) | 의도된 동작이다. `git init` 직후 첫 커밋도 브랜치가 `main`이면 막힌다 | `git switch -c <type>/<name>` 후 다시 커밋(변경한 파일은 따라옴) |
| 브랜치 가드를 통과해 main에 커밋이 생겼다 (P10) | `git merge`, `cherry-pick`, `revert`, `am`, `rebase`, 스크립트 안의 git 호출, git 별칭은 보지 않는다. 가드는 실수 방지이지 보안 경계가 아니다 | 원격의 branch protection을 함께 쓴다 |
| 마스킹했는데 비밀이 세션 저장소나 파일에 남아 있다 (P11) | 가려지는 것은 모델에게 가는 글자(와 훅에서 같이 가린 `metadata`)뿐이다. 세션 DB의 `event` 테이블 `running` 기록과 opencode의 `tool-output/` 전체 사본에는 원본이 남는다 | 보호 범위를 이해하고 쓴다. 비밀 파일을 못 읽게 하려면 `tool.execute.before`(P1) |
| 마스킹 플러그인이 MCP 도구 결과를 가리지 못한다 (P11) | MCP 도구의 `output`은 `{content: [{type, text}]}`뿐이라 `output.output`만 바꾸면 반영되지 않는다 | `output.content[].text`도 처리한다 |
| 가려진 글자(`***`)로 파일을 고치려다 `Could not find oldString`으로 실패한다 (P11) | 모델은 원문을 모른다. `write`로 통째로 다시 쓰면 `***`가 실제 파일에 들어갈 수 있다 | 비밀이 든 파일은 통째로 다시 쓰지 않게 한다 |

## Windows

opencode 1.19.5를 Windows에서 쓸 때 만나는 문제를 모았습니다. 확인은 Windows 11(한국어, 코드 페이지 949)에서 했습니다.

### bash 도구는 PowerShell 5.1입니다

Git for Windows가 설치되어 있어도 `bash` 도구는 Git Bash도 cmd도 아닌 **Windows PowerShell 5.1**(`powershell.exe`)로 명령을 실행합니다. `OPENCODE_GIT_BASH_PATH`를 지정해 봤지만 한 번의 시험에서는 셸이 바뀌지 않았습니다. 이 버전에서 Git Bash로 바꾸는 방법은 확인하지 못했습니다.

| bash에서는 되는 것 | PowerShell 5.1에서는 |
|---|---|
| `a && b` | 문법 오류 |
| `$APP_ENV`, `export X=1` | `$env:APP_ENV`, `$env:X = "1"` (`$APP_ENV`는 빈 값인 PowerShell 변수) |
| `date +%F` | `Get-Date -Format yyyy-MM-dd` |
| `2>/dev/null`, `\| head`, `wc -l`, `uname` | 없음 (인식되지 않습니다) |
| `cat file` | `cat`은 `Get-Content`의 별칭 |
| `$?` | `$LASTEXITCODE` (종료 코드 확인) |

그래서 스킬이 시키는 명령은 `python <스킬 폴더>/scripts/x.py 인자` 한 줄로 쓰고, 셸 문법이 필요한 일은 스크립트 안으로 옮깁니다. 모델이 쓰는 위험 명령도 `Remove-Item`, `Get-Content` 같은 PowerShell 문법이 되므로, 가드 플러그인(P1, P2)은 둘 다 봅니다. 스킬 폴더 경로는 `C:\...\.opencode\skills\<이름>`처럼 역슬래시로 오지만 `/`로 바꿔 넘겨도 Python이 처리합니다. 출력 줄 끝은 `\r\n`입니다.

### 인코딩 (cp949)

| 증상 | 해결 |
|---|---|
| MCP 서버가 보낸 한글이 `�ȳ��ϼ���`로 깨진다. `mcp list`는 `connected` | 서버 맨 위에 `sys.stdout.reconfigure(encoding="utf-8", newline="\n")`, stdin/stderr도 같이. 파일은 `open(..., encoding="utf-8")` |
| 스크립트 출력 한글이 깨진다 | 스크립트가 stdout을 UTF-8로 고정 |
| `Get-Content`로 읽은 UTF-8 파일(BOM 없음)이 깨진다 | `Get-Content 파일 -Encoding UTF8` |
| 파이프로 넘길 때 한글이 깨진다 | `$env:PYTHONUTF8=1` |
| PowerShell의 오류 메시지가 깨져 보인다 | 한국어 Windows의 PowerShell 메시지는 cp949라 터미널에 따라 그렇다. 동작에는 영향 없음 |

### python과 python3

Windows에서는 `python`, Linux에서는 `python3`가 일반적입니다. 예제의 `opencode.json`과 `SKILL.md`는 `python`으로 적혀 있습니다. Linux에서 `python` 명령이 없으면 `command`를 `["python3", ...]`로 바꾸고, 스킬에는 "`python`이 없으면 `python3`" 한 줄을 둡니다. 가상환경의 파이썬 경로도 다릅니다(Windows `.venv\Scripts\python.exe`, Linux `.venv/bin/python`).

### 경로와 환경 변수

| 항목 | 내용 |
|---|---|
| 전역 설정 | `%USERPROFILE%\.config\opencode\opencode.json` (Windows에서 `XDG_CONFIG_HOME` 없이 쓸 때의 기본 위치는 스킬 폴더에 대해서는 확인하지 못했음. `opencode debug paths`로 확인) |
| 사용자 `.npmrc` | `%USERPROFILE%\.npmrc` |
| `$env:이름 = "값"` | **그 PowerShell 창에서만** 유효. 다른 창이나 이미 떠 있는 opencode에는 안 보임 |
| 환경 변수 정리 | `Remove-Item Env:이름` |
| 로그 경로 | `opencode debug paths`의 `log` 줄. Windows 기본 위치는 확인하지 못했음 |
| `file:` 주소 | `file:///C:/work/...` 형태 |
| 로그에 찍히는 경로 | 역슬래시가 두 겹(`\\`)으로 나올 수 있음. 비교할 때 `/`로 정규화 |
| `.git` 폴더 삭제 | 읽기 전용 파일 때문에 거부되면 `Remove-Item -Recurse -Force 폴더` |
| 스크립트에서 `npx` 띄우기 (M11) | Windows의 `npx`는 `npx.cmd`라서 직접 쓴 스크립트(`subprocess` 등)에서 이름만으로는 실행되지 않는다. `shutil.which("npx")`로 전체 경로를 찾아 넘긴다. opencode가 띄울 때는 `["npx", ...]` 그대로 된다 |
| 실행 파일 서버의 `command` (M14) | `.exe`를 붙이지 않아도 된다. 교차 빌드한 `bin\glossary-mcp.exe`를 `["./bin/glossary-mcp"]`로 찾아 `connected`였다. Windows에서 `cargo build`로 직접 빌드하는 과정은 확인하지 못했다 |
| 열린 SQLite 연결 | 닫지 않으면 DB 파일을 못 지움 |
| 방화벽 | `127.0.0.1` 바인딩에서는 보통 안 뜨고, `0.0.0.0`으로 열면 허용 여부를 묻는 창이 뜰 수 있음 |
| 한글 글꼴 | HTML 리포트는 `Malgun Gothic` 순으로 사용 |

`opencode mcp list` 출력은 Windows에서 세로선을 `│` 대신 `|`로 그립니다. 읽는 데는 영향이 없습니다.

TUI 동작(`/skills` 선택창, `@` 자동완성, `ask` 확인 창)은 Linux에서만 확인했고 Windows TUI는 확인하지 못했습니다. `opencode run`, `opencode debug`, 서버 `/command`는 Windows에서도 `check.py`로 확인했습니다.

## 모델이 안 움직일 때

예제를 따라 했는데 모델이 응답하지 않거나, 멈춘 것처럼 보일 때입니다.

### 무료 모델의 한도가 바닥났을 때

가장 흔하고 가장 알기 어렵습니다. 한도가 찬 무료 모델(`opencode/big-pickle` 등)은 **조용히 멈춥니다.** 화면에 오류가 없고, `opencode run`이 끝나지 않고 재시도만 합니다. 단순한 한 단어 프롬프트도 수 분 안에 끝나지 않습니다.

`Free usage limit reached`라는 이유는 **`--print-logs`를 붙여야만** 보입니다.

PowerShell:
```powershell
opencode run --print-logs --log-level ERROR -m opencode/big-pickle "안녕"
```
Linux bash:
```bash
opencode run --print-logs --log-level ERROR -m opencode/big-pickle "안녕"
```

이 문구가 보이면 한도가 찬 것입니다. 다른 모델로 바꾸거나 시간이 지난 뒤 다시 시도하세요. 이 저장소의 일부 검증(실제 모델로 비율을 재는 S5a, 실제 모델의 요약 확인 P7 등)이 "미검증"으로 남은 이유이기도 합니다. 발표 중이라면 각 예제 README의 "기대 결과"를 보여 줍니다. 한도를 쓰지 않고 동작을 확인하는 가짜 모델 기반 검사는 `python check.py`(모델 없음)입니다.

### `opencode run`이 끝나지 않을 때: stdin

`opencode run`은 **stdin이 열려 있으면 멈춥니다.** 스크립트나 자동화에서 띄울 때 stdin을 닫아 주세요. 이 저장소의 검증 도구는 `subprocess.run(..., stdin=subprocess.DEVNULL)`을 씁니다. bash에서는 `opencode run ... < /dev/null`이 같은 효과입니다. PowerShell 5.1에서의 동등한 방법은 확인하지 못했습니다.

### `opencode run`은 프로젝트 폴더를 $PWD에서 읽습니다

`opencode run`은 프로세스의 현재 폴더(cwd)가 아니라 환경 변수 **`PWD`** 를 프로젝트 폴더로 삼는 것으로 관찰됐습니다(Linux). Python `subprocess.run(cwd=...)`만 쓰면 `PWD`가 부모의 폴더로 남아, 엉뚱한 폴더의 설정과 스킬로 실행되거나 `Unexpected server error`가 납니다. 스크립트에서 띄울 때는 `env["PWD"]`도 작업 폴더로 맞추세요. 터미널에서 직접 실행할 때는 신경 쓰지 않아도 됩니다. `opencode debug ...`는 영향을 받지 않았습니다.

### 그 밖에

| 증상 | 원인 | 해결 |
|---|---|---|
| 모델이 도구/스킬을 안 쓰고 지어낸 답을 한다 | 스킬이 안 열렸다 (`→ Skill "이름"` 줄이 없다). 도구 설명이 모호하다 | 이름을 직접 말한다. description과 도구 설명을 구체적으로 |
| 모델 설정이 없어 시작이 안 된다 | 사용할 모델이 지정되지 않았다 | `-m opencode/big-pickle`처럼 무료 모델을 지정 |
| 같은 프롬프트인데 결과가 매번 다르다 | 모델 출력은 확률적이다 | 숫자 하나보다 여러 번 돌린 비율을 본다 |
| 모델이 "스테이징된 변경이 없습니다"라고 한다 (S1a) | 예제 폴더가 아니라 상위 저장소에서 실행했다 | `sandbox/`로 이동해 실행 |
| 가짜 모델 서버 포트가 겹친다 | 예제는 운영체제가 고른 빈 포트를 쓰므로 보통 겹치지 않는다. 고정 포트(M4의 3917, M5의 3918)는 겹칠 수 있다 | `--port`로 바꾼다 |

다음: [00-concepts](00-concepts.md)로 돌아가 개념을 복습하거나, [examples/README.md](../../examples/README.md)에서 예제 목록을 확인하세요.
