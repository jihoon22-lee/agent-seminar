# M1 가장 작은 MCP 서버 (stdio)

> 구성: Python 파일 1개 + JSON 용어집 | 난이도: ★☆☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: MCP — 로컬 서버 (stdio)

## 무엇을 보여 주나

MCP 서버는 마법 상자가 아니다. **표준 입력으로 JSON 한 줄을 받고, 표준 출력으로 JSON 한 줄을 돌려주는 프로그램**이다.
이 예제는 표준 라이브러리만으로 약 120줄(주석 제외)짜리 서버를 직접 만들고, 에이전트가 하는 일을 손으로 흉내 내는
`raw_session.py`로 주고받는 JSON을 전부 눈으로 확인한다. 그다음 opencode가 같은 서버에 붙어 도구를 호출하는 모습을 본다.

## 실무에서는

- **팀 전용 지식**(용어집, 코딩 규칙, 배포 체크리스트)을 에이전트가 직접 찾아보게 하고 싶을 때, 가장 작은 형태의 MCP 서버가 이 모양이다.
- 기존 CLI/스크립트를 에이전트용 도구로 감쌀 때의 출발점이다. `tools/call`에서 스크립트를 부르기만 하면 된다.
- 서버가 이상하게 동작할 때, 에이전트를 거치지 않고 JSON 줄을 직접 넣어 보는 디버깅 방법을 익혀 두면 어떤 MCP 서버든 문제 지점을 빨리 찾는다.

## 파일 구성

```
m1-stdio-minimal/
  README.md        이 문서
  server.py        MCP 서버 본체 (주석이 많은 약 210줄, 코드는 약 120줄)
  glossary.json    팀 용어집 데이터 (용어 14개)
  raw_session.py   서버를 띄워 JSON-RPC 대화를 줄 단위로 출력하는 스크립트
  opencode.json    mcp.glossary 항목: ["python", "server.py"] 로 서버 실행
  check.py         자동 검증 (tools/run_checks.py가 실행)
  fake_llm.py      가짜 LLM 서버. check.py 가 모델 없이 opencode 의 요청을 기록·재현하는 데 씀
```

## 따라 하기

모든 명령은 이 예제 폴더(`examples/02-mcp/m1-stdio-minimal`)에서 실행한다.
> Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`opencode.json`의 `command`도 `["python3", "server.py"]`로)

**1. 에이전트 없이 대화 엿보기**

```powershell
cd examples\02-mcp\m1-stdio-minimal
python raw_session.py
```

```bash
cd examples/02-mcp/m1-stdio-minimal
python3 raw_session.py
```

`>>`는 보낸 줄, `<<`는 받은 줄, `[서버 stderr]`는 서버가 stderr로 남긴 로그다.

**2. opencode가 서버에 연결되는지 확인**

```powershell
opencode mcp list
```

```bash
opencode mcp list
```

**3. opencode에서 질문하기** — 평소 쓰는 모델로 실행하면 됩니다.

```powershell
opencode
```

```bash
opencode
```

프롬프트에 입력:

```
팀 용어집에서 ADR이 무슨 뜻인지 찾아줘
```

모델 설정이 없다면 무료 모델로 한 번에 실행할 수도 있다.

```powershell
opencode run -m opencode/big-pickle --auto "팀 용어집에서 ADR이 무슨 뜻인지 찾아줘"
```

```bash
opencode run -m opencode/big-pickle --auto "팀 용어집에서 ADR이 무슨 뜻인지 찾아줘"
```

**4. (선택) 서버를 손으로 직접 쓰기** — 서버를 켜 놓고 터미널에 JSON 한 줄을 붙여 넣어 보자.

```powershell
python server.py
```

```bash
python3 server.py
```

```
{"jsonrpc":"2.0","id":1,"method":"ping"}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"lookup_term","arguments":{"term":"SLO"}}}
```

종료는 `Ctrl+C` (입력을 닫는 `Ctrl+Z`+Enter(Windows) / `Ctrl+D`(Linux)도 된다).

## 기대 결과

`python raw_session.py` (Linux, Python 3.14에서 실행. 줄은 길어서 일부만 발췌):

```
== 1. 첫 인사: 프로토콜 버전과 기능을 맞춘다
  >> {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", ...}}
  << {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "glossary-m1", "version": "1.0.0"}}}

== 2. 알림: 인사 끝. id가 없으므로 서버는 답장하지 않는다
  >> {"jsonrpc": "2.0", "method": "notifications/initialized"}
  (답장 없음)

== 4. 도구 호출 (성공)
  >> {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "lookup_term", "arguments": {"term": "ADR"}}}
  << {"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "ADR: 중요한 설계 결정을 배경, 선택지, 결과와 함께 ... 쓴다.\n(별칭: Architecture Decision Record, 아키텍처 결정 기록)"}], "isError": false}}

== 5. 도구 호출 (용어집에 없는 용어) -> 오류가 아니라 isError:true 결과
  << {"jsonrpc": "2.0", "id": 4, "result": {"content": [{"type": "text", "text": "'카나리아 배포'은(는) 용어집에 없습니다. 비슷한 용어: 카나리 배포, 블루/그린 배포. list_terms로 전체 목록을 볼 수 있습니다."}], "isError": true}}

== 6. 도구 호출 (없는 도구 이름) -> JSON-RPC 오류 -32602
  << {"jsonrpc": "2.0", "id": 5, "error": {"code": -32602, "message": "알 수 없는 도구: delete_everything"}}

== 7. 모르는 method -> JSON-RPC 오류 -32601
  << {"jsonrpc": "2.0", "id": 6, "error": {"code": -32601, "message": "모르는 method: resources/list"}}

== 8. ping
  << {"jsonrpc": "2.0", "id": 7, "result": {}}
```

`opencode mcp list`:

```
●  ✓ glossary connected
│      python server.py
```

opencode에서 질문했을 때 (모델 `opencode/big-pickle`로 같은 server.py 코드를 임시 폴더에 복사해 실행한 결과를 발췌. 예제 폴더 자체에서의 모델 실행은 무료 모델 한도 때문에 확인하지 못했다):

```
⚙ glossary_lookup_term {"term":"ADR"}
ADR(Architecture Decision Record, 아키텍처 결정 기록): 중요한 설계 결정을 배경, 선택지, 결과와 함께 짧은 문서 한 장으로 남기는 방식. 나중에 '왜 이렇게 했지?'에 답하기 위해 쓴다.
```

`⚙ glossary_lookup_term` 한 줄이 "모델이 MCP 도구를 불렀다"는 표시다. 도구 이름이 `glossary` + `_` + `lookup_term`인 점에 주목하자.

## 동작 원리

opencode가 시작되면 `opencode.json`의 `mcp.glossary`를 읽고 아래 순서로 움직인다. (`raw_session.py`의 1~8번과 같은 대화다.)

1. **프로세스 실행** — `command` 배열 `["python", "server.py"]`를 **opencode를 실행한 폴더 기준으로** 자식 프로세스로 띄운다. stdin/stdout은 파이프로 연결된다.
2. **`initialize`** — opencode 1.19.5는 `protocolVersion: "2025-11-25"`, `capabilities: {"roots": {}}`, `clientInfo: {"name": "opencode", "version": "1.19.5"}`를 보낸다. 서버는 자기가 아는 버전이면 **그대로 되돌려 주고**(echo), 모르는 버전이면 서버의 최신 버전을 제안한다. 이 서버가 아는 버전은 `2025-11-25`, `2025-06-18`, `2025-03-26`, `2024-11-05`다.
3. **`notifications/initialized`** — 인사 끝이라는 알림. `id`가 없는 메시지(알림)에는 **절대 답장하지 않는다.** 답장하면 클라이언트가 혼란스러워한다.
4. **`tools/list`** — 서버가 가진 도구의 `name`, `description`, `inputSchema`를 받는다. opencode는 이것을 모델에게 보이는 도구 목록에 `서버이름_도구이름`(`glossary_lookup_term`) 형태로 넣는다. **모델은 설명과 스키마만 보고 도구를 고른다** — `description`을 대충 쓰면 모델이 도구를 못 쓴다.
5. **`tools/call`** — 모델이 도구를 고르면 `{"name": "lookup_term", "arguments": {"term": "ADR"}}`가 전달된다. opencode는 `params._meta.progressToken`도 함께 붙인다.
6. **결과 반환** — `result.content`는 블록 배열이고 대부분 `{"type": "text", "text": ...}`다. 이 텍스트가 그대로 모델의 다음 입력이 된다.
7. **종료** — 호출이 끝나면 opencode가 `notifications/cancelled`(reason: AbortError)를 보내기도 한다. 모르는 알림은 조용히 무시해야 서버가 안전하다. opencode가 끝나면 stdin이 닫히고, `for line in sys.stdin` 반복이 끝나 프로세스가 종료된다.

### 오류는 두 종류다

| 상황 | 표현 | 의미 |
|------|------|------|
| 모르는 method | `error.code = -32601` | 프로토콜 오류: 이 서버는 그 기능이 없다 |
| 모르는 도구 이름, 필수 인자 누락 | `error.code = -32602` | 프로토콜 오류: 요청 자체가 잘못됐다 |
| 깨진 JSON 줄 | `error.code = -32700` | 프로토콜 오류: 줄을 읽을 수 없다 |
| 용어가 없다 | `result.isError = true` | **도구 오류**: 도구는 정상이지만 "결과가 실패"다 |

도구 오류(`isError: true`)는 모델이 메시지를 읽고 **스스로 다시 시도**할 수 있게 하려는 것이다. 그래서 `server.py`는 "비슷한 용어: 카나리 배포"처럼 다음 행동의 단서를 메시지에 넣는다.

### 제한 시간 (opencode 1.19.5에서 측정)

| 상황 | 기본값 | 결과 |
|------|--------|------|
| 서버 시작·`initialize`·`tools/list` | 30초 | `✗ failed — Operation timed out after 30000ms` 또는 `Failed to get tools` |
| 도구 호출(`tools/call`) | 60초 | 40초 걸린 호출은 성공, 75초 걸린 호출은 약 60초에 `MCP error -32001: Request timed out`이 모델에게 돌아간다 |

서버 항목에 `"timeout": 3000`(밀리초)을 쓰면 위 제한 시간이 바뀐다. 3초로 줄였더니 8초 걸리는 도구 호출이 `Request timed out`으로 실패했고, `tools/list`가 느리면 서버가 `failed`가 됐다. 최상위 `experimental.mcp_timeout`(밀리초)은 도구 호출 제한을 바꾼다. 오래 걸리는 도구는 서버 항목의 `timeout`을 늘려 주자.

### stdout은 프로토콜 전용

stdout은 JSON-RPC 메시지가 흐르는 통로다. opencode 1.19.5에서 직접 시험해 보니, 줄바꿈으로 끝나는 `print("디버그")` 한 줄이 섞인 것은 **무시되고** 서버는 `✓ connected` 그대로였고 도구 호출도 됐다. 하지만 **줄바꿈 없는 출력**(예: `sys.stdout.write("디버그 ")`)이 JSON 앞에 붙으면 그 줄이 깨진 JSON이 되어 스트림이 어긋난다. 이때 서버는 약 30초 뒤 `✗ failed — Operation timed out after 30000ms`가 된다. 안 깨지는 경우가 있다고 stdout에 출력해도 되는 것은 아니다. 클라이언트마다 처리가 다를 수 있으므로 `server.py`는 로그를 모두 `log()` 함수(stderr)로 보낸다.

### Windows 인코딩

Windows의 파이썬은 stdin/stdout을 cp949로 열기 때문에 한글이 든 JSON이 깨진다. `server.py` 첫머리의 `sys.stdout.reconfigure(encoding="utf-8", newline="\n")`이 이를 막는다. `newline="\n"`은 줄 끝이 `\r\n`으로 바뀌는 것도 막는다.

## 직접 바꿔 보기

1. **용어 추가** — `glossary.json`에 용어를 하나 추가하고, opencode를 다시 시작해서 물어본다. (서버는 시작할 때 파일을 읽으므로 opencode를 껐다 켜야 한다.)
2. **도구 추가** — `server.py`의 `TOOLS`에 `random_term`(무작위 용어 하나) 도구를 정의하고 `call_tool`에 처리를 추가한다. `python raw_session.py`로 `tools/list`에 나타나는지 먼저 확인한다.
3. **description 망가뜨려 보기** — `lookup_term`의 `description`을 `"도구"` 한 단어로 바꾸고 같은 질문을 해 본다. 모델이 도구를 고르는 확률이 어떻게 달라지는지 관찰한다.
4. **실수 체험** — `handle()` 맨 앞에 `sys.stdout.write("디버그 ")`를 넣고(줄바꿈 없는 출력) `opencode mcp list`를 실행한다. 약 30초 뒤 `✗ glossary failed — Operation timed out after 30000ms`가 나온다. 같은 자리에 `print("디버그")`를 넣으면(줄바꿈 있음) 이번 시험에서는 오류 없이 `connected`였다. 확인 후 지우자.

## 주의할 점 / 문제 해결

- **opencode를 이 예제 폴더에서 실행해야 한다.** `command`의 `server.py`는 설정 파일 위치가 아니라 **opencode를 실행한 폴더** 기준이다. 하위 폴더에서 실행하면 설정은 찾아지지만 서버 파일을 못 찾아 실패한다. Linux에서 확인한 증상은 약 2초 뒤 `✗ glossary failed — MCP error -32000: Connection closed`다(`python nope.py`처럼 없는 스크립트를 가리킬 때도 같다). Windows에서는 메시지나 걸리는 시간이 다를 수 있다(미확인). 어느 쪽이든 `command`의 경로와 실행한 폴더부터 확인한다.
- **Linux에서 `python` 명령이 없으면** `command`를 `["python3", "server.py"]`로 바꾼다.
- **한글이 `???`나 깨진 글자로 나온다** — Windows에서 `reconfigure`를 빼먹었을 때의 증상이다.
- **서버를 고쳤는데 반영이 안 된다** — opencode는 시작할 때 서버를 띄운다. 코드를 고쳤다면 opencode를 다시 시작한다.
- **`opencode mcp list`가 `failed`** — 먼저 `python server.py`를 직접 실행해 오류가 없는지 본다. stderr 로그와 `raw_session.py`가 가장 빠른 진단 도구다.
- 같은 폴더에 `.opencode/` 폴더가 생기면 opencode가 시작할 때 `@opencode-ai/plugin`을 npm에서 설치하려 한다. 이 예제는 `.opencode/`가 없어 해당 없다.
