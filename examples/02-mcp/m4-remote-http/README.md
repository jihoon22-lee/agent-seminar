# M4 원격 MCP 서버 (Streamable HTTP)

> 구성: 서버 1개(stdio/HTTP 겸용) + remote 설정 + HTTP 관찰 스크립트 | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, 터미널 2개 | 슬라이드: MCP — 로컬 vs 원격

## 무엇을 보여 주나

M1~M3의 서버는 **opencode가 프로세스를 직접 띄우는** 로컬(stdio) 서버였다. 이번에는 같은 서버를 `--http`로 **미리 켜 두고**,
opencode는 URL과 토큰으로 접속만 한다. 메시지 내용(JSON-RPC)은 똑같고 실어 나르는 길만 stdin/stdout에서 HTTP POST로 바뀐다.
누가 프로세스를 띄우는지, 어디서 실행되는지, 인증을 어떻게 하는지가 달라진다는 점이 이 예제의 핵심이다.

## 실무에서는

- 팀 공용 서버 한 대에 MCP 서버(팀 지식 검색, 배포 상태 조회 등)를 올려 두고 모두가 URL만 등록한다. 서버는 한 번만 업데이트하면 된다.
- 접속 대상 시스템의 비밀 값(DB 비밀번호, 외부 API 키)을 **서버 쪽에만** 두고, 사용자는 접속용 토큰 하나만 가진다.
- 개발 중에는 `127.0.0.1`에서 `--http`로 띄워 `curl`/`http_probe.py`로 요청을 직접 던져 보며 디버깅한다. 에이전트 없이도 서버를 시험할 수 있다는 장점이 크다.

## 파일 구성

```
m4-remote-http/
  README.md        이 문서
  server.py        M3와 같은 용어집 서버. 기본은 stdio, --http 를 주면 Streamable HTTP 서버
  glossary.json    용어집 (M1과 같은 14개)
  opencode.json    mcp.glossary-remote: type "remote", url, headers({env:DEMO_TOKEN}), oauth false
  http_probe.py    urllib으로 서버에 요청을 보내고 HTTP 요청/응답을 그대로 출력
  check.py         자동 검증 (서버를 직접 띄우고 끝에 종료)
  fake_llm.py      가짜 LLM 서버. check.py 가 모델 없이 opencode 의 요청을 기록·재현하는 데 씀
```

## 따라 하기

> Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. 포트는 `3917`이다 (`--port`로 바꿀 수 있고, 바꾸면 `opencode.json`의 `url`도 같이 바꾼다).

터미널 두 개를 연다. 둘 다 `examples/02-mcp/m4-remote-http` 폴더에서 시작한다.

**터미널 1 — 서버 켜기** (이 터미널은 서버가 점유한다. 종료는 `Ctrl+C`)

```powershell
$env:API_TOKEN = "demo-token-123"
python server.py --http
```

```bash
API_TOKEN=demo-token-123 python3 server.py --http
```

출력: `[glossary-remote] INFO HTTP 모드 시작: http://127.0.0.1:3917/mcp  (Bearer 토큰 필요, 종료는 Ctrl+C)`

**터미널 2 — 원시 HTTP 먼저 보기**

```powershell
$env:DEMO_TOKEN = "demo-token-123"
python http_probe.py
```

```bash
DEMO_TOKEN=demo-token-123 python3 http_probe.py
```

**터미널 2 — opencode로 접속**

```powershell
$env:DEMO_TOKEN = "demo-token-123"
opencode mcp list
opencode
```

```bash
export DEMO_TOKEN=demo-token-123
opencode mcp list
opencode
```

프롬프트에 입력 (평소 쓰는 모델로 충분하다):

```
glossary-remote 도구로 ADR이 무슨 뜻인지 찾아줘. 그리고 server_info로 이 서버가 stdio인지 http인지도 알려줘
```

모델 설정이 없다면 `opencode run -m opencode/big-pickle --auto "<위 문장>"`으로 한 번에 실행할 수 있다.

**실험 1 — 토큰이 틀리면?**

```powershell
$env:DEMO_TOKEN = "wrong-token"
opencode mcp list
```

```bash
DEMO_TOKEN=wrong-token opencode mcp list
```

**실험이 끝나면 올바른 토큰으로 되돌린다.** PowerShell의 `$env:` 값은 그 창에 계속 남으므로, 되돌리지 않으면 이후 단계가 계속 `401`이 된다.

```powershell
$env:DEMO_TOKEN = "demo-token-123"
```

```bash
export DEMO_TOKEN=demo-token-123   # 위에서 'DEMO_TOKEN=... opencode ...' 한 줄 형태로만 썼다면 이 창에는 남지 않아 필요 없다
```

**실험 2 — 서버를 끄면?** 터미널 1에서 `Ctrl+C`를 누른 뒤 `opencode mcp list`를 실행한다.

## 기대 결과

`opencode mcp list` (서버가 켜져 있고 토큰이 맞을 때):

```
●  ✓ glossary-remote connected
│      http://127.0.0.1:3917/mcp
```

토큰이 틀릴 때(`oauth: false` 상태):

```
●  ✗ glossary-remote failed
│      SSE error: Non-200 status code (401)
```

서버가 꺼져 있을 때:

```
●  ✗ glossary-remote failed
│      SSE error: ECONNREFUSED: Unable to connect. Is the computer able to access the url?
```

`http_probe.py`의 일부 (서버가 실제로 돌려준 응답):

```
== 3. initialize -> 200, 본문은 JSON-RPC 응답 (stdio의 한 줄과 같은 내용)
  > POST /mcp HTTP/1.1
  > Accept: application/json, text/event-stream
  > Content-Type: application/json
  > Authorization: Bearer ***
  > {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", ...}}
  < HTTP 200 OK
  < Content-Type: application/json; charset=utf-8
  < {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}, "serverInfo": {"name": "glossary-m4", "version": "1.0.0"}}}

== 4. 알림(id 없음) -> 202 Accepted, 본문 없음
  < HTTP 202 Accepted

== 7. GET -> 405 (이 서버는 서버 푸시용 SSE 스트림을 제공하지 않는다)
  < HTTP 405 Method Not Allowed
  < Allow: POST
```

opencode에서 질문하면 모델이 부르는 도구가 `⚙ glossary-remote_lookup_term {...}`, `⚙ glossary-remote_server_info`처럼 `서버이름_도구이름`으로 보인다.

## 로컬 vs 원격

| | 로컬 (M1~M3, stdio) | 원격 (M4, Streamable HTTP) |
|---|---|---|
| 프로세스를 누가 띄우나 | **opencode**가 `command`를 실행하고, 끝나면 함께 종료 | **사람(또는 서비스 관리자)**이 미리 켜 둔다. opencode는 접속만 한다 |
| 어디서 실행되나 | 내 PC, opencode의 자식 프로세스 | 어디든 (같은 PC의 다른 터미널, 팀 공용 서버, 컨테이너) |
| 설정 항목 | `type: "local"`, `command`, `environment` | `type: "remote"`, `url`, `headers`, `oauth` |
| 인증 | 필요 없음 (내 PC의 내 프로세스). 서버가 쓸 비밀 값은 `environment`로 전달 | 서버가 요청마다 확인한다: `Authorization: Bearer <토큰>` → 틀리면 `401` |
| 비밀 값이 있는 곳 | 각 사용자의 PC (`{env:}`/`{file:}`) | 서버 쪽에 두고, 사용자는 접속 토큰만 가진다 |
| 서버 업데이트 | 사용자마다 코드를 받아야 함 | 서버 한 곳만 갱신 |
| 동시에 여러 명이 쓰면 | 각자 자기 프로세스 | 한 프로세스를 공유 (동시 요청 처리, 로그 분리를 고려해야 함) |
| 실패 모습 | 프로세스가 죽으면 `failed` (Linux에서 없는 스크립트를 가리키면 약 2초 만에 `MCP error -32000: Connection closed`. Windows에서는 다를 수 있다, 미확인) | 서버가 꺼져 있으면 `ECONNREFUSED`, 토큰이 틀리면 `401` |
| 네트워크 노출 | 없음 | 포트를 연다 → 바인딩 주소와 토큰이 보안의 전부 |

## 동작 원리

### Streamable HTTP 최소 규칙 (이 서버가 지키는 것)

| 요청 | 응답 |
|------|------|
| `POST /mcp` + JSON-RPC **요청**(id 있음) | `200`, `Content-Type: application/json`, 본문 = JSON-RPC 응답 |
| `POST /mcp` + JSON-RPC **알림**(id 없음) | `202 Accepted`, 본문 없음 |
| `GET /mcp` | `405 Method Not Allowed` (서버가 먼저 말을 거는 SSE 스트림을 제공하지 않음) |
| `Authorization: Bearer <토큰>` 불일치/없음 | `401` + `WWW-Authenticate: Bearer` (GET에도 똑같이 적용) |
| `Origin` 헤더가 있는데 localhost가 아님 | `403` (웹페이지를 통한 DNS 리바인딩 공격 방어) |
| `/mcp`가 아닌 경로 | `404` |
| 깨진 JSON | `400` + JSON-RPC `-32700` |

서버가 줄 수 있는 응답 형식은 `application/json` 하나뿐이다. 클라이언트는 `Accept: application/json, text/event-stream`을 보내므로 서버가 두 형식 중 JSON을 고른 것이다. 이 정도면 opencode 1.19.5는 아무 문제 없이 동작한다.

### opencode 1.19.5가 접속하는 순서 (서버 로그로 확인)

1. `POST /mcp` `initialize` — `protocolVersion: "2025-11-25"`, `User-Agent: opencode/1.19.5`. 이때는 `MCP-Protocol-Version` 헤더가 없다.
2. `POST /mcp` `notifications/initialized` — 이 이후의 요청부터 `MCP-Protocol-Version: 2025-11-25` 헤더가 붙는다. 서버는 `202`.
3. `GET /mcp` (`Accept: text/event-stream`) — 서버가 보내는 이벤트 스트림을 열어 보려는 시도. 서버가 `405`로 거절해도 접속은 계속된다.
4. `POST /mcp` `tools/list`, 그리고 이후 `tools/call`.

세션 ID(`Mcp-Session-Id`)는 쓰지 않는 서버다. 요청이 서로 독립적이어서 서버를 재시작해도 클라이언트가 다시 `initialize`만 하면 된다.

### `Authorization` 헤더와 `{env:DEMO_TOKEN}`

```json
"glossary-remote": {
  "type": "remote",
  "url": "http://127.0.0.1:3917/mcp",
  "headers": { "Authorization": "Bearer {env:DEMO_TOKEN}" },
  "oauth": false,
  "enabled": true
}
```

`headers` 값 안의 `{env:DEMO_TOKEN}`은 M3에서 본 것과 같은 치환이다. 환경 변수가 없으면 빈 문자열이 되어 `Authorization: Bearer`(뒤가 빔)가 전송되고 서버는 `401`을 낸다.
서버 쪽 기대값은 환경 변수 `API_TOKEN`이다. **클라이언트와 서버는 서로 다른 프로세스라 환경 변수 이름도 따로 정할 수 있다** (여기서는 서버 `API_TOKEN`, 클라이언트 `DEMO_TOKEN`). 두 값이 같아야 접속된다.

`opencode debug config`에서는 원격 `headers`의 값이 전부 `***`로 가려진다.

### `"oauth": false`를 넣는 이유 (직접 실험한 결과)

`oauth` 키는 `type: "remote"` 항목에서 허용되고, `false`를 넣으면 설정 검증을 통과한다. 접속이 **성공할 때는 아무 차이가 없다.** 차이는 서버가 `401`을 낸 뒤에 생긴다.

| | `oauth` 키 없음 | `"oauth": false` |
|---|---|---|
| 401을 받은 뒤 | opencode가 OAuth 로그인 절차를 찾아 나선다: `GET /.well-known/oauth-protected-resource`, `/.well-known/oauth-authorization-server`, `/.well-known/openid-configuration`, 그리고 `POST /register`까지 시도하고, 이를 두 차례 반복한다 (서버 로그에 요청이 여러 줄 찍힌다) | 이런 탐색 요청이 **전혀 없다** |
| `opencode mcp list`의 오류 메시지 | 빈 줄 (원인이 안 보인다) | `SSE error: Non-200 status code (401)` |

즉 **고정 토큰을 헤더로 보내는 서버에는 `"oauth": false`를 넣는 것이 좋다.** 불필요한 OAuth 탐색 요청을 막고 `401`이라는 진짜 원인이 화면에 나온다. 서버가 OAuth를 쓰는 경우(브라우저 로그인이 필요한 서비스)에는 키를 생략하고 `opencode mcp auth`를 쓴다.

오류 메시지가 `SSE error`로 시작하는 이유: 서버 로그를 보면 opencode는 Streamable HTTP 접속(`POST`)이 실패한 뒤 `GET /mcp`(`Accept: text/event-stream`)로 옛 방식인 SSE 전송을 한 번 더 시도하는 것으로 보이고, **마지막 시도의 오류**를 화면에 보여 준다. 이 때문에 `401` 서버가 GET에도 인증을 요구하지 않으면 마지막 오류가 `405`로 나와 원인이 가려진다. 이 서버는 `GET`에도 인증을 먼저 확인해 `401`이 보이게 했다.

### 서버 구현 포인트 (`server.py`)

- `handle(msg)`와 도구 코드는 stdio와 HTTP가 **똑같이** 쓴다. `serve_stdio()`는 줄 단위로 읽고, `McpHandler`는 POST 본문을 읽는다.
- 응답 본문은 `json.dumps(...).encode("utf-8")`로 UTF-8 바이트를 만들고 `Content-Type: application/json; charset=utf-8`을 붙인다. 파이썬의 기본 인코딩(Windows cp949)에 기대지 않으므로 한글이 안전하다.
- `ThreadingHTTPServer`를 쓰고 `protocol_version = "HTTP/1.1"`로 연결을 재사용(keep-alive)한다. 그래서 `202`/`405` 응답에도 `Content-Length: 0`을 반드시 붙인다.
- 토큰 비교는 `hmac.compare_digest`(상수 시간 비교)로 한다.
- `API_TOKEN` 없이 `--http`로 시작하면 서버가 거부하고 종료한다. 토큰 없는 서버가 실수로 열리는 것을 막는 "안전한 기본값"이다.
- 기본 바인딩은 `127.0.0.1`이다. 같은 PC에서만 접속된다.

## 직접 바꿔 보기

1. **포트 바꾸기** — `python server.py --http --port 4000`으로 켜고 `opencode.json`의 `url`을 `http://127.0.0.1:4000/mcp`로 바꿔 접속해 본다.
2. **서버 재시작** — opencode를 켜 둔 채 터미널 1에서 서버를 껐다 켜고, 다음 질문이 어떻게 되는지 관찰한다. (opencode를 재시작해야 할 수도 있다.)
3. **로컬 항목과 비교** — `opencode.json`의 `mcp`에 같은 `server.py`를 stdio로 띄우는 항목(`"glossary-local": {"type": "local", "command": ["python", "server.py"], "environment": {"API_TOKEN": "demo-token-123"}}`)을 추가한다. 같은 도구가 `glossary-local_...`와 `glossary-remote_...` 두 이름으로 보이고, 어느 쪽이 호출됐는지는 `server_info`의 `TRANSPORT=stdio`/`http`와 `PID`로 구분할 수 있다.
4. **`oauth` 키 빼 보기** — `"oauth": false`를 지우고 토큰을 틀리게 해서 서버 로그에 어떤 요청이 몰려오는지 본다. (`LOG_LEVEL=DEBUG`로 서버를 켜면 모든 요청 경로가 보인다.)

## 주의할 점 / 문제 해결

- **`--host 0.0.0.0`으로 바꾸면 같은 네트워크의 모든 PC에서 접속할 수 있다.** 이 예제의 서버는 평문 HTTP이므로 토큰이 네트워크에서 그대로 보인다. 공용 서버로 쓸 때는 앞단에 HTTPS 프록시를 두고, 토큰은 사용자별로 발급·폐기할 수 있게 해야 한다. 이 예제는 개념을 보여 주는 최소 구현이라 그런 기능이 없다.
- **포트 충돌** — `3917`이 이미 사용 중이면 서버가 `Address already in use`로 종료한다. 이전에 켜 둔 서버를 먼저 끄거나 `--port`를 바꾼다.
- **토큰을 정했는데도 `401`** — 서버 터미널의 `API_TOKEN`과 opencode 터미널의 `DEMO_TOKEN`이 다른 창의 변수일 수 있다. PowerShell의 `$env:...`은 그 창에서만 유효하다. 값 끝에 공백이 붙지 않았는지도 확인한다.
- **`opencode mcp list`에 `SSE error` 라고만 나온다** — 서버가 꺼졌거나(`ECONNREFUSED`), 인증 실패(`401`), 경로 오류(`404`)다. 괄호 안의 숫자가 단서다. `oauth` 키가 없으면 인증 실패 메시지가 비어 보일 수 있다.
- **`http_probe.py`가 "서버에 접속하지 못했습니다"** — 터미널 1에서 서버를 먼저 켰는지 확인한다.
- **Windows 방화벽 알림** — `127.0.0.1` 바인딩에서는 보통 뜨지 않는다. `0.0.0.0`으로 열면 허용 여부를 묻는 창이 뜰 수 있다.
