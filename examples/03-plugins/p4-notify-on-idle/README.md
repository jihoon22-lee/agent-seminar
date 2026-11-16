# P4 작업 완료·승인 대기 알림 (notify-on-idle)

> 구성: 플러그인(JS) `event` 훅 + 외부 명령 실행 | 난이도: ★★☆ | 필요: opencode 1.19.5 (Windows: PowerShell 5.1 / Linux: 선택적으로 `notify-send`), Node 는 단위 테스트에만 | 슬라이드: 플러그인 — 이벤트 받아 외부 명령 실행

## 무엇을 보여 주나

`event` 훅은 opencode 안에서 일어나는 모든 일(세션 생성, 메시지 갱신, 권한 요청 …)을 이벤트로 받습니다.
이 예제는 그중 두 가지, **응답이 끝나 입력을 기다리는 순간(`session.idle`)** 과 **도구 실행 허락을 기다리는 순간(`permission.asked`)** 에 소리와 알림을 보냅니다.
"이벤트를 받는다 → 바깥 프로그램(PowerShell, notify-send)을 실행한다"는 패턴은 알림뿐 아니라 메신저 전송, 로그 수집, 빌드 트리거 같은 연동의 기본 틀입니다.

## 실무에서는

- 에이전트에게 긴 작업(테스트 수정, 리팩터링)을 시켜 놓고 다른 창에서 일하다가, 끝났거나 내 승인이 필요할 때만 불려 오고 싶을 때 씁니다. 승인 대기를 놓치면 에이전트가 몇십 분을 그냥 멈춰 있습니다.
- 알림 대신 메신저 웹훅 호출, 팀 채널 공유, 작업 시간 기록으로 바꿔 쓸 수 있습니다. 바꾸는 곳은 `sendNotification` 한 함수뿐입니다.
- 실제로 이 방식은 필자가 매일 쓰는 개인 플러그인과 같은 구조입니다: 이벤트 하나를 받고, 외부 명령 하나를 실행합니다.

## 파일 구성

```
p4-notify-on-idle/
├── README.md
├── fake_llm.py                       # 검증용 가짜 LLM (표준 라이브러리만, 복사본)
├── check.py                               # 자동 검증 (단위 테스트 + 플러그인 로드 + --model 모델 검사)
├── opencode.json                          # permission.bash = ask (승인 알림을 시연하려고 bash 에 승인을 요구)
├── .opencode/plugins/notify-on-idle.js    # 플러그인 본체
├── tests/notify.test.mjs                  # 이벤트 훅을 직접 호출하는 시험 (node, 알림은 실제로 보내지 않음)
└── logs/                                  # 실행하면 생김: plugin-load.log, notify.log, (events.log)
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. (모델 설정이 없다면 무료 모델 `-m opencode/big-pickle` 을 붙이세요.)

1. 이 폴더에서 opencode 를 실행합니다. 처음 실행하면 opencode 가 `.opencode/` 안에 `@opencode-ai/plugin` 을 npm 으로 설치하려고 합니다. 인터넷이 막혀 있고 패키지 미러도 없으면 첫 시작이 70초쯤 멈췄다가 계속 진행됩니다.

   PowerShell:
   ```powershell
   cd examples\03-plugins\p4-notify-on-idle
   opencode
   ```
   Linux bash:
   ```bash
   cd examples/03-plugins/p4-notify-on-idle
   opencode
   ```

2. 프롬프트: `bash 도구로 echo hello 를 실행해 줘`
   - `opencode.json` 때문에 bash 는 승인을 요구합니다. 승인 창이 뜨는 순간 **승인 필요** 알림이 옵니다. 승인하면 명령이 실행되고, 응답이 끝나는 순간 **작업 완료** 알림이 옵니다.
   - 알림이 오기 전에 다른 창으로 이동해 두세요.

3. 기록은 항상 남습니다.

   PowerShell: `Get-Content logs\notify.log`
   Linux bash: `cat logs/notify.log`

4. **이벤트 이름을 직접 찾아보는 방법**: 아래처럼 `NOTIFY_LOG_ALL_EVENTS=1` 로 실행하면 받은 모든 이벤트의 type 이 `logs/events.log` 에 쌓입니다. 이 예제가 어떤 이름을 쓸지 정할 때 쓴 방법입니다.

   PowerShell:
   ```powershell
   $env:NOTIFY_LOG_ALL_EVENTS = 1
   opencode run --auto "bash 도구로 echo hello 를 실행해 줘"
   Get-Content logs\events.log | ForEach-Object { ($_ -split "`t")[1] } | Sort-Object -Unique
   ```
   Linux bash:
   ```bash
   NOTIFY_LOG_ALL_EVENTS=1 opencode run --auto "bash 도구로 echo hello 를 실행해 줘"
   cut -f2 logs/events.log | sort -u
   ```

5. 소리·알림 없이 기록만 남기고 싶을 때(시험용): `NOTIFY_DRY_RUN=1`. 자동 검증은 `python check.py` / `python check.py --model` 입니다 (Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요).

## 기대 결과

아래 출력은 `check.py` 가 쓰는 **가짜 LLM**(`fake_llm.py`: 정해진 도구 호출을 대신 수행하는 OpenAI 호환 서버, 표준 라이브러리만 사용)으로 실제 `opencode 1.19.5` 를 실행해 얻은 것입니다. 모델이 무엇을 시키든 플러그인이 어떻게 반응하는지를 매번 똑같이 재현할 수 있습니다. 실제 모델(무료 모델)로는 이번 확인 시점에 한도 초과/시간 초과로 결과를 얻지 못해 **미검증**입니다. 평소 쓰는 모델로 해 보면 모델의 말투와 시도 순서는 다르겠지만 차단/기록 동작은 같아야 합니다.

가짜 LLM 이 `echo notify-demo` 를 실행하려 했을 때 (`permission.bash` 가 `ask` 이므로 승인 요청이 발생; Linux 와 Windows 동일). `NOTIFY_DRY_RUN=1` 이라 알림 명령은 실행하지 않고 기록만 남긴 `logs/notify.log`:

```
2026-11-16T17:10:34.047Z	permission	ses_…	opencode: 승인 필요 / bash 실행 허락을 기다리는 중: echo notify-demo
2026-11-16T17:10:34.166Z	idle	ses_…	opencode: 작업 완료 / 응답이 끝났습니다. 결과를 확인하세요.
```

`NOTIFY_LOG_ALL_EVENTS=1` 로 받은 이벤트 type 전체(`logs/events.log` 에서 중복 제거):

```
catalog.updated  integration.updated  message.part.delta  message.part.updated  message.updated
permission.asked  permission.replied  plugin.added  reference.updated
session.created  session.diff  session.idle  session.status  session.updated
```

Windows 에서 `opencode serve` 에 붙어(TUI 처럼 오래 사는 프로세스) 실제 알림 명령까지 실행한 `notify.log` (`NOTIFY_REAL_CHECK=1 python check.py`):

```
2026-11-16T17:22:50.121Z	idle	ses_…	opencode: 작업 완료 / 응답이 끝났습니다. 결과를 확인하세요.
  └ powershell started
  └ sound ok
  └ toast ok
```

(소리가 실제로 들리는지, 토스트가 화면에 보이는지는 사람이 확인해야 해서 검증하지 못했습니다. `sound ok`/`toast ok` 는 예외 없이 호출이 끝났다는 뜻입니다.)

## 동작 원리

### 어떤 이벤트를 쓰는가 (1.19.5 에서 직접 확인)

모델 실행 중에 `event` 훅이 받은 type 을 전부 기록해 보았습니다.

| type | 언제 | 주요 `properties` |
|---|---|---|
| `session.idle` | 응답이 모두 끝나고 입력을 기다리는 상태가 될 때 (**완료 알림에 사용**) | `sessionID` |
| `permission.asked` | 도구 실행 전에 사용자 승인이 필요할 때 (**승인 알림에 사용**) | `id`, `sessionID`, `permission`(예: `bash`), `patterns`(예: `["echo hello"]`), `metadata`, `always`, `tool` |
| `permission.replied` | 승인/거부가 되었을 때 | `sessionID`, `requestID`, `reply`(`once`/`reject` …) |
| `session.status` | 상태가 바뀔 때 (`status.type` 이 `busy` 또는 `idle`) | `sessionID`, `status` |
| `session.created` / `session.updated` / `session.diff` | 세션 생성·갱신 | `info`(SDK 의 `Session` 타입에 `parentID?` 가 있어 서브에이전트 세션을 구분할 수 있음) |
| `message.updated` / `message.part.updated` / `message.part.delta` | 메시지와 출력이 스트리밍될 때 | `info` / `part` / `delta` |
| `plugin.added`, `catalog.updated`, `reference.updated`, `integration.updated` | 시작 시 내부 상태 | — |

주의할 점:

- `session.status` 도 `idle` 을 알리지만 `session.idle` 과 **같은 순간에 둘 다 옵니다.** 둘 다 처리하면 알림이 두 번 가므로 `session.idle` 만 씁니다.
- SDK 의 타입 정의(`@opencode-ai/plugin` 이 가져오는 타입)에는 `permission.updated` 가 있지만, 1.19.5 가 실제로 내보내는 것은 `permission.asked` / `permission.replied` 입니다. 타입 정의만 믿지 말고 이벤트를 직접 기록해 보세요.
- 같은 이름의 `permission.ask` **훅**(훅 목록에 있는 것)은 이번 확인에서 권한 요청이 발생해도 호출되지 않았습니다. 알림에는 `event` 훅의 `permission.asked` 를 쓰세요.
- 권한 설정이 `ask` 이면 `--auto` 로 실행해도 `permission.asked` 이벤트는 발생했습니다(자동으로 `once` 승인). 그래서 `check.py` 가 대화형 입력 없이 승인 알림 경로를 시험할 수 있습니다.
- 하위 에이전트(`task` 도구)의 세션이 끝날 때마다 알림이 오지 않도록, `session.created` 에서 `info.parentID` 가 있는 세션은 기억해 두었다가 그 세션의 `idle` 은 건너뜁니다. 이 부분은 단위 테스트로만 확인했고 실제 `task` 실행으로는 확인하지 않았습니다.

### 알림 보내기

1. 이벤트를 받으면 **먼저** `logs/notify.log` 에 한 줄을 동기 방식으로 씁니다. `opencode run` 은 응답이 끝나자마자 종료되므로, 외부 프로세스를 띄우기 전에 기록부터 남겨야 합니다.
2. Windows: `cmd.exe /c start "" /b powershell.exe -EncodedCommand ...` 로 PowerShell 을 띄웁니다. 스크립트가 하는 일은 두 가지입니다.
   - `System.Media.SystemSounds` 의 Asterisk 소리 재생 (추가 모듈 없음)
   - `Windows.UI.Notifications` 로 토스트 표시 (추가 모듈 없음, Windows PowerShell 의 앱 ID 를 빌려 씀)
   각 단계의 결과(`sound ok` / `toast ok` / 실패 이유)는 `notify.log` 에 `└` 로 시작하는 줄로 덧붙습니다. 스크립트는 `-EncodedCommand`(UTF-16LE base64)로 넘기고 제목·본문은 환경변수로 전달해서, 따옴표나 한글이 들어 있어도 깨지지 않습니다.
3. Linux: `notify-send` 가 있으면 실행하고, 없으면(`ENOENT`) 터미널 벨 문자(`\x07`)를 출력합니다. 두 경우 모두 `notify.log` 가 남습니다.
4. 같은 세션의 같은 종류 알림은 1.5초 안에 한 번만 보냅니다.

## 직접 바꿔 보기

1. `sendNotification` 을 바꿔 알림 대신 `logs/done.txt` 에 완료 시각을 쓰게 해 보세요. 이벤트 → 외부 동작 연결이 어떻게 되는지 가장 단순한 형태로 볼 수 있습니다.
2. `session.error` 이벤트(오류 발생)도 알림에 추가해 보세요. 먼저 `NOTIFY_LOG_ALL_EVENTS=1` 로 존재하는 이벤트 이름을 확인한 뒤, `switch` 에 `case` 를 추가합니다.
3. `opencode.json` 의 `permission.bash` 를 `allow` 로 바꾸면 승인 알림이 사라지고 완료 알림만 남는지 확인해 보세요.

## 주의할 점 / 문제 해결

- **`opencode run` 에서는 소리·토스트가 나지 않을 수 있습니다.** `opencode run` 은 응답이 끝나자마자 종료되고, 그때 알림 프로세스도 같이 끊깁니다 (Windows 에서 확인: `notify.log` 에는 `idle` 줄만 남고 소리 단계 기록이 없었습니다). TUI(`opencode`)나 `opencode serve` 처럼 오래 사는 프로세스에서는 PowerShell 이 끝까지 실행되어 `notify.log` 에 `powershell started` → `sound ok` → `toast ok` 가 남았습니다. 알림이 필요한 곳은 TUI 이므로 이 예제의 용도에는 문제가 없지만, `run` 으로 시험할 때는 `notify.log` 의 첫 줄(이벤트를 받았다는 기록)만 보세요.
- **Windows 에서 PowerShell 띄우는 방법**: `spawn(..., { detached: true })` 로 PowerShell 을 직접 띄우면 콘솔이 없어 스크립트가 실행되지 않고 소리도 로그도 없이 끝났습니다. 그래서 `cmd.exe /c start "" /b powershell.exe ...` 로 띄웁니다. 소리가 실제로 들리는지, 토스트가 화면에 보이는지는 사람이 확인해야 하므로 이 문서에서는 `sound ok`/`toast ok` 기록까지만 확인했습니다. (`NOTIFY_REAL_CHECK=1 python check.py` 가 Windows 에서 `opencode serve` 에 붙어 이 기록을 확인하며, 소리가 한 번 납니다.)
- 토스트는 Windows 의 방해 금지(집중 지원) 설정이 켜져 있으면 화면에 나타나지 않을 수 있습니다. 소리는 시스템 볼륨을 따릅니다.
- WSL 에서 Linux 용 opencode 를 쓰면 `notify-send` 가 있어도 Windows 화면에는 알림이 뜨지 않습니다. 이 예제는 WSL 을 따로 처리하지 않습니다.
- 알림에 들어가는 `patterns` 에는 실행하려는 명령이 그대로 들어 있습니다. 비밀이 들어 있는 명령이 화면과 `notify.log` 에 남을 수 있으니 길이를 80자로 자르는 부분을 유지하세요.
- **export 는 플러그인 함수만 하세요.** 상수나 보조 함수를 export 하면 opencode 가 그것도 플러그인으로 호출하다가 오류 메시지 없이 파일 전체를 건너뜁니다.
- `node` 가 없으면 `check.py` 가 경고(WARN)를 내고 단위 테스트를 건너뜁니다. opencode 실행에는 Node 가 필요 없습니다.
