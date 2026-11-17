# 3. MCP: 에이전트에 도구를 꽂는 표준 규격

이 문서는 세미나 5장 "MCP"를 글로 옮긴 것입니다. stdio 프로토콜의 속, 표준 라이브러리로 서버를 만드는 방법과 공식 SDK를 쓰는 방법, 로컬과 원격(Streamable HTTP)의 차이, 서버를 실행하는 여러 방법(직접, `npx`, `uvx`, 실행 파일 하나)과 남이 만든 서버 가져다 쓰기, 기존 CLI 감싸기, 토큰 넘기기, resources와 prompts, opencode가 받아 주는 MCP 기능의 범위, 켜고 끄고 막기, 토큰 비용, 시간 제한, Windows 인코딩, 디버깅을 다룹니다.
모든 내용은 **opencode 1.19.5** 기준입니다.

관련 예제: [M1 stdio 최소 서버](../../examples/02-mcp/m1-stdio-minimal/) · [M2 공식 SDK](../../examples/02-mcp/m2-python-sdk/) · [M3 환경 변수](../../examples/02-mcp/m3-env-config/) · [M4 원격 HTTP](../../examples/02-mcp/m4-remote-http/) · [M5 팀 공용 서버](../../examples/02-mcp/m5-team-shared-server/) · [M6 티켓 DB](../../examples/02-mcp/m6-sqlite-tickets/) · [M7 resources와 prompts](../../examples/02-mcp/m7-resources-prompts/) · [M8 켜고 끄고 막기](../../examples/02-mcp/m8-enable-disable-deny/) · [M9 디버깅 갤러리](../../examples/02-mcp/m9-pitfalls/) · [M10 Node SDK와 npx](../../examples/02-mcp/m10-node-sdk-npx/) · [M11 남의 서버 쓰기](../../examples/02-mcp/m11-use-existing-server/) · [M12 패키지와 uvx](../../examples/02-mcp/m12-package-uvx/) · [M13 CLI 감싸기](../../examples/02-mcp/m13-wrap-cli/) · [M14 단일 실행 파일](../../examples/02-mcp/m14-single-binary/) · [M15 클라이언트 지원 범위](../../examples/02-mcp/m15-client-features/)

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
| 호출이 끝날 때마다 | `notifications/cancelled` 알림을 보냄 (답하면 안 됨) |
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

이 표는 M1처럼 프로토콜을 직접 처리하는 서버 기준입니다. 공식 SDK는 다릅니다. M10의 TypeScript SDK(와 M2의 Python SDK)에서는 **필수 인자 누락과 모르는 도구 이름도 JSON-RPC 오류가 아니라 `isError: true` 결과**로 나옵니다. 본문에 `MCP error -32602: Input validation error: ...`가 들어 있을 뿐이라, `error.code`로 구분하던 코드는 SDK 위에서는 쓸 수 없습니다.

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

서버를 Python으로 만들어야 하는 것은 아닙니다. 프로토콜은 JSON-RPC 줄이라 언어를 가리지 않습니다. 이 저장소에는 같은 용어집 서버가 Python(M1, M2, M12)뿐 아니라 Node(M10, 공식 TypeScript SDK)와 Rust(M14, 실행 파일 하나)로도 있습니다. 어떤 언어로 만들든 그 서버를 **어떻게 띄우는지**가 다음 절의 주제입니다.

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

## 서버를 실행하는 방법

서버 코드를 정했다면 `command`에 무엇을 적을지가 다음 질문입니다. 같은 용어집 서버(또는 공개 서버)를 띄우는 방법을 비교합니다. 시작 시간은 모두 **이 저장소를 만든 PC(Linux)의 한 번 측정**이고, `initialize` 응답까지 걸린 시간입니다. 이 PC는 레지스트리가 빨라서 느린 미러에서의 시간은 측정하지 못했습니다.

| 방법 | `command` 예 | 필요한 것 | 측정한 시작 시간 | 예제 |
|---|---|---|---|---|
| 직접 실행 (Python) | `["python", "server.py"]`, `["python", "-m", "team_glossary_mcp"]` + `environment` | Python. 표준 라이브러리만 쓰면 설치 없음 | `python -m`: 0.04~0.05초 | [M1](../../examples/02-mcp/m1-stdio-minimal/), [M12](../../examples/02-mcp/m12-package-uvx/) |
| 직접 실행 (Node) | `["node", "src/server.mjs"]` | Node, 폴더에서 `npm install` 한 번 (레지스트리나 미러) | 0.2~0.3초 | [M10](../../examples/02-mcp/m10-node-sdk-npx/) |
| `npx` | `["npx", "-y", "패키지@버전"]` | Node, 첫 실행에 레지스트리나 미러 | `.tgz` 첫 실행 4.2~4.7초, 이후 1.5~1.8초. 공개 파일 서버(M11) 첫 2.8초, 이후 1.1~1.7초 | M10, [M11](../../examples/02-mcp/m11-use-existing-server/) |
| `uvx` | `["uvx", "--from", ".", "team-glossary-mcp"]`, `["uvx", "mcp-server-time==2026.11.11"]` | uv, 첫 빌드나 내려받기에 패키지 인덱스(PyPI나 미러) | 로컬 폴더 빌드 첫 0.64~0.87초, 이후 0.06~0.07초. 공개 시간 서버(M11) 첫 2.5초, 이후 0.8초 | M12, M11 |
| 단일 실행 파일 | `["./bin/glossary-mcp"]` | 만드는 PC에 Rust와 첫 빌드용 crates 레지스트리나 미러. 받는 PC에는 Python도 Node도 필요 없음. OS마다 따로 빌드 | 1.3ms (같은 방법으로 Python M1은 27.9ms, 각각 15회 중앙값) | [M14](../../examples/02-mcp/m14-single-binary/) |
| 원격 | `"type": "remote"`, `url` | 상시 떠 있는 서버 한 곳, 토큰 | (위 "로컬과 원격") | [M4](../../examples/02-mcp/m4-remote-http/), [M5](../../examples/02-mcp/m5-team-shared-server/) |

고르는 기준은 대략 이렇습니다.

- **혼자 쓰거나 한 프로젝트에 붙어 있는 서버**는 직접 실행이 가장 단순합니다. 가장 빠르고 레지스트리가 필요 없습니다.
- **레포를 받지 않고 설정 한 줄로 쓰게 하려면** `npx`나 `uvx`입니다. 대신 레지스트리(또는 팀 미러)에 올리고 버전을 관리해야 하며, 첫 실행이 느립니다.
- **받는 쪽에 런타임을 깔 수 없거나 깔기 싫으면** 실행 파일 하나입니다. 대신 만드는 쪽에 툴체인이 필요하고 OS마다 따로 빌드합니다.
- **업데이트를 한 곳에서 하고 싶으면** 원격입니다.

모든 로컬 방식에 공통인 시작 제한(약 30초)은 느린 미러에서 `npx`나 `uvx`의 첫 실행이 길어질 때 문제가 됩니다. 시작을 일부러 35초 늦춘 서버(Linux 전용 시험)로 확인했습니다.

```text
●  ✗ slow-default failed
│      Operation timed out after 30000ms
●  ✓ slow-60s connected              <- 같은 명령에 "timeout": 60000 을 준 항목
```

그래서 첫 실행이 느릴 수 있는 항목에는 서버별 `timeout`(밀리초)을 늘려 둡니다(M10, M11, M12의 예제 설정은 60000).

### 남이 만든 서버 가져다 쓰기: 살펴보고, 고정하고, 제한하기 (M11)

실무에서는 이미 있는 서버를 가져다 쓰는 일이 더 많습니다. [M11](../../examples/02-mcp/m11-use-existing-server/)은 `opencode.json`에 두 줄로 공개 서버 둘(`npx`로 파일 서버, `uvx`로 시간 서버)을 붙이고, 순서를 지킵니다.

```json
"files": {
  "type": "local",
  "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem@2.3.0", "--confine-roots", "sandbox"],
  "timeout": 60000
},
"clock": { "type": "local", "command": ["uvx", "mcp-server-time==2026.11.11"], "timeout": 60000 }
```

**1. 켜기 전에 살펴봅니다.** `show_tools.py`가 서버를 띄워 도구 이름, 설명 길이, 스키마 길이, 읽기 전용 표시를 보여 주고, opencode가 모델에게 실제로 넘기는 도구도 보여 줍니다. 파일 서버는 도구가 16개이고 그중 6개(`write_file`, `append_file`, `edit_file`, `create_directory`, `move_file`, `copy_file`)가 쓰기 도구입니다. 읽기 전용 표시는 서버가 스스로 붙인 것이라 참고용이고, 이름과 설명을 눈으로도 읽어야 합니다.

**2. 버전을 고정합니다.** `@2.3.0`, `==2026.11.11`처럼 적지 않으면 실행할 때마다 최신 버전을 받을 수 있습니다. 그런데 **최상위 패키지만 고정해도 하위 의존성은 흘러갑니다.** `mcp-server-time==2025.9.25`는 2026-11-17에 하위 의존성 `mcp`가 2.x로 설치되어 `ImportError: cannot import name 'McpError'`로 죽었습니다. 그래서 예제는 의존성이 호환되는 `2026.11.11`을 씁니다. 엄격하게 하려면 `uvx --exclude-newer <날짜>`나 잠금 파일을 쓰는데, M11에서는 시험하지 않았습니다.

**3. 필요한 만큼만 남깁니다.** `permission`에 `<서버>_<도구>: "deny"`를 적으면 그 도구는 모델에게 가는 목록에서 빠집니다([M8](../../examples/02-mcp/m8-enable-disable-deny/)). 서버가 `--read-only` 옵션을 지원하면 서버 쪽에서 막을 수도 있습니다. `--read-only`를 붙이면 도구가 10개(읽기 전용)뿐이고 `write_file`을 직접 부르면 `Tool write_file not found`(-32602)가 나왔습니다. 이 옵션은 서버마다 다릅니다. 막은 것은 MCP 도구뿐이라 opencode **내장** `write`, `edit`, `bash`는 그대로 있습니다. 쓰기를 정말 막으려면 내장 도구도 deny하세요.

#### `--confine-roots`: 인자 한 줄이 허용 범위를 바꿉니다

opencode는 연결할 때 `roots` 기능을 선언하고, 서버가 물으면 **프로젝트 폴더**를 roots로 알려 줍니다. 이 파일 서버(2.3.0)는 `--confine-roots` 없이 roots를 받으면 **명령줄에 준 허용 폴더를 버리고 roots로 바꿉니다.** `--confine-roots`를 뺀 설정에서 `list_allowed_directories`가 `sandbox`가 아니라 프로젝트 폴더 전체를 돌려주는 것을 직접 확인했습니다. 남의 서버를 쓸 때는 "허용 범위가 내 생각과 같은가"를 `list_allowed_directories` 같은 도구로 직접 확인하세요. 그 밖에 확인한 것은 `sandbox`처럼 상대 경로로 준 인자는 서버의 작업 폴더 기준이라는 점입니다.

#### 컨텍스트 비용

도구 정의는 매 요청마다 전송됩니다. `show_tools.py`로 잰 값입니다(글자 수 ÷ 4가 토큰 어림값).

| | 도구 수 | 정의 JSON | ≈ 토큰 |
|---|---|---|---|
| 모델이 받음: 서버 둘 다, 제한 없음 | 19 | 17,034자 | 4,258 |
| 모델이 받음: 쓰기 도구 6개 deny | 13 | 11,334자 | 2,833 |
| 서버가 내놓음(`tools/list`): 파일 서버 | 16 | 14,147자 | 3,536 |
| 서버가 내놓음(`tools/list`): 시간 서버 | 3 | 2,184자 | 546 |

위 두 줄은 opencode가 보낸 `tools` 배열(래퍼 포함) 기준이고 아래 두 줄은 서버가 준 이름+설명+스키마만 센 값이라 서로 바로 비교하면 안 됩니다. 쓰기 도구 6개를 빼면 약 1,400 토큰이 줄었습니다.

가져다 쓰기 전에 "이게 정말 서버여야 하나"도 따집니다. 현재 프로젝트 파일만 읽는다면 opencode 내장 `read`, `grep`, `bash`로 되고, 파일 서버가 의미 있는 경우는 **프로젝트 밖의 특정 폴더를 범위를 정해 열어 줄 때**입니다. 서버는 내 PC에서 내 권한으로 실행되는 프로그램이므로 이름은 철자까지 복사해서 쓰고 게시자와 소스 저장소를 확인하세요.

### Node SDK 서버 (M10)

[M10](../../examples/02-mcp/m10-node-sdk-npx/)은 같은 용어집 서버를 공식 TypeScript SDK(`@modelcontextprotocol/sdk` 1.32.2)로 만듭니다. 파일은 `src/server.mjs` 하나(주석·빈 줄 제외 56줄)이고 컴파일이 없습니다. 도구의 이름, 설명, 입력 스키마(`zod`), 실행 함수만 쓰고 프로토콜 코드는 SDK가 맡습니다.

| | M1 (직접) | M2 (Python SDK) | M10 (Node SDK) |
|---|---|---|---|
| 잘못된 인자 | `-32602` 반환 | `isError` 결과 | `isError` 결과 |
| 모르는 도구 | `-32602` | `isError` 결과 | `isError` 결과 |
| 모르는 method | `-32601` | SDK | SDK (`-32601`) |
| 코드 줄 수(주석·빈 줄 제외) | 앞의 M1·M2 비교표 참고 | 24 | 56 |

- stdout은 프로토콜 전용이라 로그는 `console.error`(stderr)로만 씁니다.
- Node는 입출력을 UTF-8로 쓰므로 Windows 인코딩 문제가 없습니다(M1의 `reconfigure`에 해당하는 코드가 필요 없음).
- `npx`로 실행하는 배포 형태는 `npm pack`으로 만든 `.tgz`를 `["npx", "-y", "./team-glossary-mcp-1.0.0.tgz"]`로 실행합니다. 로컬 폴더를 `npx -y .`로 실행하면 `bin`만 연결하고 의존성을 설치하지 않으므로 `npm install` 전에는 `ERR_MODULE_NOT_FOUND`로 실패합니다. `.tgz`를 **절대 경로**로 주면 `Permission denied`(파일을 명령으로 실행하려 함)이니 `./`를 붙이거나 `--package=` 형태를 쓰세요.
- 레지스트리나 미러에 올린 뒤의 모양은 `["npx", "-y", "team-glossary-mcp@1.0.0"]`이지만 이 예제는 올리지 않아 **미실행**입니다.
- **잠금 파일.** 최상위 의존성은 정확한 버전(`1.32.2`, `4.6.7`)으로 고정했지만 그 아래(`hono`, `ajv` 등)는 `^` 범위라 시점에 따라 달라질 수 있습니다. 레포에 포함한 `package-lock.json`은 **레포를 받아 `npm ci`나 `npm install`을 할 때만** 하위 의존성을 고정합니다. `npm pack`에는 들어가지 않으므로 `npx`로 배포한 패키지의 하위 의존성은 여전히 흘러갑니다. 배포물까지 고정하는 장치는 `npm-shrinkwrap.json`인데, `package.json`에 `files` 목록이 있으면 거기에 적어야 패키지에 들어갑니다(npx가 그것을 따르는지는 확인하지 못했습니다). `zod`를 4.6.7로 고정한 이유는 3.25.76에서 `npm audit`가 high 경고를 냈기 때문입니다.
- `npx`의 비용: 첫 실행에 의존성 설치(레지스트리나 미러 필요), 시작 제한 30초에 걸릴 수 있어 `timeout`을 늘림, 코드를 고치면 버전을 올리고 다시 게시.

### 패키지로 배포하기 (M12)

[M12](../../examples/02-mcp/m12-package-uvx/)는 M1의 `server.py`를 설치 가능한 패키지로 바꿉니다. 바뀌는 것은 코드가 아니라 `command` 한 줄과 데이터 파일을 찾는 방법(`importlib.resources`)입니다.

```json
"glossary-pkg": {
  "type": "local",
  "command": ["python", "-m", "team_glossary_mcp"],
  "environment": { "PYTHONPATH": "src" }
},
"glossary-uvx": {
  "type": "local",
  "command": ["uvx", "--from", ".", "team-glossary-mcp"],
  "enabled": false,
  "timeout": 60000
}
```

- **`environment` + `PYTHONPATH`.** 설치 없이 `src`에서 패키지를 찾게 하는 형태입니다. opencode는 `environment`를 서버 프로세스에 실제로 전달하며(같은 명령에서 `environment`만 빼면 `failed`), 상대 경로 `src`는 서버 프로세스의 작업 폴더, 곧 opencode를 실행한 폴더 기준으로 풀립니다.
- **uvx의 첫 빌드에는 인덱스가 필요합니다.** 빈 uv 캐시에서 `--offline`으로 `uvx --from .`를 실행하면 빌드 백엔드(`hatchling`)를 받지 못해 실패합니다. 서버 자체는 의존성이 없어도 빌드 단계에서 인덱스가 필요합니다.
- **낡은 빌드 함정.** `uvx --from .`는 캐시된 빌드를 다시 씁니다. `server.py`를 고치고 다시 실행해도, `__version__`을 올려도 이전 내용이 나왔습니다(uv 0.12.5). 다시 빌드가 일어난 경우는 `uvx --no-cache --from . team-glossary-mcp`이거나 `pyproject.toml`의 수정 시각이 바뀐 때뿐이고, `--refresh-package`와 `--reinstall-package`는 효과가 없었습니다. 개발 중에는 `python -m` 경로를 쓰세요.
- **배포 방법.** wheel 파일을 공유 폴더에 두고 `uvx --from /공유/폴더/....whl team-glossary-mcp`(Linux 로컬 경로에서 빈 캐시 + `--offline`으로 실행 확인)는 인터넷도 인덱스도 필요 없습니다. 서버가 표준 라이브러리만 쓰기 때문에 가능하고, 의존성이 있는 서버는 그 의존성을 받을 인덱스가 필요합니다. 인덱스에 게시한 `uvx team-glossary-mcp==1.0.0`과 git 주소 방식은 **미실행**이고, 공유 폴더 경로의 Windows 형태(`\\서버\공유\...`, 드라이브 문자)도 확인하지 못했습니다.
- 선택 기준: 팀원이 clone 없이 쓰거나, 프로젝트가 여럿이거나, 버전을 고정해야 하면 패키지. 그렇지 않으면 M1처럼 파일 하나가 더 단순합니다.

### 기존 CLI를 읽기 전용 도구로 감싸기 (M13)

[M13](../../examples/02-mcp/m13-wrap-cli/)은 `git`을 `git_log`, `git_blame`, `git_diff_stat` 세 읽기 전용 도구로 내놓습니다. 기능은 `subprocess.run` 몇 줄이면 끝나고, 요점은 **모델이 보낸 문자열을 명령줄에 넣는 순간 생기는 문제**를 막는 일입니다. 다음 일곱 가지를 `check.py`가 각각 확인합니다.

| # | 막으려는 것 | 이 서버의 방법 |
|---|---|---|
| 1 | 입력이 셸 명령으로 해석됨 | 인자 리스트로 실행, 셸을 쓰지 않는다 |
| 2 | 옵션 주입 (`--output=파일`) | `-`로 시작하는 값 거부, 경로 앞에 `--` |
| 3 | 저장소 밖 파일 읽기 | `resolve()`로 실제 위치를 구해 저장소 안인지 확인(`..`, 심볼릭 링크 포함), 절대 경로 거부 |
| 4 | 끝없이 긴 출력 | 40줄에서 자르고 `…(N줄 생략)` 표시 |
| 5 | 멈춘 프로세스 | 10초 제한 |
| 6 | 실패를 성공처럼 전달 | 0이 아닌 종료 코드 → `isError: true` + stderr 문장 |
| 7 | 환경마다 달라지는 출력 | 색, 페이저, 형식을 고정하고 `-c core.quotepath=false`(한글 파일명이 8진수 이스케이프로 나오는 것을 막음), UTF-8로 읽기 |

두 번째가 놓치기 쉽습니다. **셸을 안 써도 옵션 주입은 일어납니다.** 읽기 전용 명령인 `git diff --stat`에 `--output=pwned.txt`를 넘기면 실제로 파일이 써집니다(`check.py`가 대조 실험). 줄 수를 자를 때는 조용히 자르지 않고 잘렸다는 사실과 다음 행동을 알려 줍니다.

이 서버는 읽기 전용 "동작"만 노출한 것이지 읽기 전용 "권한"이 아닙니다. 같은 사용자 권한으로 돌기 때문에 검증이 뚫리면 그 사용자가 할 수 있는 일은 다 할 수 있습니다.

**스킬이 더 싼 경우도 많습니다.** "이 CLI를 이렇게 실행하라"고 `SKILL.md`에 적고 모델이 `bash`로 직접 실행하게 하면 서버 코드를 짤 필요가 없고 항상 컨텍스트에 있는 것도 이름과 설명 한 줄뿐입니다. 약점은 모델이 명령줄을 마음대로 조립한다는 것입니다. `bash`를 열면 `--output=` 같은 인자를 인자 단위로 검증할 방법이 없습니다. MCP 래퍼가 값을 하는 때는 정해져 있습니다. **(1) 입력 검증이 필요할 때, (2) 열어 주는 범위를 좁히고 싶을 때, (3) 여러 에이전트나 사람이 같은 도구를 공유할 때.** 셋 다 해당하지 않으면 스킬이 더 쌉니다. 스크립트 없이 CLI만 쓰는 스킬은 [S1d](../../examples/01-skills/s1d-cli-only/)입니다.

### 런타임 없이 실행 파일 하나로 (M14)

[M14](../../examples/02-mcp/m14-single-binary/)는 M1과 같은 일을 하는 서버를 Rust(`serde_json`만 사용)로 다시 만듭니다. 용어집도 빌드할 때 실행 파일 안에 들어가므로 배포할 파일이 하나입니다. 용어를 고치면 **다시 빌드해야** 반영됩니다.

- **크기와 시작 시간.** 355 KiB. 프로세스를 띄워 `initialize` 응답을 받을 때까지 Rust 중앙값 1.3ms, Python M1 중앙값 27.9ms(각 15회, 이 PC의 한 번 측정)입니다. 30초 제한에 걸리는 일이 없는 한 체감 차이는 크지 않습니다.
- **값을 치르는 것.** 만드는 PC에 툴체인이 필요하고, OS마다 따로 빌드합니다(Linux 용 파일은 Windows에서 안 돕니다). 도구가 몇 개 안 되고 자주 안 바뀌고 널리 배포할 때 어울립니다. Go도 같은 목적에 쓸 수 있지만 만들어 보지 않았습니다(미검증).
- **`command`의 상대 경로는 opencode를 실행한 폴더 기준**입니다(설정 파일 위치 기준이 아님). `["./bin/glossary-mcp"]`는 프로젝트 폴더에서는 connected이고 하위 폴더에서는 failed였으며, 절대 경로는 어디서나 connected였습니다(Linux).
- **glibc.** 기본 `cargo build --release`(Linux, `x86_64-unknown-linux-gnu`)의 결과는 동적 링크이고 필요한 glibc 심볼 버전은 최대 `GLIBC_2.34`였습니다(빌드한 PC의 glibc는 2.43). 즉 이 파일은 glibc 2.34보다 오래된 배포판에서는 실행되지 않을 가능성이 높습니다(오래된 배포판에서 실제로 돌려 보지는 않았고, 필요 버전은 `objdump -T`로 읽은 값). "런타임이 필요 없다"는 말은 Python이나 Node가 필요 없다는 뜻이지 시스템 C 라이브러리까지 없어도 된다는 뜻이 아닙니다. 대안으로 `x86_64-unknown-linux-musl`로 빌드하면 정적 링크된 459,512바이트 파일이 나왔습니다(이 PC에서 빌드와 `ldd`까지만 확인).
- **Windows.** Linux에서 `cargo xwin build --target x86_64-pc-windows-msvc`로 만든 `.exe`(204 KiB)를 `bin\glossary-mcp.exe`로 두고 Windows의 opencode 1.19.5에서 `opencode mcp list`를 실행하면, 설정은 Linux와 같은 `["./bin/glossary-mcp"]` 그대로인데 `connected`였습니다. opencode가 Windows에서 `.exe`를 붙이지 않은 이름으로도 실행 파일을 찾으므로 `opencode.json` 하나로 두 OS를 쓸 수 있습니다. 확인하지 못한 것은 Windows에서 `cargo build`로 직접 빌드하는 과정입니다(시험한 Windows에 cargo가 없었음).

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

## 클라이언트가 지원하는 범위

MCP 스펙에는 도구 호출 말고도 진행 알림, 구조화된 결과, 도구 목록 변경 알림, 서버가 클라이언트에게 거꾸로 요청하는 기능(sampling, elicitation)이 있습니다. 서버가 **보낸다고 해서** 에이전트가 **쓰는 것은 아닙니다.** [M15](../../examples/02-mcp/m15-client-features/)는 이 기능들을 일부러 전부 보내 보는 서버와, 진짜 opencode 1.19.5를 가짜 모델로 붙여 무슨 일이 일어났는지 기록하는 `probe.py`로 이루어져 있습니다. 아래 표는 opencode 1.19.5 한 버전, 가짜 모델 기준이고 다른 클라이언트는 다르게 동작할 수 있습니다(미검증).

| 기능 | opencode 1.19.5가 한 일 | 그래서 서버를 이렇게 만든다 |
|---|---|---|
| 클라이언트 capabilities | `{"roots": {}}`만 선언 (sampling, elicitation 없음). protocolVersion `2025-11-25` | 선언 없는 기능은 쓰지 않는다 |
| `_meta.progressToken` | **모든** `tools/call`에 붙인다 | 토큰이 있을 때만 progress를 보낸다 |
| `notifications/progress` | 오류 없이 받지만 화면, `--print-logs DEBUG`, `--format json` 어디에도 **안 나온다.** 대신 **도구 호출 제한 시간을 늘려 준다** (`timeout: 3000`에서 5초짜리 도구: 알림 있으면 완료, 없으면 `MCP error -32001: Request timed out`) | 사용자에게 보여 줄 목적으로는 쓸 수 없다. 오래 걸리는 도구의 "살아 있다" 신호로는 쓸 수 있다 |
| `notifications/message` | `--print-logs --log-level DEBUG` 로그에만 나온다 | 사용자에게 보일 정보가 아니라 디버깅용 |
| 서버 stderr | `--print-logs DEBUG`에도 안 나온다 | 서버 쪽 진단은 파일로 남긴다 |
| `structuredContent` + text | 모델은 **text 블록만** 받는다 | 중요한 결과는 text에 넣는다 |
| `structuredContent`만 | 모델은 compact JSON **문자열**을 받는다 | text 설명을 같이 주는 편이 안전하다 |
| `outputSchema` | 모델에게 가는 도구 정의에 **들어가지 않는다** (`name`, `description`, `parameters`만) | 출력 모양은 `description`에 글로 쓴다 |
| `notifications/tools/list_changed` | `tools/list`를 다시 요청하고, 다음 모델 요청부터 새 도구가 보인다 | 동적 도구 목록을 써도 된다 |
| `roots/list` (서버→클라이언트) | 프로젝트 폴더의 `file://` URI 하나를 답한다 | 경로가 서버로 간다는 점에 유의 |
| `sampling/createMessage`, `elicitation/create` | 즉시 `-32601 Method not found`로 거절 | 이 기능에 기대는 서버는 opencode에서 동작하지 않는다. 사용자에게 물어야 하면 도구 결과로 질문을 돌려주고 모델이 대신 묻게 한다 |
| `notifications/cancelled` | 호출이 끝날 때마다 온다 (8번 호출에 8번) | 알림이므로 답하지 않는다. 오류로 취급하지 않는다 |

알아 둘 점입니다. 알림이 있을 때 제한 시간을 **얼마나 오래** 늘려 주는지(총 상한이 있는지)는 확인하지 못했습니다. `notifications/message`는 `DEBUG` 수준에서만 확인했습니다. 이미지나 리소스 링크 같은 다른 결과 형식은 다루지 않았습니다.

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

서버 항목의 `"timeout"`(밀리초)이 이 제한을 바꿉니다. 서버가 `notifications/progress`를 보내면 도구 호출 제한이 늘어납니다([M15](../../examples/02-mcp/m15-client-features/), 위 "클라이언트가 지원하는 범위"의 표). 시작과 `tools/list`뿐 아니라 도구 호출에도 적용되는 것으로 관찰됐습니다(`timeout: 3000`일 때 8초 걸리는 도구 호출이 실패). 최상위 `experimental.mcp_timeout`(밀리초)은 **도구 호출 제한만** 바꿉니다(시작 제한이 아닙니다).

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
