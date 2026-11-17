# M10 공식 TypeScript SDK로 만든 서버, npx로 실행

> 구성: Node(ESM) 서버 1개 + package.json + JSON 용어집 | 난이도: ★★☆ | 필요: opencode 1.19.5, Node.js 18+ (npm 포함), Python 3.10+ (check.py) | 슬라이드: MCP — Node 서버와 npx

## 무엇을 보여 주나

M1은 JSON-RPC를 손으로 읽고 썼고, M2는 Python SDK(`mcp`)를 썼다. 이 예제는 같은 팀 용어집 서버(`lookup_term`, `list_terms`)를 **공식 TypeScript SDK(`@modelcontextprotocol/sdk` 1.32.2)** 로 만든다. 파일은 `src/server.mjs` 하나(주석·빈 줄 빼고 56줄)이고 TypeScript 컴파일은 없다.

그리고 서버를 실행하는 두 가지 모양을 비교한다.

1. `["node", "src/server.mjs"]` — 폴더에서 `npm install`을 한 번 한 뒤 쓰는 기본 항목.
2. `npx -y …` — clone이 필요 없는 **배포 형태**. `npm pack`으로 만든 `.tgz`를 `npx`로 실행해 처음 실행할 때 걸리는 시간을 잰다.

## 실무에서는

- Node 생태계의 서버(대부분의 공개 MCP 서버)는 `npx -y 패키지@버전` 한 줄로 실행한다. 직접 서버를 만들어도 같은 모양으로 배포하면 팀원은 레포를 받지 않고 설정 한 줄만 쓰면 된다.
- 프론트엔드 팀처럼 Node가 이미 있는 환경에서는 Python 환경(M2의 `.venv`)을 새로 만드는 것보다 Node 서버가 자연스럽다.
- SDK를 쓰면 프로토콜 코드를 직접 짜지 않고 **도구의 이름, 설명, 입력 스키마, 실행 함수**만 쓴다.

## 파일 구성

```
m10-node-sdk-npx/
  README.md
  package.json       name team-glossary-mcp, version 1.0.0, type module, bin, 의존성 고정
  src/server.mjs     SDK로 만든 서버 (shebang 포함)
  glossary.json      M1과 같은 용어집 (14개). npm 패키지에도 함께 들어간다 ("files")
  opencode.json      glossary-node(켜짐) + glossary-npx(꺼짐)
  check.py           자동 검증 (tools/run_checks.py가 실행)
  fake_llm.py        가짜 LLM 서버 (check.py 용)
  package-lock.json  하위 의존성까지 고정한 잠금 파일 (레포에 포함)
  .gitignore         node_modules/, *.tgz
  node_modules/      (생성됨) npm install 결과
```

`package.json`의 핵심:

```json
{
  "name": "team-glossary-mcp",
  "version": "1.0.0",
  "type": "module",
  "bin": { "team-glossary-mcp": "src/server.mjs" },
  "files": ["src", "glossary.json"],
  "dependencies": { "@modelcontextprotocol/sdk": "1.32.2", "zod": "4.6.7" }
}
```

`opencode.json`:

```json
{
  "mcp": {
    "glossary-node": { "type": "local", "command": ["node", "src/server.mjs"], "enabled": true },
    "glossary-npx":  { "type": "local", "command": ["npx", "-y", "./team-glossary-mcp-1.0.0.tgz"], "enabled": false, "timeout": 60000 }
  }
}
```

## 따라 하기

> **`npm install` 단계는 npm 패키지 미러(레지스트리)가 필요하다.** 인터넷이 막혀 있으면 먼저 `npm config set registry <미러 주소>`를 설정한다. 현재 설정은 `npm config get registry`로 본다.

모든 명령은 이 예제 폴더(`examples/02-mcp/m10-node-sdk-npx`)에서 실행한다.

**1. 의존성 설치 (한 번)**

```powershell
cd examples\02-mcp\m10-node-sdk-npx
npm install
```

```bash
cd examples/02-mcp/m10-node-sdk-npx
npm install
```

**2. 에이전트 없이 서버에 말 걸어 보기** — 서버를 켜 놓고 JSON 한 줄씩 붙여 넣는다. 종료는 `Ctrl+C`.

```powershell
node src/server.mjs
```

```bash
node src/server.mjs
```

```
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"hand","version":"0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"lookup_term","arguments":{"term":"SLO"}}}
```

**3. opencode로 연결 확인**

```text
opencode mcp list
```

**4. opencode에서 질문하기** — 평소 쓰는 모델로 실행하면 된다.

```text
opencode run --auto "팀 용어집에서 ADR이 무슨 뜻인지 찾아줘"
```

**5. 배포 형태 시험하기** — 패키지로 묶어 `npx`로 실행한다. 처음 실행할 때 의존성을 내려받으므로 레지스트리가 필요하다.

```powershell
npm pack
npx -y ./team-glossary-mcp-1.0.0.tgz
```

```bash
npm pack
npx -y ./team-glossary-mcp-1.0.0.tgz
```

`opencode.json`에서 `glossary-npx`의 `enabled`를 `true`로 바꾸면 opencode가 이 방식으로 서버를 띄운다 (`glossary-node`는 `false`로 두면 같은 도구가 이중으로 나오지 않는다).

**6. 자동 검증**

```text
python check.py            # 모델 없이 (가짜 모델)
python check.py --model    # 실제 모델이 도구를 쓰는지까지 (soft)
```

## 기대 결과

`opencode mcp list` (Linux, `npm install` 후):

```text
●  ✓ glossary-node connected
│      node src/server.mjs
●  ○ glossary-npx disabled
│      npx -y ./team-glossary-mcp-1.0.0.tgz
```

`tools/call`의 결과 (`lookup_term`, 성공과 용어 없음. 직접 서버에 보낸 결과):

```text
{"result":{"content":[{"type":"text","text":"ADR: 중요한 설계 결정을 배경, 선택지, 결과와 함께 ... \n(별칭: Architecture Decision Record, 아키텍처 결정 기록)"}]},"jsonrpc":"2.0","id":3}
{"result":{"content":[{"type":"text","text":"'카나리아 배포'은(는) 용어집에 없습니다. 비슷한 용어: 카나리 배포. list_terms로 전체 목록을 볼 수 있습니다."}],"isError":true},"jsonrpc":"2.0","id":4}
```

`npm install`은 패키지 95개, `node_modules` 약 29 MB, 3.1초(캐시가 따뜻한 상태)였다. `npm audit`는 0개 취약점이다.

### 시작 시간 (Linux, Node 24.18, npm 11.16, initialize 응답까지)

| 실행 방식 | 첫 실행 | 이후 |
|-----------|---------|------|
| `node src/server.mjs` (`npm install` 후) | 0.2~0.3초 | 0.2초 |
| `npx -y .` (`npm install` 후) | 1.3초 | 1.3~1.5초 |
| `npx -y ./team-glossary-mcp-1.0.0.tgz` (npm 캐시를 비운 상태) | 4.2~4.7초 | 1.5~1.8초 |

opencode의 서버 시작 제한은 30초다(M9). 이 PC는 레지스트리가 빨라서 첫 실행도 5초 안에 끝났다. 느린 미러에서의 시간은 측정하지 못했다.

시작이 제한을 넘으면 어떻게 되는지는 시작을 일부러 35초 늦춘 서버(`sh -c "sleep 35; exec node src/server.mjs"`, Linux 전용 시험)로 확인했다.

```text
●  ✗ slow-default failed
│      Operation timed out after 30000ms
●  ✓ slow-60s connected              <- 같은 명령에 "timeout": 60000 을 준 항목
```

그래서 `npx`처럼 처음 실행이 느릴 수 있는 항목에는 서버별 `timeout`(밀리초)을 늘려 둔다 (`glossary-npx`에 60000).

### `npx`에 무엇을 줄 수 있나 (직접 시험)

| 명령 | 결과 |
|------|------|
| `npx -y .` (`npm install` 전) | **실패.** `ERR_MODULE_NOT_FOUND: Cannot find package '@modelcontextprotocol/sdk'`. 로컬 폴더를 `npx`로 실행하면 `bin`만 연결하고 의존성을 설치하지 않는다 |
| `npx -y .` (`npm install` 후) | 성공, 1.3초. 하지만 `node src/server.mjs`보다 약 1초 느리기만 하다 |
| `npx -y ./team-glossary-mcp-1.0.0.tgz` | 성공. 처음 실행에서 의존성을 설치한다 |
| `npx -y /절대/경로/team-glossary-mcp-1.0.0.tgz` | **실패.** `sh: …tgz: Permission denied` (파일을 명령으로 실행하려 한다). 앞에 `./`를 붙이거나 아래 형태를 쓴다 |
| `npx -y --package=/절대/경로/x.tgz team-glossary-mcp` | 성공 (2.7초) |
| `npx -y file:/절대/경로/x.tgz` | 성공 (3.4초) |

같은 버전으로 `.tgz`를 다시 만들어도 `npx`는 바뀐 내용을 반영했다 (파일에 표식을 넣고 다시 `npm pack`해서 확인).

그래서 `opencode.json`의 `glossary-npx` 항목은 `["npx", "-y", "./team-glossary-mcp-1.0.0.tgz"]`다. `npm pack`을 먼저 해야 파일이 있다. `.tgz`는 `.gitignore` 대상이다. Windows에서도 같은 `./…tgz` 형태로 `check.py`가 통과했다.

### 실제 배포 모양

레지스트리(또는 팀 미러)에 올린 뒤에는 이렇게 쓴다. 이 예제는 올리지 않았으므로 **미실행**이다.

```json
"command": ["npx", "-y", "team-glossary-mcp@1.0.0"]
```

`package.json`의 `bin`이 `team-glossary-mcp` 명령을 가리키므로 패키지 이름만 주면 된다.

## 동작 원리

### SDK가 대신해 주는 일 (M1, M2와 비교)

| | M1 (직접) | M2 (Python SDK) | M10 (Node SDK) |
|---|---|---|---|
| 입출력 | `sys.stdin` 줄 읽기, `json.dumps` | SDK | SDK (`StdioServerTransport`) |
| `initialize` 협상 | 직접 | SDK | SDK |
| 도구 목록 | `TOOLS` 목록에 스키마를 손으로 | 타입 힌트에서 생성 | `zod` 스키마에서 생성 |
| 잘못된 인자 | 우리가 `-32602` 반환 | `isError` 결과 | `isError` 결과 |
| 모르는 도구 | `-32602` | `isError` 결과 | `isError` 결과 |
| 모르는 method | `-32601` | SDK | SDK (`-32601`) |
| 코드 줄 수(주석·빈 줄 제외) | 124 | 24 | 56 |

직접 확인한 SDK의 동작:

- **인자 누락, 모르는 도구는 JSON-RPC 오류가 아니라 `isError: true` 결과**로 나온다. 본문에 `MCP error -32602: Input validation error: Invalid arguments for tool lookup_term: ...`이 들어 있다. M1처럼 `error.code`로 구분하던 코드는 이 SDK 위에서는 쓸 수 없다.
- 용어 없음은 우리가 직접 `isError: true`를 돌려준다. 프로토콜 오류가 아니라 모델이 읽고 다시 시도할 결과이기 때문이다 (M1과 같은 이유).
- SDK는 `capabilities.tools.listChanged: true`를 선언하고, 도구마다 `execution: {taskSupport: "forbidden"}`를 붙인다. 지금은 신경 쓸 필요 없다.
- **stdout은 프로토콜 전용**이다. 로그는 `console.error`(stderr)로만 쓴다. 이 서버의 `[team-glossary] …` 로그는 모두 stderr다 (`check.py`가 stdout의 모든 줄이 JSON인지 확인한다).
- Windows 인코딩 문제가 없다. Node는 입출력을 UTF-8로 쓰기 때문에 M1의 `reconfigure`에 해당하는 코드가 필요 없다.

### `glossary.json`은 어디서 찾나

`new URL("../glossary.json", import.meta.url)` — 서버 파일 기준 위치다. 실행한 폴더와 상관없고, `package.json`의 `"files"`에 `glossary.json`을 넣었기 때문에 `.tgz` 안에도 들어간다. `check.py`가 `.tgz`의 파일이 `package.json`, `glossary.json`, `src/server.mjs` 셋뿐인지 확인한다 (크기 3.5 kB).

### npx가 더해 주는 것과 치르는 비용

| 얻는 것 | 치르는 것 |
|---------|-----------|
| 레포를 받지 않아도 된다: 설정 한 줄 | **처음 실행에 의존성 설치**: 이 PC에서 4~5초, 이후 1.5초 (매번 `node`보다 1초 이상 느림) |
| 버전 고정: `team-glossary-mcp@1.0.0` | **레지스트리/미러가 필요**. 막혀 있으면 서버가 뜨지 않는다 |
| 팀 전체가 같은 코드 | 시작 제한 30초 → 느린 미러에서는 `timeout`을 늘려야 한다 |
| 의존성이 패키지에 적혀 있어 환경 준비가 자동 | 코드를 고쳤을 때 버전을 올리고 다시 게시해야 한다 |

최상위 의존성을 정확한 버전(`1.32.2`, `4.6.7`)으로 고정했다. 그 아래 의존성(`hono`, `ajv` 등)은 `^` 범위라 시점에 따라 달라질 수 있다. 그래서 `package-lock.json`을 레포에 포함했다. `npm install` 대신 `npm ci`를 쓰면 잠금 파일 그대로 설치한다. 잠금 파일의 내려받기 주소는 `registry.npmjs.org`로 적혀 있지만, 미러를 지정해 두면 npm이 그 주소로 바꿔 받는다(npm 설정 `replace-registry-host`의 기본 동작이며, 이 예제에서 직접 시험하지는 않았다). `zod`를 4.6.7로 고정한 이유는 3.25.76에서 `npm audit`가 high 경고를 냈기 때문이다 (SDK 1.32.2는 `^3.25 || ^4.0`을 받는다).

## 직접 바꿔 보기

1. `src/server.mjs`에 `random_term` 도구를 추가하고 `node src/server.mjs`에 `tools/list`를 보내 확인한다. 설명(`description`)을 `"도구"` 한 단어로 줄이면 모델이 고르는 방식이 어떻게 바뀌는지 M1처럼 본다.
2. `package.json`의 `version`을 `1.0.1`로 올리고 `npm pack`을 다시 한다. 파일 이름이 바뀌므로 `opencode.json`의 `.tgz` 이름도 같이 바꿔야 한다.
3. `check.py`가 출력하는 `[info]` 시간을 느린 환경과 비교해 보자. 미러가 느리면 첫 실행이 30초를 넘는지, `timeout`을 늘리면 `connected`가 되는지 본다.
4. `glossary-npx`를 `enabled: true`로 켜고 `glossary-node`를 `false`로 바꿔 `opencode mcp list`를 실행한다.

## 주의할 점 / 문제 해결

- **`glossary-node`가 `failed`**: `npm install`을 했는지 먼저 본다. 안 했다면 서버가 `Cannot find package '@modelcontextprotocol/sdk'`로 죽는다. 서버를 터미널에서 직접 실행하면 이 메시지가 보인다.
- **`npx -y .`가 같은 이유로 실패**하면 위 표처럼 `npm install`이 필요하다. 의존성까지 자동 설치되는 것은 `.tgz`나 레지스트리의 패키지다.
- **opencode를 이 폴더에서 실행해야 한다.** `src/server.mjs`는 opencode를 실행한 폴더 기준이다 (M1과 같다).
- **미러 환경**: `npm config get registry`가 미러 주소인지 확인한다. `check.py`는 이 주소에 3초 안에 닿지 않고 `node_modules`도 없으면 WARN만 남기고 건너뛴다.
- **`check.py`는 `node_modules`가 없고 레지스트리에 닿으면 이 폴더에서 `npm install`을 실행한다.** 배포 형태 검사는 임시 폴더와 임시 npm 캐시에서 하므로 예제 폴더에 `.tgz`를 남기지 않는다.
- **Windows**: `check.py` 전체를 Windows(PowerShell 5.1, opencode 1.19.5)에서도 실행해 통과했다(`node` 실행, `npm pack` 후 `npx -y ./….tgz` 항목 포함). 위의 시작 시간 표는 Linux에서 잰 값이고 Windows에서는 재지 않았다.
