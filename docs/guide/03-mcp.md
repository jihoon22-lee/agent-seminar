# 3. MCP: 에이전트에 도구를 꽂는 표준 규격

이 문서는 세미나 5장 "MCP"를 글로 옮긴 것입니다. stdio 프로토콜의 속, 표준 라이브러리로 서버를 만드는 방법과 공식 SDK를 쓰는 방법, 로컬과 원격(Streamable HTTP)의 차이, 토큰 넘기기, resources와 prompts, 켜고 끄고 막기, 토큰 비용, 시간 제한, Windows 인코딩, 디버깅을 다룹니다.
모든 내용은 **opencode 1.19.5** 기준입니다.

관련 예제: [M1 stdio 최소 서버](../../examples/02-mcp/m1-stdio-minimal/) · [M2 공식 SDK](../../examples/02-mcp/m2-python-sdk/) · [M3 환경 변수](../../examples/02-mcp/m3-env-config/) · [M4 원격 HTTP](../../examples/02-mcp/m4-remote-http/) · [M5 팀 공용 서버](../../examples/02-mcp/m5-team-shared-server/) · [M6 티켓 DB](../../examples/02-mcp/m6-sqlite-tickets/) · [M7 resources와 prompts](../../examples/02-mcp/m7-resources-prompts/) · [M8 켜고 끄고 막기](../../examples/02-mcp/m8-enable-disable-deny/) · [M9 디버깅 갤러리](../../examples/02-mcp/m9-pitfalls/)

## MCP 서버는 마법 상자가 아닙니다

MCP 서버는 **표준 입력으로 JSON 한 줄을 받고, 표준 출력으로 JSON 한 줄을 돌려주는 프로그램**입니다. 서버가 할 일은 네 가지뿐입니다.

1. `initialize`에 답한다: 프로토콜 버전, 할 수 있는 일(`capabilities`), 서버 이름
2. `tools/list`에 도구 목록을 준다: 이름, 설명, 인자 스키마
3. `tools/call`을 실행하고 결과를 `content`로 돌려준다
4. `id`가 없는 **알림에는 절대 답하지 않는다.** 모르는 알림은 조용히 무시한다

opencode가 실제로 보내는 값입니다 (예제 서버의 로그와 가짜 모델 서버로 기록).

| 항목 | 값 |
|---|---|
| `protocolVersion` | `2025-11-25` |
| `clientInfo` | `opencode` `1.19.5` |
| 호출이 끝난 뒤 | `notifications/cancelled` 알림을 보내기도 함 (답하면 안 됨) |
| 모델이 보는 도구 이름 | `서버이름_도구이름` (예: `glossary_lookup_term`) |
| 연결 제한 시간 | 약 30초 (시작 + `initialize` + `tools/list`) |
| 호출 제한 시간 | 약 60초 |

서버가 아는 버전이면 그대로 되돌려 주고, 모르는 버전이면 서버의 최신 버전을 제안합니다.

[M1](../../examples/02-mcp/m1-stdio-minimal/)의 `raw_session.py`는 서버를 직접 띄워 주고받는 JSON을 한 줄씩 보여 줍니다. 서버를 만들 때 opencode 없이 먼저 이것으로 확인하면 편합니다.

PowerShell:
```powershell
cd examples\02-mcp\m1-stdio-minimal
python raw_session.py
opencode mcp list
```
Linux bash:
```bash
cd examples/02-mcp/m1-stdio-minimal
python3 raw_session.py
opencode mcp list
```

설정은 이만큼입니다.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "glossary": {
      "type": "local",
      "command": ["python", "server.py"],
      "enabled": true
    }
  }
}
```

`command`는 **설정 파일 위치가 아니라 opencode를 실행한 폴더** 기준으로 실행됩니다. 하위 폴더에서 실행하면 서버 파일을 못 찾아 30초 뒤 `failed`가 됩니다. Linux에서 `python`이 없으면 `["python3", "server.py"]`로 바꿉니다.

### 오류는 두 종류입니다

| 상황 | 표현 | 의미 |
|---|---|---|
| 모르는 method | `error.code = -32601` | 프로토콜 오류: 이 서버는 그 기능이 없다 |
| 모르는 도구 이름, 필수 인자 누락 | `error.code = -32602` | 프로토콜 오류: 요청 자체가 잘못됐다 |
| 깨진 JSON 줄 | `error.code = -32700` | 프로토콜 오류 |
| 용어가 없다 | `result.isError = true` | **도구 오류**: 도구는 정상이고 결과가 실패다 |

도구 오류(`isError: true`)는 모델이 메시지를 읽고 **스스로 다시 시도**할 수 있게 하려는 것입니다. 그래서 "비슷한 용어: 카나리 배포"처럼 다음 행동의 단서를 메시지에 넣습니다.

### 도구 설명이 곧 설명서입니다

모델은 도구의 `description`과 `inputSchema`만 보고 도구를 고릅니다. 스킬의 description과 같은 원리입니다. 설명에는 다음을 담습니다.

- 무엇을 하는지
- 언제 쓰는지 (예시 단어 포함)
- 다른 도구와 어떻게 이어지는지 ("모를 때 먼저 사용한다")
- 형식과 허용 값 (날짜는 `YYYY-MM-DD`, `service`는 `enum`으로 후보 전체)
- 한계 ("최대 20건, 많으면 조건을 좁혀 다시 호출")

이 설명은 서버를 켜 두는 동안 **매 요청마다** 모델에게 전달됩니다. 길게 쓰면 그만큼 비용이 듭니다. ("토큰 비용" 절 참고)

## 서버 만들기: 표준 라이브러리 vs 공식 SDK

같은 용어집 서버를 두 방식으로 만든 것이 M1과 M2입니다.

| | M1 표준 라이브러리 | M2 공식 SDK |
|---|---|---|
| 코드 | 124줄 | 24줄 (주석, 빈 줄, docstring 제외) |
| 시작 시간 | 0.02초 | 0.7~1초 |
| 설치 | 없음 | 28개 패키지, 58MB |
| 도구 정의 | JSON을 직접 작성 | 함수, 타입 힌트, docstring |
| 가상환경 | 필요 없음 | OS마다 경로가 다름 |

**실무에서는 SDK를 씁니다.** 다만 SDK가 하는 일을 알고 쓰면 문제가 생겼을 때 훨씬 빨리 찾습니다. 설치 없이 어디서나 돌아야 하는 작은 서버라면 표준 라이브러리도 현실적입니다.

SDK 쪽은 이렇게 생겼습니다 ([M2](../../examples/02-mcp/m2-python-sdk/)의 `server.py` 일부).

```python
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("glossary-m2", version="1.0.0")

@mcp.tool()
def lookup_term(term: Annotated[str, Field(description="찾을 용어. 예: 'ADR', '카나리 배포'")]) -> str:
    """팀 용어집에서 용어 하나의 뜻을 찾는다.
    ...
    """
    ...
    raise ToolError(f"'{term}'은(는) 용어집에 없습니다. list_terms로 전체 목록을 볼 수 있습니다.")

if __name__ == "__main__":
    mcp.run()  # 기본이 stdio
```

함수 이름이 도구 이름, docstring이 `description`, 타입 힌트가 `inputSchema`가 됩니다. `ToolError`는 `isError: true` 결과로 바뀝니다.

SDK를 쓸 때의 주의점입니다.

- **가상환경의 파이썬을 `command`에 직접 적습니다.** `activate` 같은 셸 상태에 의존하지 않기 위해서입니다. 경로가 Windows는 `.venv/Scripts/python.exe`, Linux는 `.venv/bin/python`으로 달라서, M2는 `prepare.py`가 현재 OS용 `opencode.json`을 만들어 줍니다. `.venv`도 OS별로 따로 만들어야 합니다. Linux에서 만든 것을 Windows로 복사하면 동작하지 않습니다.
- **`mcp` 패키지 2.0부터 `FastMCP`가 `MCPServer`로 바뀌었습니다.** import 경로도 `mcp.server.mcpserver`입니다. 인터넷 예제 대부분(1.x)의 `from mcp.server.fastmcp import FastMCP`는 2.x에서 `ModuleNotFoundError`가 납니다. 그 예제를 그대로 쓰려면 `mcp<2`로 고정하세요.
- 인터넷이 막힌 환경에서는 `pip` 설치에 패키지 미러 주소가 필요합니다.
- stdout에 `print`를 쓰면 안 된다는 규칙은 SDK를 써도 같습니다.

### stdout은 프로토콜 전용입니다

서버의 `print()`가 stdout에 한 줄이라도 쓰면 opencode는 그 줄을 JSON-RPC로 읽으려다 실패할 수 있습니다. 로그, 배너, 디버깅 출력은 모두 **stderr**로 보냅니다. [M9](../../examples/02-mcp/m9-pitfalls/)가 1.19.5에서 관찰한 정확한 동작은 이렇습니다.

| 서버가 stdout에 한 짓 | 결과 |
|---|---|
| 줄바꿈 있는 잡음 한 줄 (`print("배너")`) | 무시되고 정상 동작 |
| **줄바꿈 없는** 잡음 (`print("...", end="")`) | 다음 JSON 응답 앞에 붙어 그 줄이 통째로 깨짐 → 제한 시간 뒤 `failed` |

"배너가 있어도 되더라"는 우연일 뿐입니다. 규칙은 단순하게 **stdout에는 MCP 메시지만**입니다. 디버깅하다 무심코 넣은 `print("here")`가 가장 흔한 MCP 서버 오류입니다.

## 로컬과 원격

| | 로컬 (`"type": "local"`) | 원격 (`"type": "remote"`) |
|---|---|---|
| 누가 실행 | opencode가 프로세스를 띄운다 | 미리 떠 있는 서버에 접속한다 |
| 통신 | stdio | Streamable HTTP |
| 설정 | `command`, `environment` | `url`, `headers`, `oauth` |
| 인증 | 내 PC 권한 그대로 | 토큰 헤더 또는 OAuth |
| 업데이트 | 각자 PC에서 | 서버 한 곳에서 |

로컬에서 원격으로 바꿀 때 서버 코드는 거의 그대로이고 설정만 `command`에서 `url`로 바뀝니다. 대신 인증과 오류 메시지 해석이 새로 생깁니다.

### 원격 서버의 최소 규칙 (Streamable HTTP)

[M4](../../examples/02-mcp/m4-remote-http/)의 서버가 지키는 규칙입니다.

| 요청 | 응답 |
|---|---|
| `POST /mcp` + JSON-RPC 요청(id 있음) | `200`, `application/json`, 본문 = JSON-RPC 응답 |
| `POST /mcp` + 알림(id 없음) | `202 Accepted`, 본문 없음 |
| `GET /mcp` | `405` (서버가 먼저 말을 거는 SSE 스트림을 제공하지 않음) |
| `Authorization` 불일치 | `401` + `WWW-Authenticate: Bearer` (GET에도 적용) |
| 깨진 JSON | `400` + `-32700` |

opencode 1.19.5는 `initialize` → `notifications/initialized` → `GET /mcp`(405를 받아도 계속) → `tools/list` → `tools/call` 순서로 접속합니다. `initialize` 이후의 요청에는 `MCP-Protocol-Version: 2025-11-25` 헤더가 붙습니다.

### 토큰은 헤더로, 값은 환경 변수로

```json
"glossary-remote": {
  "type": "remote",
  "url": "http://127.0.0.1:3917/mcp",
  "headers": { "Authorization": "Bearer {env:DEMO_TOKEN}" },
  "oauth": false,
  "enabled": true
}
```

- `headers`와 `url` 안에서도 `{env:}`가 치환됩니다. 환경 변수가 없으면 빈 문자열이 되어 `Authorization: Bearer`(뒤가 빔)가 전송되고 서버는 `401`을 냅니다. ([M5](../../examples/02-mcp/m5-team-shared-server/)는 `"url": "{env:TEAM_MCP_URL}"`까지 환경 변수로 받습니다.)
- 서버와 클라이언트는 다른 프로세스라 환경 변수 이름도 따로 정할 수 있습니다(M4: 서버 `API_TOKEN`, 클라이언트 `DEMO_TOKEN`). 값만 같으면 됩니다.
- `debug config`에서는 원격 `headers`의 값이 전부 `***`로 가려집니다. ([1장](01-config.md)의 마스킹 절)

**고정 토큰을 쓰는 서버에는 `"oauth": false`를 넣으세요.** 접속이 성공할 때는 차이가 없습니다. 서버가 `401`을 낸 뒤가 다릅니다.

| | `oauth` 키 없음 | `"oauth": false` |
|---|---|---|
| 401을 받은 뒤 | OAuth 로그인 절차를 찾아 나선다: `/.well-known/oauth-protected-resource` 등과 `POST /register`까지 시도, 두 차례 반복 | 이런 탐색 요청이 전혀 없다 |
| `mcp list`의 오류 | 빈 줄 (원인이 안 보인다) | `SSE error: Non-200 status code (401)` |

서버가 OAuth를 쓰는 경우(브라우저 로그인이 필요한 서비스)에는 키를 생략하고 `opencode mcp auth`를 씁니다.

오류가 `SSE error`로 시작하는 이유는 opencode가 Streamable HTTP(`POST`) 실패 뒤에 옛 방식인 SSE(`GET`)를 한 번 더 시도하고 **마지막 시도의 오류**를 보여 주기 때문입니다. 그래서 서버는 `GET`에도 인증을 먼저 확인해 `401`이 보이게 해야 합니다. 그렇지 않으면 `405`가 원인을 가립니다.

| `mcp list`의 메시지 | 원인 |
|---|---|
| `SSE error: Non-200 status code (401)` | 토큰이 틀림 |
| `SSE error: ECONNREFUSED ...` | 서버가 꺼져 있거나 주소/포트가 다름 |
| `Invalid MCP URL for "..."` | `url`이 비어 있음 (`{env:}` 미설정) |
| 괄호 안 `404` | 경로 오류 |

### 팀 공용 서버

[M5](../../examples/02-mcp/m5-team-shared-server/)는 서버를 한 곳에 띄우고 팀원이 URL로 접속하는 방식입니다. 팀원은 **같은 `opencode.json`을 그대로** 쓰고 환경 변수 두 개(`TEAM_MCP_URL`, `TEAM_MCP_TOKEN`)만 다릅니다.

PowerShell:
```powershell
$env:TEAM_MCP_URL   = "http://127.0.0.1:3918/"
$env:TEAM_MCP_TOKEN = "demo-token-bob-1"
opencode mcp list
```
Linux bash:
```bash
export TEAM_MCP_URL=http://127.0.0.1:3918/
export TEAM_MCP_TOKEN=demo-token-bob-1
opencode mcp list
```

- 업데이트가 한 곳입니다. 서버만 다시 띄우면 모두에게 반영됩니다.
- 토큰마다 사용자 이름이 붙어 서버에 "누가, 어떤 도구를, 언제 불렀는지" 감사 로그가 남습니다.
- 토큰 교체는 서버 재시작 없이 합니다. 새 토큰을 같은 사용자로 **추가** → 사용자가 환경 변수 교체 → 옛 토큰 줄 **삭제**.
- 대신 서버가 죽으면 모두가 못 씁니다. 상시 실행과 `/healthz` 같은 점검이 필요합니다.
- 기본 바인딩은 `127.0.0.1`(내 컴퓨터만)입니다. `--host 0.0.0.0`은 같은 네트워크의 모든 PC에서 접속을 허용합니다. 예제는 평문 HTTP라 토큰이 네트워크에 그대로 보이므로, 팀 네트워크 밖에는 열지 말고 앞단에 HTTPS 프록시를 두세요.

## 비밀 값과 환경 변수

로컬 서버에는 `environment`로 값을 넘깁니다. [M3](../../examples/02-mcp/m3-env-config/)입니다.

```json
"glossary-env": {
  "type": "local",
  "command": ["python", "server.py"],
  "environment": {
    "GLOSSARY_PATH": "glossary.json",
    "API_TOKEN": "{env:DEMO_API_TOKEN}",
    "LOG_LEVEL": "INFO"
  },
  "enabled": true
}
```

치환 규칙(`{env:}` 미설정은 빈 문자열, `{file:}`는 설정 파일 기준, `${}`는 안 됨)과 `debug config`의 마스킹 규칙은 [1장](01-config.md)에 모아 두었습니다. 서버 쪽 규칙은 이렇습니다.

- 변수가 아예 없을 때와 **빈 문자열**일 때를 둘 다 "없음"으로 취급합니다. `{env:X}`가 미설정이면 빈 문자열이 오기 때문입니다.
- 토큰이 없으면 도구가 `isError: true`로 거절하고, 메시지에 **어떤 설정을 확인해야 하는지** 적습니다. 모델이 사용자에게 그대로 안내할 수 있습니다.
- 토큰 값이나 앞 글자, 길이를 로그와 응답에 노출하지 않습니다.
- 마스킹된 `***`만으로는 값이 비었는지 알 수 없으므로, 서버가 상태를 알려 주는 도구(`server_info`)를 두면 진단하기 쉽습니다.

**MCP 서버의 인증은 파일 직접 접근을 막지 못합니다.** M3를 무료 모델로 돌렸을 때, 모델이 도구의 거절 메시지를 본 뒤 `bash`로 `glossary.json`을 직접 읽어 답을 만들었습니다. 서버의 토큰 검사는 **그 서버의 도구만** 막습니다. 데이터가 에이전트가 읽을 수 있는 곳에 있으면 도구를 막아도 다른 길로 갑니다. 진짜 경계는 `permission`이나 플러그인이고, 민감한 데이터는 원격 서버 뒤에 두는 것이 맞습니다.

## 실제 시스템을 연결할 때: M6의 원칙 세 가지

[M6](../../examples/02-mcp/m6-sqlite-tickets/)는 장애 티켓 DB(가짜 데이터)를 읽기 전용으로 열어 줍니다. 어떤 시스템을 연결하든 같은 원칙입니다.

1. **최소 권한.** DB를 `?mode=ro`로 열어 SQLite가 쓰기를 거부하게 합니다. 모델에게 SQL을 직접 쓰게 하지 않고, 필터는 `?` 바인딩으로만 받으며, 열 이름이 들어가는 곳은 허용 목록으로 제한합니다. 진짜 시스템이라면 서버 코드의 방어에만 기대지 말고 **연결 계정 자체를 읽기 전용**으로 만드세요.
2. **작은 도구.** `search_tickets`, `get_ticket`, `ticket_stats` 세 개만 둡니다. 역할이 겹치지 않으면 모델이 올바른 도구를 고릅니다.
3. **결과 크기 제한.** 기본 10건, 최대 20건, 긴 문장은 120자에서 자릅니다. 잘렸다는 사실(`총 N건 중 최신 M건 표시`)과 다음 행동(조건을 좁혀라)을 알려 줍니다. 도구 결과는 모델의 대화에 그대로 쌓이므로 수백 건을 돌려주면 컨텍스트와 비용이 낭비됩니다.

오류 메시지도 설명서입니다. 잘못된 값에는 "허용 값: payment, auth, ..."를 돌려줘서 모델이 읽고 다시 시도하게 합니다.

## resources와 prompts

MCP 서버는 도구만 주는 것이 아닙니다. [M7](../../examples/02-mcp/m7-resources-prompts/)에서 opencode가 각각을 어디에 노출하는지 확인합니다. 대부분의 서버는 tools만 쓰고, resources와 prompts는 TUI에서 **사람이 고를 때** 빛납니다.

| | 노출 방식 | 쓰는 때 |
|---|---|---|
| prompts | `/서버:프롬프트` 슬래시 명령 (예: `/runbooks:incident-report INC-1`) | 자주 쓰는 질문 틀 |
| resources | TUI에서 `@`로 첨부. 서버에 resources가 있으면 모델에게 `list_mcp_resources`, `read_mcp_resource`, `list_mcp_resource_templates` 도구가 붙음 | 팀 런북처럼 사람이 골라서 첨부할 문서 |

중요한 제약입니다 (모두 1.19.5).

- 서버가 `initialize`의 `capabilities`에 `prompts`, `resources`를 **선언해야** 보입니다. 선언하지 않으면 opencode는 묻지도 않습니다.
- 프롬프트 인자는 opencode가 직접 끼워 넣습니다. 서버의 `prompts/get`에는 사용자 입력이 아니라 **리터럴 `"$1"`** 이 옵니다. 서버는 사용자가 친 값을 볼 수 없으므로 인자로 DB를 조회하거나 값을 검증하는 프롬프트는 기대대로 안 됩니다. 인자를 본문에 그대로 끼워 넣는 프롬프트만 의도대로 동작합니다. 인자가 하나뿐인 프롬프트에 여러 단어를 주면 마지막 자리표시자가 나머지를 전부 받습니다.
- `opencode run`(비대화형)에서는 일부가 막힙니다.

| 하고 싶은 것 | TUI | `opencode run` |
|---|---|---|
| MCP 프롬프트 실행 | `/runbooks:incident-report INC-1` | `--command runbooks:incident-report INC-1` 만 됨 (메시지에 `/명령`을 쓰면 글자 그대로 모델에게 감) |
| 리소스를 `@`로 첨부 | 가능 | **불가** (`-f`는 로컬 파일 경로만 받음) |
| 모델이 리소스를 스스로 읽기 | 가능 | 가능 |

## 켜고, 끄고, 막기, 그리고 비용

MCP 서버를 붙일수록 모델에게 가는 **도구 정의가 매 요청마다** 늘어납니다. 안 쓰는 도구도 컨텍스트를 차지하고, 도구가 많으면 모델이 고르기도 어려워집니다. [M8](../../examples/02-mcp/m8-enable-disable-deny/)입니다.

### 토큰 비용

도구 12개짜리 서버 하나를 켜면 매 요청마다 약 **1,600 토큰**이 늘었습니다 (M8: MCP 도구 정의가 약 180 토큰에서 약 1,789 토큰으로). 대화 20번이면 같은 정의가 20번 전송됩니다. `count_tool_tokens.py`는 `tools/list`의 이름, 설명, 스키마 글자 수를 4로 나눠 어림합니다. 한글은 글자당 토큰이 더 많아 실제로는 더 클 수 있으므로 절대값보다 **서버 간 비교**에 쓰세요.

### 끄는 방법 세 가지

| 방법 | 효과 |
|---|---|
| `"enabled": false` | 서버 프로세스를 띄우지 않고 도구도 목록에 없다. `mcp list`에 `○ disabled`. 상위 설정에서 `false`인 서버를 프로젝트에서 `true`로 켤 수도 있다 |
| `permission`에서 `deny` | 그 도구가 **모델에게 보내는 목록에서 빠진다.** 컨텍스트를 아끼는 효과는 이쪽에서만 난다 |
| `permission`에서 `ask` | 도구는 보이되 호출 때 사용자 허락. 목록 크기는 줄지 않는다. `opencode run`은 `--auto`가 없으면 자동 거절 |

```json
{
  "permission": {
    "ops_noisy_*": "deny",
    "ops_restart": "ask"
  }
}
```

- 규칙은 `<서버>_<도구>` 이름에 걸립니다.
- **나중에 쓴 규칙이 이깁니다.** `{"ops_*": "deny", "ops_status": "allow"}`는 `ops_status`만 살리지만, 순서를 바꾸면 전부 막힙니다.
- 에이전트마다 다르게 줄 수 있습니다. `agent.<이름>.tools`로 `"ops_*": false` 등을 쓰면 그 에이전트에서만 적용됩니다. 전역에서 deny한 도구를 특정 에이전트에서만 되살리는 것도 됩니다.
- 예전 형식의 `"tools": {"x_*": false}`도 같은 `deny` 규칙으로 번역됩니다. 새로 쓸 때는 `permission`을 권장합니다.
- 숨겨진 도구를 모델이 억지로 호출하면 `Model tried to call unavailable tool` 오류가 돌아옵니다.
- `opencode debug agent build`는 권한 규칙과 내장 도구만 보여 주고 MCP 도구 목록은 없습니다. 모델이 실제로 받는 도구는 가짜 모델 서버로 요청 본문을 기록해야 볼 수 있습니다(M8의 `show_model_tools.py`).

안 쓰는 서버는 끄고, 안 쓰는 도구는 deny로 숨기세요.

## 시간 제한

| 상황 | 기본값 | 결과 |
|---|---|---|
| 서버 시작, `initialize`, `tools/list` | 약 30초 | `failed` (`Operation timed out after 30000ms`) |
| 도구 호출 | 약 60초 | 75초 걸린 호출은 약 60초에 `MCP error -32001: Request timed out`이 모델에게 돌아감 |

서버 항목의 `"timeout"`(밀리초)이 이 제한을 바꿉니다. 시작과 `tools/list`뿐 아니라 도구 호출에도 적용되는 것으로 관찰됐습니다(`timeout: 3000`일 때 8초 걸리는 도구 호출이 실패). 최상위 `experimental.mcp_timeout`(밀리초)은 **도구 호출 제한만** 바꿉니다(시작 제한이 아닙니다).

```json
"mcp": {
  "slow-one": { "type": "local", "command": ["python", "slow.py"], "timeout": 15000 }
}
```

시작이 느린 진짜 원인은 보통 무거운 초기화입니다. 입력을 읽기 전에 끝내려 하지 말고, 첫 도구 호출 때 하거나 백그라운드 스레드로 미루세요. 오래 걸리는 도구는 서버 항목의 `timeout`을 늘립니다.

## Windows에서는 인코딩

Windows의 파이썬은 stdin/stdout을 OS 기본 인코딩(한국어 Windows는 cp949)으로 엽니다. MCP는 UTF-8 JSON을 주고받으므로 서버가 보낸 한글이 깨집니다. 가장 위험한 점은 **조용히 틀린다는 것**입니다. `mcp list`는 `connected`이고 도구 호출도 성공으로 보이는데 모델이 받는 텍스트가 `�ȳ��ϼ���`처럼 깨져 있습니다. 사용자가 보낸 한글 인자는 우연히 원래 바이트로 되돌아와 멀쩡해 보여서 원인 찾기가 더 어렵습니다. Linux는 UTF-8이라 문제가 드러나지 않으니 Linux에서만 개발하면 놓칩니다.

서버 맨 위에 다음을 넣습니다.

```python
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
sys.stderr.reconfigure(encoding="utf-8")
```

`newline="\n"`은 Windows가 줄 끝을 `\r\n`으로 바꿔 쓰는 것도 막습니다. 파일은 `open(..., encoding="utf-8")`로 엽니다. `opencode.json`의 `environment`에 `"PYTHONUTF8": "1"`을 주는 우회도 있지만 서버 코드에서 고치는 쪽이 이식성이 좋습니다. 공식 SDK는 stdio를 UTF-8로 직접 다루므로 이 문제가 없습니다.

## 디버깅

MCP 서버가 안 붙을 때 opencode 화면에는 `failed` 한 단어만 보이는 경우가 많습니다. [M9](../../examples/02-mcp/m9-pitfalls/)가 흔한 고장 네 가지를 일부러 만들어 두었습니다.

| 고장 | 보이는 증상 | 원인과 처방 |
|---|---|---|
| stdout 오염 | `failed` (Operation timed out) | 줄바꿈 없이 찍은 배너가 다음 JSON 앞에 붙는다. stdout에는 MCP 메시지만, 로그는 stderr로 |
| 인코딩 | `connected`인데 한글이 깨짐 | 한국어 Windows(cp949)에서만. `sys.stdout.reconfigure(encoding="utf-8")` |
| 느린 시작 | `failed` (약 30초 초과) | 서버별 `timeout`을 늘리거나 무거운 초기화를 첫 호출로 미룬다 |
| 호출 중 예외 | `connected`인데 호출하면 `MCP error -32000: Connection closed` | 서버가 죽고 **그 도구가 목록에서 빠진다.** `try/except`로 감싸 `isError: true`를 반환 |

진단 순서입니다.

1. `opencode mcp list`로 상태를 봅니다. `--print-logs`나 `--log-level DEBUG`를 붙이면 로그가 화면에 나옵니다.
2. **서버를 터미널에서 직접 실행**해 첫 줄을 눈으로 봅니다. 서버가 stderr로 쓴 traceback은 opencode 화면에도 로그 파일에도 나오지 않는 것으로 관찰됐습니다. 직접 실행하거나 서버 안에서 파일 로그(`logging.FileHandler`)를 쓰세요.
3. `opencode debug paths`의 `log` 폴더에서 `opencode.log`를 봅니다. 연결 실패는 `message="server unavailable" ... status=failed`, 호출 중 끊김은 `message="MCP connection closed" server=<서버>`입니다.

호출 중 크래시는 특히 알기 어렵습니다. 원인(`database connection lost`)은 모델에게도 사용자에게도 전달되지 않고 `Connection closed`만 남습니다. 도구 실행을 `try/except`로 감싸 `isError` 결과를 돌려주면 서버가 살아 있고 모델은 `도구 실행 실패: database connection lost`를 읽고 대응할 수 있습니다.

그 밖에 기억할 점입니다.

- 서버를 고친 뒤에는 opencode를 **다시 시작**해야 합니다. 서버는 시작할 때 한 번 띄웁니다.
- opencode를 예제 폴더에서 실행했는지 확인하세요. `command`의 상대 경로는 실행 폴더 기준입니다.
- 스크립트에서 `opencode run`을 띄울 때는 환경 변수 `PWD`를 작업 폴더에 맞추세요. `opencode run`은 프로세스의 cwd가 아니라 `PWD`로 프로젝트 폴더를 정하는 것으로 관찰됐습니다. ([5. 문제 해결](05-troubleshooting.md))
- Linux에서 `python`이 없으면 `Executable not found in $PATH: "python"`으로 실패합니다. `python3`로 바꾸세요.

다음: [4. 플러그인](04-plugins.md)
