# P6 플러그인 커스텀 도구

> 구성: 플러그인(`tool` 훅) | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+(check.py만), **첫 실행 때 npm 레지스트리 또는 패키지 미러** | 슬라이드: 플러그인 - 커스텀 도구

## 무엇을 보여 주나

플러그인은 훅만 다는 게 아니라 **모델이 부를 수 있는 새 도구**도 등록할 수 있습니다. 플러그인 파일 하나에서
`@opencode-ai/plugin` 의 `tool()` 로 도구를 정의하면, 모델 화면에 `bash`, `read` 같은 내장 도구와 똑같이
`⚙ business_days {...}` 로 나타납니다. 별도 서버도, 프로토콜도 필요 없습니다. 대신 이 도구는 **opencode 안에서만** 쓸 수 있습니다.

이 예제는 세 개의 도구를 등록합니다.

| 도구 | 하는 일 | 인자(zod 스키마) |
|---|---|---|
| `business_days` | 두 날짜 사이의 영업일 수(토·일 제외) | `from`, `to` (`YYYY-MM-DD`) |
| `uuid_v4` | 무작위 UUID 하나 | 없음 |
| `team_glossary` | 같은 폴더의 `glossary.json` 에서 팀 용어 뜻 찾기 | `term` |

## 실무에서는

- **날짜·단위·ID 계산처럼 모델이 틀리기 쉬운 일**을 코드로 고정할 때: 영업일 계산, 배포 번호 규칙, 티켓 키 검증.
- **팀 규칙 조회**: 용어집, 코드 오너 표, 브랜치 이름 규칙을 모델이 추측하지 않고 도구로 확인하게 할 때.
- **opencode 안의 정보를 쓰는 도구**: 플러그인 도구는 같은 프로세스에서 실행되므로 `client`(opencode SDK), `$`(셸), 세션 정보를 그대로 쓸 수 있습니다.
- 다른 에이전트에서도 같은 도구를 쓰고 싶다면 [MCP](../../02-mcp/) 로 만드세요. 두 방식의 비교는 아래 "플러그인 도구 vs MCP 도구" 를 보세요.

## 파일 구성

```
p6-custom-tool/
├── README.md
├── check.py                         # 자동 검증 (모델 없이 도구 등록·실행까지 확인)
├── glossary.json                    # team_glossary 가 읽는 데이터
└── .opencode/
    └── plugins/
        └── team-tools.js            # 플러그인 본체: tool() 로 도구 3개 등록
        (package.json, node_modules/, ... 는 opencode 가 첫 실행 때 자동으로 만든다. git 에는 안 올라간다)
```

`opencode.json` 은 없습니다. `.opencode/plugins/` 안의 파일은 설정 없이 자동으로 로드되기 때문입니다.

## 따라 하기

> 평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 `opencode -m opencode/big-pickle` 처럼 무료 모델을 지정하세요.

### 0. 첫 실행 전 확인: npm 레지스트리에 닿는가

`.opencode/` 폴더가 있으면 opencode 가 첫 실행 때 `@opencode-ai/plugin` 을 npm 에서 **자동으로 설치**합니다.
이 예제의 `import { tool } from "@opencode-ai/plugin"` 이 바로 그 패키지입니다. 인터넷이 막힌 환경이면
먼저 아래 "주의할 점" 의 **패키지 미러 설정**을 하세요.

### 1. 실행

PowerShell:

```powershell
cd examples\03-plugins\p6-custom-tool
opencode
```

Linux (bash):

```bash
cd examples/03-plugins/p6-custom-tool
opencode
```

첫 실행은 패키지를 내려받느라 수 초 걸립니다(레지스트리에 닿을 때). 두 번째부터는 1초 안팎입니다.

### 2. 프롬프트

opencode 에 하나씩 입력하세요.

```
business_days 도구로 2026-11-02 부터 2026-11-27 까지 영업일이 며칠인지 알려 줘.
```
```
uuid_v4 도구로 UUID 하나 만들어 줘.
```
```
team_glossary 도구로 '온콜' 이 무슨 뜻인지 찾아 줘.
```

화면에 `⚙ business_days {"from":"2026-11-02","to":"2026-11-27"}` 처럼 도구 호출 줄이 보이고, 답이 **20일** 이면 성공입니다.
(11월 2일 월요일부터 27일 금요일까지 4주 = 20일. 모델이 암산한 것이 아니라 도구가 센 값입니다.)

화면 없이 한 번에 실행하려면:

```powershell
opencode run --auto "business_days 도구로 2026-11-02 부터 2026-11-27 까지 영업일이 며칠인지 알려 줘."
```
```bash
opencode run --auto "business_days 도구로 2026-11-02 부터 2026-11-27 까지 영업일이 며칠인지 알려 줘."
```

### 3. 모델 없이 등록만 확인하기

`opencode serve` 는 모델을 쓰지 않고도 현재 프로젝트에서 모델에게 보일 도구 목록을 알려 줍니다.

```bash
opencode serve --port 4096 &        # PowerShell 에서는 새 창에서 `opencode serve --port 4096`
curl http://127.0.0.1:4096/experimental/tool/ids
# ["invalid","question","bash","read","glob","grep","edit","write","task","webfetch","todowrite","websearch","skill","apply_patch","business_days","uuid_v4","team_glossary"]
```

PowerShell 은 `Invoke-RestMethod http://127.0.0.1:4096/experimental/tool/ids` 를 쓰면 됩니다. 도구 목록 끝에 세 도구가 보이면 등록된 것입니다.

### 4. 자동 검증

```powershell
python check.py            # Linux 에서 python 이 없으면 python3
python check.py --model    # 실제 모델로 한 번 더 (평소 쓰는 모델은 AGENT_SEMINAR_MODEL 로 지정)
```

## 기대 결과

`check.py` 의 "스크립트 실행" 검사는 **스크립트된 가짜 모델**(정해진 순서로 도구를 호출하는 작은 로컬 서버)로 같은 흐름을
실제 opencode 에 태웁니다. 아래는 그 실행의 실제 출력입니다. `⚙` 줄과 도구 결과는 opencode 가 낸 그대로이고,
마지막 "도구 결과:" 문장만 가짜 모델이 도구 결과를 읽어 준 것입니다(실제 모델은 자기 말투로 답합니다).

```
> build · scripted

⚙ business_days {"from":"2026-11-02","to":"2026-11-27"}
⚙ uuid_v4 Unknown
⚙ team_glossary {"term":"온콜"}
✗ business_days {"from":"2026-13-40","to":"2026-11-27"} failed
Error: 존재하지 않는 날짜입니다: 2026-13-40

도구 결과:
2026-11-02 ~ 2026-11-27 영업일: 20일 (토·일 제외, 공휴일 미반영)
a3fe1ffb-b945-4148-864f-85d8108d90be
온콜: 장애 알림을 받아 1차 대응을 맡는 당번. 보통 주 단위로 교대한다.
존재하지 않는 날짜입니다: 2026-13-40
```

- 인자가 없는 도구(`uuid_v4`)는 인자 자리에 `Unknown` 이 찍힙니다. 오류가 아니라 표시 방식입니다.
- 도구가 예외를 던지면 `✗ ... failed` 와 오류 메시지가 보이고, 같은 메시지가 모델에게 전달됩니다.

> 실제 모델(무료 모델 포함)로 돌린 transcript 는 이 문서를 쓰는 시점에 무료 모델 한도가 소진되어 캡처하지 못했습니다.
> `python check.py --model` 이 통과하면 같은 `⚙ business_days` 줄이 보여야 합니다.

## 동작 원리

1. opencode 가 시작될 때 `.opencode/plugins/team-tools.js` 를 찾아 로드합니다(설정 필요 없음). 플러그인은 opencode 에 내장된
   **Bun 런타임** 안에서 실행됩니다(확인: 플러그인 안에서 `process.versions.bun` 이 `1.4.4` 로 보임).
2. 플러그인 함수 `TeamTools({ directory, ... })` 가 훅 객체를 돌려줍니다. 여기서는 `tool` 훅 하나만 씁니다.
3. `tool: { 이름: tool({...}) }` 의 **키가 곧 모델에게 보이는 도구 이름**입니다(MCP 처럼 서버 이름 접두사가 붙지 않습니다).
4. `tool()` 에 넘기는 것은 세 가지입니다.
   - `description`: 모델이 "언제 이 도구를 쓸지" 판단하는 유일한 근거입니다. 구체적으로 쓰세요.
   - `args`: `tool.schema`(= zod) 로 만든 인자 정의. opencode 가 JSON Schema 로 바꿔 모델에게 보냅니다.
     `.describe("...")` 설명도 같이 전달됩니다. 필수 인자는 그대로 `required` 가 됩니다(확인: `from`, `to` 필수, `uuid_v4` 는 인자 없음).
   - `execute(args, context)`: 실제 코드. 문자열을 반환하면 그대로 결과가 됩니다. `{ title, output, metadata }` 형태도 가능합니다.
     `context.directory`(프로젝트 폴더), `context.worktree`, `context.sessionID`, `context.abort`, `context.ask()`(권한 요청) 를 쓸 수 있습니다.
     상대 경로는 `process.cwd()` 가 아니라 `context.directory` 를 기준으로 푸세요.
5. 모델이 도구를 부르면 opencode 가 `execute` 를 실행하고, 반환값(또는 던진 오류)을 모델에게 돌려줍니다.

### 확인한 세부 동작

| 항목 | 확인한 결과 |
|---|---|
| 플러그인 도구 이름이 내장 도구와 같으면 | **내장 도구를 덮어씁니다.** `webfetch` 라는 이름으로 등록했더니 모델이 부른 `webfetch` 가 플러그인 쪽으로 실행됨 |
| `opencode.json` 의 `permission` 으로 막기 | `"permission": {"uuid_v4": "deny"}` 이면 그 도구가 모델에게 **아예 안 보임**(호출하면 "unavailable tool"). `"ask"` 는 `--auto` 에서 자동 승인 |
| `--pure` 로 실행 | 외부 플러그인을 로드하지 않으므로 커스텀 도구 3개가 사라짐 (내장 도구만 남음) |
| 같은 기능을 `.opencode/tools/` 로 | `.opencode/tools/<파일>.js` (옛 이름 `tool/` 도 동작)에 `export default tool({...})` 하면 **파일 이름이 도구 이름**. 추가 `export const second = tool(...)` 는 `<파일>_second` 가 됨 |
| 플러그인 파일의 `export` | 내보낸 **모든 함수가 플러그인으로 호출됩니다**. 함수가 아닌 값(`export const X = 42`)을 내보내면 그 파일의 플러그인이 전부 조용히 로드되지 않습니다. 도우미 함수는 `export` 하지 마세요 |

### 플러그인 도구 vs MCP 도구

| | 플러그인 커스텀 도구 (이 예제) | MCP 도구 ([M1](../../02-mcp/) 등) |
|---|---|---|
| 실행 위치 | **opencode 프로세스 안**(Bun) | **별도 프로세스**(stdio) 또는 원격 서버(HTTP) |
| 언어 | JavaScript / TypeScript | 아무 언어 (우리 예제는 Python 표준 라이브러리) |
| 모델에게 보이는 이름 | `business_days` | `<서버이름>_<도구이름>` (예: `glossary_lookup_term`) |
| 표준 여부 | **opencode 전용** | **공개 표준 프로토콜** - Claude Code, Cursor 등 다른 에이전트도 같은 서버를 씀 |
| 의존성 | `@opencode-ai/plugin`(npm) 필요 | 프로토콜만 지키면 의존성 없음 |
| opencode 내부 접근 | 가능 (`client`, `$`, 훅, 세션 정보) | 불가능 (프로토콜 밖) |
| 잘못되면 | 같은 프로세스라 예외·무한 루프가 opencode 에 영향 | 서버만 죽고 opencode 는 계속 동작 |
| 배포 | 파일 한 개 복사 | 서버 설치 또는 URL 공유 |
| 어울리는 일 | 가벼운 계산·규칙 조회, opencode 와 얽힌 기능 | 여러 에이전트·여러 사람이 공유할 도구, 외부 시스템 연동 |

한 줄 기준: **"다른 에이전트도 쓸 도구인가?"** 그렇다면 MCP, 아니고 opencode 안의 가벼운 기능이라면 플러그인 도구.

## 직접 바꿔 보기

1. `uuid_v4` 를 참고해 `now_kst` 도구를 추가해 보세요(`execute` 에서 현재 시각을 문자열로 반환). opencode 를 다시 시작하고 `opencode serve` 의 도구 목록에 나오는지 확인합니다.
2. `business_days` 에 선택 인자 `holidays: tool.schema.array(tool.schema.string()).optional()` 를 추가해 공휴일을 빼도록 고쳐 보세요. 모델이 공휴일을 직접 넘기는지 관찰합니다.
3. `opencode.json` 에 `{"permission": {"team_glossary": "deny"}}` 를 넣고 같은 프롬프트를 실행해 보세요. 도구가 사라지는 것을 확인합니다.

## 주의할 점 / 문제 해결

### npm 자동 설치와 레지스트리(패키지 미러)

`.opencode/` 가 있는 폴더에서 opencode 를 시작하면 `.opencode/package.json` 에
`"@opencode-ai/plugin": "1.19.5"` 가 적히고 `node_modules/` 가 만들어집니다(같은 설치가 전역 설정 폴더
`~/.config/opencode/` 에도 일어납니다). 직접 확인한 동작은 다음과 같습니다.

| 상황 | 결과 |
|---|---|
| 레지스트리에 닿음 | 첫 시작 6~10초, 이후 1초 안팎 |
| 레지스트리가 연결을 거부/차단(응답 없음) | **약 70초 동안 시작이 멈춘** 뒤 계속 진행. 설치가 안 됐으므로 `import ... "@opencode-ai/plugin"` 이 실패하고 **커스텀 도구가 오류 메시지 없이 사라짐** |
| 레지스트리는 응답하지만 패키지가 없음(404) | 지연 없이 바로 실패, 마찬가지로 도구가 조용히 사라짐 |

도구가 안 보이면 `opencode --print-logs` 로 실행해서 이 줄을 찾으세요(일반 실행에는 출력되지 않습니다).

```
level=WARN message="background dependency install failed" dir=.../.opencode error="...NpmInstallFailedError..."
```

플러그인을 가져오다 실패하는 것(`import` 오류, 문법 오류) 자체는 **로그에도 안 남습니다.** 플러그인 안에서 파일에 한 줄 쓰는 식의
확인 코드를 넣어 두면 로드 여부를 알 수 있습니다([P8](../p8-load-methods/) 의 마커 파일 방식).
반면 플러그인 함수가 초기화 중 예외를 던지면 `level=ERROR message="failed to load plugin"` 이 남습니다.

**패키지 미러(레지스트리) 지정하는 법** - 아래 중 하나면 됩니다. 주소는 예시이니 실제 미러 주소로 바꾸세요.

1. 사용자 `.npmrc` (가장 무난함. 전역 폴더 설치와 `.opencode/` 설치, 그리고 `"plugin": ["이름@버전"]` 설치에 모두 적용됨)
   - Linux: `~/.npmrc`, Windows: `%USERPROFILE%\.npmrc`
   ```
   registry=https://registry.example.com/
   ```
2. 환경 변수 `npm_config_registry` (한 번만 쓰거나 스크립트에서 지정할 때)
   ```powershell
   $env:npm_config_registry = "https://registry.example.com/"; opencode
   ```
   ```bash
   npm_config_registry=https://registry.example.com/ opencode
   ```
3. `.opencode/.npmrc` - **`.opencode/` 의 의존성 설치에만** 적용됩니다.
4. 프로젝트 루트의 `.npmrc` 는 **적용되지 않습니다**(확인함). 넣어도 공식 레지스트리로 갑니다.

미러에 `@opencode-ai/plugin` 과 그 의존 패키지가 들어 있어야 합니다. 이미 설치된 곳의 `.opencode/node_modules/`
(+ `package.json`, `package-lock.json`)를 통째로 복사하는 방법도 있지만, 아래 지연은 남습니다.

**레지스트리에 전혀 닿지 않는 환경의 현실**(확인함): `.opencode/node_modules` 를 미리 채워 두면 프로젝트의 커스텀 도구는 등록됩니다.
그러나 전역 설정 폴더(`~/.config/opencode/`)의 설치가 계속 실패하므로 **시작할 때마다 약 71초씩 멈춥니다**(연속 3번 실행 모두 71초).
이 지연을 없애려면 접근 가능한 미러를 지정하는 것이 유일한 방법입니다. 그래서 인터넷이 막힌 환경에서는 패키지 미러 설정을 먼저 하세요.

### 그 밖에

- 이 예제의 `.opencode/package.json`, `node_modules/` 등은 `.gitignore` 에 있습니다. 새로 클론하면 첫 실행에 다시 설치됩니다.
- Windows 에서도 같은 파일이 그대로 동작합니다(경로는 `node:path` 의 `join` 을 썼습니다).
- `tool.schema` 는 zod 입니다. `tool.schema.string().optional()`, `.enum([...])`, `.number()`, `.array(...)` 를 쓸 수 있습니다.
- 도구 설명(`description`)을 바꾸면 모델이 부르는 빈도가 바뀝니다. 안 불린다면 설명에 "언제 쓰는지" 를 한 줄 더 넣으세요.
- 날짜 계산은 UTC 로 고정했습니다. 시간대가 다른 PC 에서도 같은 결과가 나오게 하려는 것입니다.
