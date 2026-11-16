# M5 팀이 함께 쓰는 원격 MCP 서버

> 구성: MCP(원격, Streamable HTTP) | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: MCP - 원격·공유 서버

## 무엇을 보여 주나

MCP 서버를 각자 PC 에서 띄우는 대신 **한 곳에서 띄워 두고 팀원이 URL 로 접속**하는 방식입니다. 서버는 표준 라이브러리만 쓴
Python 파일 하나(`server.py`)이고, 팀원은 같은 `opencode.json` 을 그대로 복사해 쓰면서 **자기 토큰만 환경 변수로** 넣습니다.
토큰마다 사용자 이름이 붙기 때문에 서버에는 "누가, 어떤 도구를, 언제 불렀는지" 감사 로그가 남습니다.

공유 도구 두 개:

| 도구 | 설명 |
|---|---|
| `oncall_lookup(team, date?)` | `oncall.json` 에서 팀의 온콜 당번(1차/2차) 조회. 날짜를 생략하면 오늘(일정표 밖이면 주간 순환 배정) |
| `team_status()` | `status.json` 의 서비스 상태(ok / degraded / maintenance) 요약 |

## 실무에서는

- 온콜표, 서비스 상태, 배포 일정, 코드 오너 표처럼 **팀 전체가 같은 값을 봐야 하는 정보**를 에이전트에게 주고 싶을 때.
- 서버 코드를 고치면 **서버만 다시 띄우면** 모두에게 반영됩니다. 팀원 PC 마다 파일을 배포하고 버전을 맞출 필요가 없습니다.
- 접근 기록이 필요할 때: 토큰 = 사용자이므로 감사 로그에 이름이 남습니다. 퇴사·교체 시에는 토큰 한 줄만 지우면 됩니다.

## 파일 구성

```
m5-team-shared-server/
├── README.md
├── server.py        # 원격 MCP 서버 (표준 라이브러리, --host / --port / --tokens ...)
├── tokens.json      # {"토큰": "사용자"} - 가짜 값. 요청마다 다시 읽으므로 수정에 재시작이 필요 없음
├── oncall.json      # 온콜 데이터 (가짜)
├── status.json      # 서비스 상태 데이터 (가짜)
├── opencode.json    # 팀원 공용 설정: url 과 토큰을 {env:} 로 받음
├── check.py         # 자동 검증
└── logs/server.log  # (실행하면 생김, git 제외) 감사 로그
```

## 따라 하기

> 평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 `opencode -m opencode/big-pickle` 처럼 무료 모델을 지정하세요.

### 1. 서버 띄우기 (터미널 1)

PowerShell:

```powershell
cd examples\02-mcp\m5-team-shared-server
python server.py
```

Linux (bash) - `python` 명령이 없으면 `python3` 로 바꾸세요:

```bash
cd examples/02-mcp/m5-team-shared-server
python3 server.py
```

기본은 `127.0.0.1:3918` 입니다(내 컴퓨터에서만 접속 가능). 다른 팀원이 접속하게 하려면 `--host 0.0.0.0` 를 쓰세요(아래 "공유할 때 주의").

### 2. 팀원 쪽: 환경 변수 두 개만 설정하고 opencode 실행 (터미널 2)

PowerShell:

```powershell
$env:TEAM_MCP_URL   = "http://127.0.0.1:3918/"      # 팀 서버 주소로 바꿈
$env:TEAM_MCP_TOKEN = "demo-token-bob-1"            # 내 토큰
opencode mcp list                                    # ✓ team-shared connected
opencode
```

Linux (bash):

```bash
export TEAM_MCP_URL=http://127.0.0.1:3918/
export TEAM_MCP_TOKEN=demo-token-bob-1
opencode mcp list
opencode
```

### 3. 프롬프트

```
team-shared MCP 의 oncall_lookup 으로 platform 팀의 2026-11-18 온콜 1차 담당자가 누구인지 알려 줘.
```
```
team_status 로 지금 정상이 아닌 서비스가 뭔지 알려 줘.
```

답에 `⚙ team-shared_oncall_lookup {...}` 줄이 보이고 "1차 carol, 2차 alice" 가 나오면 성공입니다.
서버 터미널(터미널 1)에는 이렇게 감사 로그가 찍힙니다.

```
2026-11-17T01:20:11+09:00 user=bob tool=oncall_lookup {"team": "platform", "date": "2026-11-18"} -> ok
```

### 4. 자동 검증

```powershell
python check.py          # Linux: python3 check.py
```

## 기대 결과

서버를 직접 호출해 본 실제 출력(Linux):

```
$ curl -i -X POST localhost:3918/ -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="team-shared"

$ curl -X POST localhost:3918/ -H 'Authorization: Bearer demo-token-alice-1' \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"oncall_lookup","arguments":{"team":"platform","date":"2026-11-18"}}}'
{"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "platform 팀 온콜 (2026-11-18): 1차 carol, 2차 alice (근무 기간 2026-11-16 ~ 2026-11-22)"}], "isError": false}}
```

서버 stderr 와 `logs/server.log` (같은 내용):

```
2026-11-17T00:47:44+09:00 user=- auth POST from=127.0.0.1 -> denied(401)
2026-11-17T00:47:44+09:00 user=alice tool=oncall_lookup {"team": "platform", "date": "2026-11-18"} -> ok
2026-11-17T00:47:44+09:00 user=bob tool=team_status {} -> ok
```

`opencode mcp list` (실제 출력):

```
●  ✓ team-shared connected          # 토큰이 맞을 때
●  ✗ team-shared failed             # 토큰이 틀릴 때
│      SSE error: Non-200 status code (401)
●  ✗ team-shared failed             # TEAM_MCP_URL 이 비어 있을 때
│      Invalid MCP URL for "team-shared"
```

모델이 도구를 부르는 transcript 는 `check.py` 가 스크립트된 가짜 모델로 확인했습니다(`⚙ team-shared_oncall_lookup` 호출, 결과에 carol, 서버 로그에 `user=bob`).
실제 모델로 돌린 transcript 는 이 문서를 쓰는 시점에 무료 모델 한도가 소진되어 **확인하지 못했습니다**(`python check.py --model` 로 확인).

## 동작 원리

1. `opencode.json` 의 `"type": "remote"` 항목이 `url` 로 POST 요청(JSON-RPC)을 보냅니다. 서버는 `application/json` 으로 답하고, 알림(`notifications/initialized`)에는 `202` 를 줍니다. 이것이 Streamable HTTP 의 가장 단순한 형태입니다.
2. `"url": "{env:TEAM_MCP_URL}"` - **`url` 안에서도 `{env:}` 가 치환됩니다**(확인: `opencode debug config` 에 실제 주소가 나옴). 헤더(`Authorization: Bearer {env:TEAM_MCP_TOKEN}`)도 마찬가지입니다.
   덕분에 모든 팀원이 **똑같은 `opencode.json`** 을 쓰고, 서버 주소와 개인 토큰만 환경 변수로 다릅니다. 파일은 저장소에 커밋해도 비밀이 들어 있지 않습니다.
3. 서버는 요청마다 `Authorization: Bearer <토큰>` 을 `tokens.json` 에서 찾아 사용자 이름을 얻습니다. 없으면 `401`.
4. `tools/call` 이 오면 도구를 실행하고, **사용자·도구·인자·결과**를 감사 로그 한 줄로 stderr 와 `logs/server.log` 에 남깁니다.
5. 도구 이름은 모델에게 `team-shared_oncall_lookup` 처럼 `<서버이름>_<도구이름>` 으로 보입니다.

### `"oauth": false` 는 왜 넣었나 (확인)

`oauth` 키를 빼도 토큰이 맞으면 똑같이 연결됩니다. 차이는 **틀린 토큰일 때의 진단 메시지**입니다.
`"oauth": false` 이면 `SSE error: Non-200 status code (401)` 로 원인이 보이고, 키를 빼면 `failed` 만 나오고 메시지가 비어 있습니다.
그래서 고정 토큰을 쓰는 서버에는 `"oauth": false` 를 권합니다.

### 서버 쪽 작은 설계 결정

- 클라이언트는 POST 가 실패하면 SSE(GET)로도 시도합니다. 서버가 GET 에 405 만 주면 틀린 토큰이 `405` 로 보여 헷갈리므로,
  **GET 도 토큰을 먼저 검사해서 `401`** 을 줍니다(유효한 토큰의 GET 만 405).
- `/healthz` 는 인증 없이 `ok` 를 돌려줍니다. 방화벽·모니터링이 서버 생존만 확인할 때 씁니다.

## 공유할 때 주의

### `127.0.0.1` vs `0.0.0.0`

| 바인딩 | 접속 가능한 곳 | 쓰는 때 |
|---|---|---|
| `127.0.0.1` (기본) | 서버를 띄운 컴퓨터 자신만 | 혼자 시험할 때 |
| `0.0.0.0` | 그 컴퓨터가 가진 **모든 네트워크 주소**에서 접속 가능 | 팀원이 접속해야 할 때 |

`--host 0.0.0.0` 로 열면 서버가 경고를 출력합니다. 열기 전에 확인할 것:

- **방화벽**: 포트 3918 을 팀 네트워크 대역에만 허용하세요. 인터넷에 노출된 서버에 `0.0.0.0` 로 띄우는 것은 위험합니다.
- **토큰은 평문**: 이 예제는 HTTP 입니다. 같은 사무실/VPN 안이 아니라면 앞에 HTTPS 를 끝내 주는 리버스 프록시를 두세요.
- **토큰은 사람마다 따로** 발급하세요. 한 토큰을 공유하면 로그에 누가 불렀는지 남지 않습니다.
- `tokens.json` 의 값은 예제용 가짜입니다. 실제로는 긴 무작위 문자열(예: `python -c "import secrets; print(secrets.token_urlsafe(32))"`)을 쓰고, 파일은 저장소에 올리지 마세요.

### 토큰 교체(rotation)

`tokens.json` 은 요청마다 다시 읽으므로 **서버를 재시작하지 않고** 바꿀 수 있습니다(확인).

1. 새 토큰을 같은 사용자 이름으로 **추가**합니다 (`"새토큰": "alice"`). 이 동안 옛 토큰과 새 토큰이 모두 통합니다.
2. 사용자에게 새 토큰을 전달하고 `TEAM_MCP_TOKEN` 을 바꾸게 합니다.
3. 옛 토큰 줄을 **삭제**합니다. 그 순간부터 옛 토큰은 `401` 입니다.

### 왜 원격이 팀에는 더 쉬운가

- **업데이트가 한 곳**: 도구를 고치거나 데이터(`oncall.json`)를 갱신하면 서버만 다시 띄우면 됩니다. 각자 PC 의 파일·Python·패키지 버전을 맞출 필요가 없습니다.
- **설정이 같음**: `opencode.json` 은 모두 동일, 달라지는 것은 환경 변수 두 개뿐.
- **접근 통제와 기록이 한 곳**: 로그와 토큰 폐기가 서버에서 끝납니다.
- 대신 **서버가 죽으면 모두가 못 씁니다.** 상시 실행(서비스 등록)과 간단한 점검(`/healthz`)이 필요합니다.

## 직접 바꿔 보기

1. `tokens.json` 에 `"demo-token-dana-1": "dana"` 를 추가하고(재시작 없이) 그 토큰으로 `opencode mcp list` 를 실행해 보세요. `logs/server.log` 에 `user=dana` 가 남습니다.
2. `oncall.json` 에 새 팀을 추가하고 서버를 **재시작하지 않은 채** 다시 물어보세요(데이터 파일도 요청마다 읽습니다).
3. `python server.py --host 0.0.0.0 --port 4000` 으로 띄우고 다른 PC(또는 WSL 밖)에서 `TEAM_MCP_URL=http://<서버IP>:4000/` 로 접속해 보세요.

## 주의할 점 / 문제 해결

- `✗ failed` + `SSE error: Non-200 status code (401)`: 토큰이 틀렸습니다. 서버 로그에 `denied(401)` 가 찍힙니다.
- `Invalid MCP URL`: `TEAM_MCP_URL` 이 비어 있거나 설정되지 않았습니다. 환경 변수를 설정한 **같은 터미널**에서 `opencode` 를 실행하세요.
- `ECONNREFUSED`: 서버가 안 떠 있거나 포트/주소가 다릅니다.
- 기본 포트는 3918 입니다(`--port` 로 변경). 이미 사용 중이면 서버가 시작 시 오류를 냅니다.
- `oncall.json` 에는 2026-11-02 ~ 2026-11-29 일정만 들어 있습니다. 이 기간 밖의 날짜(오늘 날짜 포함)로 `oncall_lookup` 을 부르면 서버가 **주간 순환 배정**으로 대신 답합니다. 그 팀의 항목들을 ISO 주 번호 % 항목 수 로 골라 쓰는 데모용 규칙이며, 답변에 "순환 배정"이라고 표시됩니다. 실제 당번표가 아니므로 날짜를 지정하거나 데이터를 갱신하세요. (팀 이름이 틀렸을 때만 오류가 납니다.)
- Windows 에서 `logs/server.log` 는 UTF-8 로 기록됩니다. 메모장 대신 VS Code 등으로 여세요.
