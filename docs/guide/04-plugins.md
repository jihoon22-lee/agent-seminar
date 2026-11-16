# 4. 플러그인: 모델이 무엇을 하든 항상 실행되는 코드

이 문서는 세미나 6장 "플러그인"을 글로 옮긴 것입니다. 플러그인의 생김새, 파일을 통째로 건너뛰게 만드는 export 함정, 훅이 불리는 순서와 도구별 `args` 키, 이벤트, 예제 P1~P8, `permission`과의 선택 기준, 실험적 압축 훅, 불러오는 방법을 다룹니다.
모든 내용은 **opencode 1.19.5** 기준입니다.

관련 예제: [P1 .env 보호](../../examples/03-plugins/p1-env-guard/) · [P2 위험한 명령 차단](../../examples/03-plugins/p2-dangerous-command-guard/) · [P3 감사 로그](../../examples/03-plugins/p3-audit-log/) · [P4 알림](../../examples/03-plugins/p4-notify-on-idle/) · [P5 셸 환경 변수](../../examples/03-plugins/p5-shell-env/) · [P6 커스텀 도구](../../examples/03-plugins/p6-custom-tool/) · [P7 압축 훅](../../examples/03-plugins/p7-compaction-context/) · [P8 불러오는 방법](../../examples/03-plugins/p8-load-methods/) · [X2 종합](../../examples/04-combined/x2-incident-analysis/)

## 플러그인은 훅을 돌려주는 함수입니다

`.opencode/plugins/`에 JS/TS 파일을 두면 설정 없이 자동으로 로드됩니다. 파일은 **함수를 export** 하고, 그 함수는 **훅 객체를 돌려줍니다.** 돌려주는 객체의 키가 훅 이름입니다.

```js
// P5 shell-env.js 에서 줄인 것
export const ShellEnv = async ({ directory }) => {
  const injected = { APP_ENV: "dev" }
  return {
    "shell.env": async (input, output) => {
      Object.assign(output.env, injected)
    },
  }
}
```

플러그인 함수가 받는 첫 번째 인자는 `{ client, project, directory, worktree, serverUrl, $, experimental_workspace }`입니다. 두 번째 인자 `options`는 설정에서 `[경로, 옵션]` 형태로 넘긴 값입니다. git 저장소가 아닌 곳에서는 `project.id`가 `"global"`, `worktree`가 `/`로 나옵니다. 플러그인은 opencode에 내장된 **Bun 런타임** 안에서 실행됩니다.

스킬과 MCP는 모델이 고를 때만 쓰이지만, 플러그인은 **조건이 맞으면 항상 실행됩니다.** 그래서 "반드시 지켜야 하는 규칙"과 "항상 일어나야 하는 자동화"에 씁니다. 대신 opencode 전용입니다.

## export 함정: 함수가 아닌 것을 내보내면 파일 전체가 사라집니다

가장 오래 헤맨 함정입니다. opencode는 모듈이 export한 **것을 모두 플러그인 함수로 호출**합니다.

- 상수, 배열, 객체처럼 **함수가 아닌 값**을 하나라도 export하면 **그 파일의 플러그인이 모두 로드되지 않습니다.** 평소 실행 화면에는 아무 표시가 없고, `opencode --print-logs`로 실행해야 `level=ERROR message="failed to load plugin" ... error="Plugin export is not a function"`이 보입니다.
- 보조 **함수**를 export하면 파일은 로드되지만, 그 함수도 플러그인으로 한 번 불립니다. 의도하지 않은 코드가 실행되니 역시 export하지 않습니다.

```js
export const RULES = [ ... ]          // 함수가 아니라서 이 파일 전체가 로드되지 않는다
export const MyPlugin = async () => ({ ... })
```

- **export는 플러그인 함수만** 합니다. 도우미 함수와 상수는 파일 안에서만 씁니다.
- 테스트를 위해 내보내고 싶어지면 export하지 말고, 테스트가 플러그인을 불러와 훅을 직접 호출하게 하세요. (P1, P2의 `tests/*.test.mjs`가 그렇게 합니다.)
- `.opencode/plugins/`의 **모든 `.js`가 플러그인으로 로드**됩니다. 보조 모듈이나 테스트 파일을 그 폴더에 두지 마세요.
- 로드 실패는 대부분 조용합니다. 함수가 아닌 export와 초기화 중 예외는 `--print-logs`에만 보이고, `import` 오류, 문법 오류, 잘못된 진입점은 그 로그에도 안 남습니다. 플러그인 첫 줄에서 마커 파일에 한 줄을 쓰게 해 두면 "로드 자체가 안 된 건지, 훅이 안 불린 건지"를 가를 수 있습니다. (이 저장소의 플러그인은 `logs/plugin-load.log`에 씁니다.) 플러그인 함수가 **초기화 중 예외**를 던지면 `opencode --print-logs`에서 `level=ERROR message="failed to load plugin"`이 보입니다.
- 플러그인을 고친 뒤에는 opencode를 다시 시작해야 합니다.

## 첫 실행: @opencode-ai/plugin 자동 설치

`.opencode/`가 있는 폴더에서 처음 시작하면 opencode가 `@opencode-ai/plugin`을 npm에서 `.opencode/` 안에 설치하려 합니다(`package.json`, `node_modules/`, 자체 `.gitignore` 생성). 전역 설정 폴더(`~/.config/opencode/`)에서도 같은 설치가 일어납니다.

| 상황 | 결과 |
|---|---|
| 레지스트리에 닿음 | 첫 시작 6~10초, 이후 1초 안팎 |
| 연결이 거부/차단되어 응답 없음 | 플러그인(`.opencode/plugins/*.js`)이 있는 폴더는 **시작할 때마다 약 70초 멈춘 뒤** 계속 진행(새 환경의 첫 시작은 약 130초, 패킷을 조용히 버리는 레지스트리는 200초 넘게). 스킬만 있는 폴더는 설치를 시도하지만 눈에 띄게 멈추지 않았다(`run` 4초). 설치가 안 됐으므로 `@opencode-ai/plugin`을 import하는 플러그인(P6의 `tool()` 등)이 오류 메시지 없이 사라진다 |
| 응답은 하지만 패키지가 없음(404) | 지연 없이 바로 실패, 마찬가지로 조용히 사라진다 |

도구가 안 보이면 `opencode --print-logs`로 실행해 `message="background dependency install failed"` 줄을 찾으세요. 일반 실행에는 출력되지 않습니다.

인터넷이 막힌 환경에서는 **패키지 미러**를 지정합니다. 아래 중 하나면 됩니다. 주소는 예시이니 실제 미러 주소로 바꾸세요.

1. 사용자 `.npmrc` (가장 무난함). Linux `~/.npmrc`, Windows `%USERPROFILE%\.npmrc`에 `registry=https://registry.example.com/`
2. 환경 변수 `npm_config_registry` (한 번만 쓸 때)
3. `.opencode/.npmrc` (`.opencode/`의 의존성 설치에만 적용)

프로젝트 루트의 `.npmrc`는 **적용되지 않습니다**(확인함). 레지스트리에 전혀 닿지 않는 환경에서는 `.opencode/node_modules`를 미리 채워 두면 프로젝트의 커스텀 도구는 등록되지만, 전역 폴더의 설치가 계속 실패해 **시작할 때마다 약 71초씩 멈춥니다.** 이 지연을 없애려면 접근 가능한 미러를 지정하는 것이 유일한 방법입니다. 인터넷이 막힌 환경에서는 패키지 미러 설정을 먼저 하세요.

`--pure`로 실행하면 이 자동 설치도 하지 않아 시작이 빨라집니다(1~2초).

## 훅이 불리는 순서

`bash` 명령 하나가 실행될 때 이 순서입니다.

```
tool.execute.before    검사, 인자 수정, 차단
        ↓
permission 확인        ask면 사용자에게 묻는다 (이벤트 permission.asked)
        ↓
shell.env              환경 변수 주입
        ↓
명령 실행
        ↓
tool.execute.after     결과 기록, 후처리
```

- 호출 순서를 직접 관찰했습니다: `tool.execute.before` → `permission.asked` 이벤트 → `shell.env` → 실행 → `tool.execute.after`.
- **`before`가 권한 확인보다 먼저**입니다. 그래서 플러그인이 막으면 사용자에게 묻지도 않고 끝납니다. `before`에서 `throw`하면 **`--auto`로 실행해도 차단**되고, 던진 메시지가 모델에게 오류로 전달됩니다.
- `shell.env`는 `bash` 도구가 호출될 때만 불립니다(`read`/`edit`에서는 안 불립니다).
- `tool.execute.after`는 도구가 **성공적으로 끝난 뒤**에 불립니다. `before`에서 막힌 호출은 기록되지 않으므로 차단 기록은 `before`에서 직접 남겨야 합니다.
- 훅은 내장 도구뿐 아니라 스킬(`skill` 도구)과 MCP 도구 호출에도 불립니다([X2](../../examples/04-combined/x2-incident-analysis/)에서 감사 로그에 `skill`, `tickets_*`, `read`, `write`가 모두 남는 것을 확인). 단 MCP 도구의 `after` 결과는 `output.output` 문자열이 아니라 MCP 원형(`output.content`)으로 올 수 있습니다.

### 오류 메시지는 행동 지침이어야 합니다

`throw new Error(...)`의 메시지가 모델의 다음 행동을 정합니다. "왜 막혔는지 + 대신 무엇을 하라"를 적으면 모델이 같은 시도를 반복하지 않고 방향을 바꿉니다. P1이 `.env`를 막으며 "변수 이름과 형식이 필요하면 `.env.example`을 읽으세요"라고 안내하는 이유입니다.

### 도구별 `output.args` 키 (1.19.5에서 관찰)

`input`에는 `tool`, `sessionID`, `callID`가 들어 있고, `tool.execute.after`에는 `args`도 있습니다.

| 도구 (`input.tool`) | `output.args`의 키 |
|---|---|
| `read` | `filePath` |
| `write` | `filePath`, `content` |
| `edit` | `filePath`, `oldString`, `newString` |
| `grep` | `pattern`, `path` (`include`가 올 수도 있음) |
| `glob` | `pattern`, `path` |
| `bash` | `command`, `description` |
| `apply_patch` | `patchText` (모델에 따라 노출되는 도구) |

`apply_patch`는 일부 모델에서만 제공됩니다. 이 도구가 쓰는 파일은 `patchText` 안의 `*** Update File: 경로` 같은 줄에서 읽어야 하는데, 이번 확인에 쓴 모델에서는 노출되지 않아 단위 테스트로만 검증했습니다. `tool.execute.after`의 `output`에는 `title`, `output`(본문 문자열), `metadata`가 있습니다.

### 훅 목록

| 훅 | 할 수 있는 일 |
|---|---|
| `tool.execute.before` | 도구 실행 전 검사, 인자 수정, 차단 |
| `tool.execute.after` | 실행 결과 기록, 후처리 |
| `shell.env` | `bash` 도구 명령에 환경 변수 주입 |
| `event` | opencode 안의 모든 이벤트 수신 |
| `tool` | 모델이 부를 새 도구 등록 |
| `config`, `chat.*` | 설정 변경, 메시지 가공 (이 저장소 예제에서는 다루지 않음) |
| `experimental.session.compacting` 등 | 실험적 훅 (아래 참고) |

`permission.ask` 훅이 훅 목록에 있지만, 1.19.5에서는 권한 요청이 발생해도 **한 번도 호출되지 않았습니다.** 권한 요청은 `event` 훅의 `permission.asked`로 받으세요.

## 이벤트

`event` 훅은 opencode 안에서 일어나는 모든 일을 받습니다. 모델 실행 중 받은 type을 전부 기록한 결과입니다 ([P4](../../examples/03-plugins/p4-notify-on-idle/)).

| type | 언제 |
|---|---|
| `session.idle` | 응답이 모두 끝나고 입력을 기다리는 상태가 될 때 (완료 알림에 사용) |
| `permission.asked` | 도구 실행 전에 사용자 승인이 필요할 때 (`permission`, `patterns`, `tool` 등) |
| `permission.replied` | 승인/거부가 되었을 때 (`reply`: `once`/`reject` ...) |
| `session.status` | 상태가 바뀔 때 (`busy` 또는 `idle`) |
| `session.created` / `session.updated` / `session.diff` | 세션 생성, 갱신 |
| `message.updated` / `message.part.updated` / `message.part.delta` | 메시지와 출력이 스트리밍될 때 |
| `plugin.added`, `catalog.updated`, `reference.updated`, `integration.updated` | 시작 시 내부 상태 |

알아 둘 점입니다.

- **SDK 타입 정의에는 `permission.updated`가 있지만, 1.19.5가 실제로 내보내는 것은 `permission.asked`/`permission.replied`입니다.** 타입만 믿지 말고 이벤트를 직접 기록해 보세요. P4는 `NOTIFY_LOG_ALL_EVENTS=1`로 받은 type 전체를 `logs/events.log`에 남기는 진단 모드를 제공합니다. 새 버전에서 이벤트 이름이 바뀌면 이것으로 확인하세요.
- `session.status`도 `idle`을 알리지만 `session.idle`과 같은 순간에 둘 다 옵니다. 둘 다 처리하면 알림이 두 번 가므로 `session.idle`만 씁니다.
- 권한 설정이 `ask`이면 `--auto`로 실행해도 `permission.asked` 이벤트는 발생합니다(자동으로 `once` 승인).
- 서브에이전트(`task` 도구) 세션이 끝날 때마다 알림이 오지 않게 하려면 `session.created`의 `info.parentID`를 기억해 두었다가 건너뜁니다. 이 부분은 단위 테스트로만 확인했고 실제 `task` 실행으로는 확인하지 못했습니다.
- **`opencode run`은 끝나자마자 자식 프로세스를 정리합니다.** 알림 프로세스도 같이 끊깁니다. 알림은 TUI나 `opencode serve`처럼 오래 떠 있는 프로세스에서만 울립니다. `run`으로 시험할 때는 로그 파일의 첫 줄(이벤트를 받았다는 기록)만 보세요. 그래서 P4는 외부 프로세스를 띄우기 **전에** 로그부터 동기 방식으로 씁니다.
- Windows에서 PowerShell을 `detached`로 직접 띄우면 콘솔이 없어 아무 일도 하지 않았습니다. `cmd.exe /c start "" /b powershell.exe -EncodedCommand ...`로 띄워 해결했습니다. 소리와 토스트가 실제로 나오는지는 사람이 확인해야 하므로 `sound ok`/`toast ok` 기록까지만 확인했습니다.

## 예제 P1~P8

### P1. 비밀 파일을 읽지 못하게: `tool.execute.before`

`read`, `write`, `edit`의 경로가 `.env`, `.env.*`이면 차단하고, `bash`의 `cat .env`, `Get-Content .env` 같은 우회도 막습니다. 변수 이름은 알아야 일을 하므로 `.env.example`은 허용합니다. Windows 경로(`C:\...\.env`)도 같은 코드로 처리합니다(`path.win32.basename`은 `/`와 `\`를 모두 구분자로 취급). 차단 30가지, 허용 21가지 사례를 `node` 단위 테스트로 고정했습니다.

bash 판정은 `.env` 토큰에 경계를 두고, `cat`, `type`, `Get-Content`, `grep`, `python -c` 같은 "읽는 명령"이 함께 있을 때만 막습니다. 그래서 `os.environ`, `$env:APP_ENV`, `echo .env >> .gitignore`는 통과합니다. `python -c`로 파일 이름을 문자열 조합해서 여는 식의 우회, 심볼릭 링크는 정규식으로 막을 수 없으므로 **방어선의 일부**일 뿐입니다. 진짜 격리가 필요하면 비밀이 없는 환경(컨테이너, 별도 계정)에서 실행하세요.

### P2. 위험한 명령 차단: 규칙 표를 코드로

`rm -rf /`, `git push --force`, `git reset --hard`, `DROP TABLE` 같은 되돌릴 수 없는 명령을 `bash` 실행 직전에 막습니다. 핵심은 `{ id, pattern, message }`로 이루어진 **규칙 표**입니다. 한 줄을 추가하면 새 위험 명령을 막고, `tests/matcher.test.mjs`에 막아야 하는 것과 막으면 안 되는 것을 함께 적습니다(47가지 차단, 36가지 허용). 옵션 순서(`rm -rf`, `rm -fr`, `rm -r -f`), `;` 뒤의 명령, PowerShell 문법(`Remove-Item -Recurse -Force C:\`)까지 봅니다. `git push --force-with-lease`와 `git clean -n` 같은 안전한 변형은 허용합니다.

한계도 있습니다. 명령 문자열만 보므로 `psql -f cleanup.sql` 속의 `DROP TABLE`이나 `python -c "shutil.rmtree('/')"`는 못 막고, `git commit -m "rm -rf / 금지"`처럼 따옴표 안의 글자도 막힐 수 있습니다. 정규식 필터는 실수 방지용이지 보안 경계가 아닙니다. 차단 시험을 진짜 `rm -rf /`로 하지 마세요. 플러그인이 로드되지 않았다면 실제로 실행됩니다. `echo`로 문장만 출력하는 방식이 안전합니다.

### P3. 에이전트가 한 일을 남기기: `tool.execute.after`

도구가 어떤 인자로 실행되고 결과가 얼마나 컸는지 `logs/audit.jsonl`에 한 줄(JSON)씩 쌓고, `summarize_audit.py`가 도구별 횟수와 시간순 타임라인으로 요약합니다. "에이전트가 어젯밤에 뭘 했지?"에 답할 수 있어야 팀에서 안심하고 맡길 수 있습니다. 모델과 상관없이 항상 남아야 하므로 플러그인의 일입니다.

- **파일 내용과 출력 본문은 기본적으로 남기지 않습니다.** 내용을 남기기 시작하면 감사 로그가 `.env`보다 위험한 비밀 저장소가 됩니다. 경로는 그대로 두고, `content`/`oldString`/`newString`은 `<N자 생략>`으로 길이만, 도구 출력은 `outputLength`만 남깁니다.
- `command` 안의 `Bearer <값>`, `password=<값>`, `--token <값>` 등은 `***`로 가립니다. 정규식 기반이라 모든 비밀을 잡는다고 보장할 수 없습니다.
- 크기가 `AUDIT_MAX_BYTES`(기본 1 MiB)를 넘으면 파일을 돌려 쓰고(`audit.<날짜시각>.jsonl`), 최근 `AUDIT_KEEP`개(기본 5)만 남깁니다.
- 훅 안의 모든 작업은 `try/catch`로 감쌉니다. **감사 로그 실패가 에이전트 작업을 멈추게 해서는 안 됩니다.**
- 기록 파일은 opencode를 실행한 폴더 기준 `logs/`입니다.

### P4. 알림: `event` 훅과 외부 명령

`session.idle`(작업 완료)과 `permission.asked`(승인 대기)에 소리와 알림을 보냅니다. 이벤트를 받아 바깥 프로그램을 실행하는 패턴은 메신저 전송, 로그 수집, 빌드 트리거로 확장됩니다. Windows는 소리와 토스트, Linux는 `notify-send`(없으면 터미널 벨)입니다. 알림에 들어가는 `patterns`에는 실행하려는 명령이 그대로 있으므로 길이를 80자로 자르는 부분을 유지하세요. WSL에서 Linux용 opencode를 쓰면 Windows 화면에는 알림이 뜨지 않습니다.

### P5. 에이전트의 셸에만 환경 변수 넣기: `shell.env`

프록시 주소, 사설 인증서 경로(`REQUESTS_CA_BUNDLE`), 실행 환경 표시(`APP_ENV`)처럼 모두가 같아야 하는 값을 **에이전트가 실행하는 셸 명령에만** 넣습니다. 내 터미널과 시스템 환경은 그대로입니다. `output.env`는 처음에 빈 객체이고, 넣은 키만 기존 환경 위에 덮어씌워지므로 `Object.assign(output.env, {...})`로 넣을 값만 적습니다. 경로는 `directory`와 `path.join`으로 절대 경로를 만드세요. 상대 경로는 명령이 실행되는 `cwd`에 따라 달라집니다.

비밀(API 키)은 넣지 마세요. 모델이 `env`/`printenv`로 읽을 수 있어 모델 입력으로 전달될 수 있습니다. MCP 서버에는 `bash` 도구용 `shell.env`가 아니라 `environment` 설정을 씁니다. Windows에서는 `$APP_ENV`가 빈 값이므로 `$env:APP_ENV`로 읽어야 해서, 예제는 `python show_env.py`로 확인합니다.

### P6. 커스텀 도구 등록: `tool` 훅

플러그인은 훅만 다는 것이 아니라 **모델이 부를 수 있는 새 도구**도 등록합니다. 별도 서버도 프로토콜도 필요 없습니다.

```js
import { tool } from "@opencode-ai/plugin"

export const TeamTools = async ({ directory }) => {
  return {
    tool: {
      business_days: tool({
        description: "두 날짜 사이의 영업일 수(토·일 제외)를 센다. ...",
        args: {
          from: tool.schema.string().describe("시작일, YYYY-MM-DD"),
          to: tool.schema.string().describe("종료일, YYYY-MM-DD"),
        },
        async execute(args) { ... return `...영업일: ${count}일` },
      }),
    },
  }
}
```

- `tool: { 이름: tool({...}) }`의 **키가 곧 모델에게 보이는 도구 이름**입니다(MCP처럼 서버 이름 접두사가 붙지 않습니다).
- `description`이 모델이 "언제 쓸지" 판단하는 유일한 근거입니다. `args`는 `tool.schema`(zod)이고 `.describe()` 설명이 함께 전달됩니다. `execute(args, context)`는 문자열이나 `{ title, output, metadata }`를 반환합니다. 상대 경로는 `process.cwd()`가 아니라 `context.directory` 기준으로 푸세요.
- 도구가 예외를 던지면 `✗ ... failed`와 오류 메시지가 보이고 같은 메시지가 모델에게 갑니다. 인자가 없는 도구는 transcript에 `Unknown`으로 찍히는데 오류가 아니라 표시 방식입니다.
- **내장 도구와 같은 이름으로 등록하면 내장 도구를 덮어씁니다.** (`webfetch`로 등록했더니 모델이 부른 `webfetch`가 플러그인 쪽으로 실행됨)
- `permission`의 `"uuid_v4": "deny"`면 그 도구가 모델에게 아예 안 보입니다. `--pure`로 실행하면 커스텀 도구가 사라집니다.
- `.opencode/tools/<파일>.js`에 `export default tool({...})`하는 방법도 있습니다. 이때는 **파일 이름이 도구 이름**입니다.

**플러그인 도구와 MCP 도구**의 선택 기준은 한 줄입니다. "다른 에이전트도 쓸 도구인가?" 그렇다면 MCP, 아니고 opencode 안의 가벼운 기능이라면 플러그인 도구입니다.

| | 플러그인 커스텀 도구 | MCP 도구 |
|---|---|---|
| 실행 위치 | opencode 프로세스 안(Bun) | 별도 프로세스 또는 원격 서버 |
| 이름 | `business_days` | `<서버>_<도구>` |
| 표준 | opencode 전용 | 공개 표준, 다른 에이전트도 같은 서버 사용 |
| 잘못되면 | 같은 프로세스라 예외, 무한 루프가 opencode에 영향 | 서버만 죽고 opencode는 계속 동작 |
| 의존성 | `@opencode-ai/plugin`(npm) 필요 | 프로토콜만 지키면 없음 |

### P7. 압축될 때 잊으면 안 되는 사실: 실험적 훅

대화가 길어지면 opencode가 앞부분을 요약(compaction)합니다. 이때 "이 프로젝트는 pnpm을 쓴다" 같은 사실이 빠지면 모델이 잊고 npm을 다시 씁니다. `experimental.session.compacting` 훅으로 꼭 남길 사실을 요약 프롬프트에 덧붙입니다.

| | 모양 (관찰) |
|---|---|
| `input` | `{ sessionID }` |
| `output` | `{ context: string[], prompt?: string }`. 시작할 때 `context`는 빈 배열, `prompt`는 `undefined` |

- **`output.context.push("...")`** 는 기본 압축 프롬프트 맨 끝에 빈 줄을 사이에 두고 **덧붙습니다.** "요약의 Important Details에 포함하라" 같은 지시를 함께 쓰는 것이 효과적입니다.
- **`output.prompt = "..."`** 는 기본 압축 프롬프트를 **통째로 대체**하고, 이때 `output.context`는 **무시**됩니다. 요약 형식까지 바꿀 때만 쓰세요.
- **훅 안에서 예외가 나면 압축이 통째로 실패**합니다(`summarize`가 500). 그래서 반드시 `try/catch`로 감싸 오류를 로그에만 남깁니다.
- 반환값은 쓰이지 않습니다. `output`을 직접 고칩니다.
- `experimental.compaction.autocontinue` 훅도 있습니다. `output.enabled = false`로 바꾸면 자동 압축 뒤의 "이어하기" 턴이 만들어지지 않습니다.

압축은 TUI의 `/compact`, 서버 API(`POST /session/:id/summarize`), 또는 컨텍스트가 가득 찰 때의 자동 압축으로 일어납니다. `opencode run --command compact`와 `opencode run "/compact"`는 안 됩니다.

**실험적 훅이라는 뜻.** `experimental.` 접두사는 안정 API가 아니라는 뜻입니다. 업데이트 때 경고 없이 이름이나 모양이 바뀌거나 사라질 수 있습니다. 그러면 플러그인은 에러 없이 조용히 아무 일도 하지 않게 될 것으로 예상됩니다(이 부분은 확인하지 못했습니다). 그래서 ① opencode 버전을 고정하고 올릴 때 `check.py`를 다시 돌리고, ② 훅이 불렸다는 증거(`logs/compaction.log`)를 남기고, ③ `try/catch`로 감싸고, ④ 이 훅에 의존하는 기능은 "있으면 좋은 것"으로 둡니다. 확실히 유지돼야 하는 규칙은 `AGENTS.md`/`instructions`에 적는 편이 가장 튼튼합니다. 압축 후에도 시스템 프롬프트로 계속 들어가기 때문입니다.

또한 요약 모델에게 사실이 전달되는 것까지는 확인했지만, 실제 모델의 요약에 `pnpm`이 담기는지는 무료 모델 한도 때문에 확인하지 못했습니다. 고정 사실 파일에 실제 비밀값을 쓰지 마세요. 요약 모델(외부 서비스)로 전송됩니다.

### P8. 플러그인을 불러오는 방법

같은 작은 플러그인을 네 가지 방법으로 불러 보고, 몇 번 로드됐는지를 비교합니다. 모델은 쓰지 않습니다.

| | 방법 | 쓰는 때 |
|---|---|---|
| (a) | 프로젝트 `.opencode/plugins/`에 파일을 둔다 (자동 탐색) | 이 저장소에서만 쓰는 플러그인. 커밋해서 팀이 공유 |
| (b) | 전역 폴더 `~/.config/opencode/plugins/`에 파일을 둔다 | 모든 프로젝트에서 쓰는 개인 플러그인 |
| (c) | `opencode.json`의 `"plugin"`에 경로를 쓴다 | 파일 위치를 직접 정하거나 옵션을 넘기고 싶을 때 |
| (d) | npm 패키지 형태 (`package.json` 폴더 / npm 이름) | 여러 저장소에 배포, 버전 관리 |

```json
{ "$schema": "https://opencode.ai/config.json",
  "plugin": ["./plugins/hello.js", "file:///C:/work/tools/other.js", ["./plugins/hello.js", { "greeting": "안녕" }]] }
```

- (a)의 파일은 `opencode debug config`의 `plugin` 배열에 `file:///...` 주소로 자동 추가되어 나타납니다. `opencode debug config`도 플러그인을 로드하므로, 모델 없이 로드 여부를 확인하는 가장 쉬운 방법입니다.
- (c)의 `[경로, 옵션객체]`는 플러그인 함수의 **두 번째 인자**로 옵션을 넘깁니다. `file:///절대경로`도 되고 Windows는 `file:///C:/work/...` 형태입니다. (키 이름은 **`plugin`** 입니다. 복수형 `plugins`는 1.19.5에서 조용히 무시됩니다.)
- (d) 로컬 폴더는 `package.json`이 있는 폴더를 가리키면 되고 진입점은 **`main`** 으로 정해집니다. `exports`만 있고 `main`이 없는 폴더는 조용히 로드되지 않았습니다. 로컬 폴더용 패키지에는 `main`을 꼭 쓰세요.
- (d) npm 이름(`"opencode-hello@1.0.0"`)은 레지스트리가 필요합니다. 인터넷이 막힌 환경에서는 패키지 미러를 지정하거나, 레지스트리가 필요 없는 **로컬 폴더(`file:`) 방식**이 가장 현실적인 배포 방법입니다. 팀 공용 폴더나 저장소에 패키지 폴더를 두고 경로를 쓰세요.
- **같은 파일**은 어떻게 가리키든(상대+절대, 같은 경로 두 번, 자동 탐색+설정에서 또 지정) **한 번만** 로드됩니다. 하지만 내용이 같아도 **파일 위치가 다르면 별개**입니다. 전역과 프로젝트에 같은 플러그인을 두면 2번 로드되어 같은 훅이 두 번 실행됩니다. 한 곳에만 두세요.
- `--pure`(또는 `OPENCODE_PURE=1`)는 외부 플러그인(자동 탐색, 전역, `plugin` 설정, npm)을 **하나도 로드하지 않습니다.** `debug config`의 `plugin` 배열에는 남아 있지만 실행되지 않습니다. 스킬과 MCP는 그대로입니다.
- (c)의 상대 경로는 `opencode.json`이 있는 폴더에서 실행했을 때 그 폴더 기준으로 풀렸습니다. 하위 폴더에서 실행했을 때의 기준은 확인하지 못했습니다.

### 종합: X2

[X2](../../examples/04-combined/x2-incident-analysis/)는 한 문장("이번 주 payment 서비스 장애 분석 리포트 만들어줘")에서 세 확장의 역할을 나눠 보여 줍니다. MCP는 읽기 전용 티켓 데이터를, 스킬은 분석 절차(5단계)를, 플러그인은 안전장치를 맡습니다. 플러그인(`audit-guard.js`)은 모든 도구 호출을 감사 로그로 남기고, `write`/`edit`/`apply_patch`의 대상 경로가 `reports/` 밖이면 예외를 던져 막습니다. `..`로 빠져나가는 경로도 `path.relative`로 막습니다. 한계로, 모델이 `bash`로 `echo x > notes.txt`처럼 쓰는 것은 **막지 못하고 기록만** 합니다. 실제로 막아야 하면 `permission` 설정을 함께 쓰세요.

## permission과 플러그인: 무엇을 쓸까

같은 "위험한 명령 막기"를 두 방식으로 할 수 있습니다.

| | `permission` (설정) | 플러그인 (코드) |
|---|---|---|
| 작성 | JSON 몇 줄 | JS와 정규식, 테스트 필요 |
| 판정 | 명령 문자열을 `*` 와일드카드 패턴과 비교 | 임의의 코드: 옵션 순서, 묶음 옵션, 예외 |
| 결과 | `allow` / `ask`(사람에게 물음) / `deny` | 차단(throw) 또는 통과. 묻는 동작은 없음 |
| 메시지 | opencode 기본 거부 메시지 | 이유와 대안을 직접 전달 |
| 기록 | 없음 | 마음대로 |
| 시험 | opencode를 실행해야 확인 | 모델 없이 `node`로 수십 사례를 한 번에 |

- **설정으로 충분하면 설정을 쓰세요.** "`git push`는 물어봐라", "`rm`은 거부", "`git status`는 허용"처럼 명령 앞부분으로 구분되는 규칙은 `permission.bash`가 가장 단순하고 `ask`로 사람에게 확인받을 수 있습니다.
- **플러그인은 패턴 하나로 표현이 안 될 때** 씁니다. `git push`는 허용하되 `--force`는 막고 `--force-with-lease`는 허용하기, 옵션 순서가 바뀌어도 막기, 차단 시도를 기록하기, 팀 규칙을 단위 테스트로 고정하기가 그런 경우입니다.
- 둘은 함께 쓸 수 있습니다. 설정으로 큰 틀(기본 `ask`)을 잡고, 플러그인으로 정말 위험한 몇 가지를 코드로 못 박는 구성이 현실적입니다. `tool.execute.before`가 권한 확인보다 먼저 실행되므로 플러그인이 막은 명령은 사용자에게 묻지도 않습니다.

비교 기준 한 줄: **조건이 "이 명령어로 시작한다"로 끝나면 `permission`, 코드로 해석해야 하면 플러그인.** `permission`은 [1장](01-config.md)에서 다룹니다.

## 플러그인을 불러오는 방법과 배포 요약

- 이 저장소에서만: `.opencode/plugins/`에 파일을 두고 커밋한다.
- 내 모든 프로젝트에서: `~/.config/opencode/plugins/`(Windows는 `%USERPROFILE%\.config\opencode\plugins\`).
- 위치를 직접 정하거나 옵션이 필요하면: `opencode.json`의 `"plugin"`.
- 여러 저장소에 배포: 로컬 패키지 폴더(오프라인에 가장 현실적) 또는 npm 이름(레지스트리/미러 필요).
- 의심이 가면: `--pure`로 "플러그인 없이도 재현되는지" 가려낸다.

다음: [5. 문제 해결](05-troubleshooting.md)
