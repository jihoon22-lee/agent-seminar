# M2 공식 Python SDK로 만든 같은 서버

> 구성: `server.py`(약 60줄) + `prepare.py` + OS별 설정 템플릿 | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, pip(패키지 미러 가능) | 슬라이드: MCP — 로컬 서버 (SDK)

## 무엇을 보여 주나

M1에서 직접 쓴 JSON-RPC 처리, 도구 목록, 입력 스키마, 오류 코드를 공식 `mcp` SDK는 **함수 + 타입 힌트 + docstring**만으로 만들어 준다.
같은 용어집을 M1은 코드 124줄, 이 예제는 24줄(주석·빈 줄·docstring 제외)로 구현한다. 대신 패키지 설치가 필요하고 가상환경 경로가 OS마다 다르다는 대가를 치른다.
어느 쪽이 정답인지가 아니라, **언제 무엇을 고를지**를 판단하는 예제다.

## 실무에서는

- 도구가 몇 개를 넘고 인자가 복잡해지면 손으로 쓴 스키마와 검증 코드가 금방 오류의 원인이 된다. 실무 MCP 서버의 대부분은 SDK(Python `mcp`, TypeScript `@modelcontextprotocol/sdk`)로 만든다.
- 같은 함수 코드를 `mcp.run("streamable-http")` 한 줄로 원격 HTTP 서버로 바꿀 수 있다. (M4에서 직접 만든 방식을 SDK가 대신해 준다.)
- 반대로 의존성을 설치할 수 없는 환경이거나 도구가 한두 개뿐이라면 M1처럼 표준 라이브러리만 쓰는 편이 낫다.

## 파일 구성

```
m2-python-sdk/
  README.md                  이 문서
  server.py                  SDK(MCPServer)로 만든 용어집 서버
  glossary.json              M1과 같은 용어집
  requirements.txt           mcp==2.3.0 (버전 고정)
  prepare.py                 .venv 만들기 -> SDK 설치 -> 이 OS용 opencode.json 생성
  opencode.windows.json      Windows용 템플릿 (.venv/Scripts/python.exe)
  opencode.linux.json        Linux용 템플릿   (.venv/bin/python)
  opencode.json              (prepare.py가 생성, .gitignore 대상)
  .venv/                     (prepare.py가 생성, .gitignore 대상)
  check.py                   자동 검증 (임시 폴더에 별도 venv를 만들어 검사)
  fake_llm.py                가짜 LLM 서버. check.py 가 모델 없이 opencode 의 요청을 기록·재현하는 데 씀
```

## 따라 하기

> Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요.

**1. 준비 (가상환경 + SDK 설치 + opencode.json 생성)**

```powershell
cd examples\02-mcp\m2-python-sdk
python prepare.py
```

```bash
cd examples/02-mcp/m2-python-sdk
python3 prepare.py
```

인터넷이 막혀 있고 **패키지 미러**를 쓰는 환경이라면 미러 주소를 알려 준다. 세 가지 방법 중 하나면 된다.

```powershell
python prepare.py --index-url https://<미러 주소>/simple      # 1) 이 스크립트에만 적용
$env:PIP_INDEX_URL = "https://<미러 주소>/simple"; python prepare.py   # 2) 이 터미널에서만
pip config set global.index-url https://<미러 주소>/simple      # 3) 계속 적용
```

```bash
python3 prepare.py --index-url https://<미러 주소>/simple
PIP_INDEX_URL=https://<미러 주소>/simple python3 prepare.py
pip config set global.index-url https://<미러 주소>/simple
```

> 미러 주소는 환경마다 다르니 `<미러 주소>`를 그대로 두지 말고 팀에서 안내받은 값으로 바꾼다. 실패하면 `prepare.py`가 위 방법을 다시 안내한다.

**2. 연결 확인**

```powershell
opencode mcp list
```

```bash
opencode mcp list
```

**3. 질문하기** — 평소 쓰는 모델로 `opencode`를 실행하고 입력한다.

```
팀 용어집에서 SLO가 무슨 뜻인지 찾아줘
```

모델 설정이 없다면:

```powershell
opencode run -m opencode/big-pickle --auto "팀 용어집에서 SLO가 무슨 뜻인지 찾아줘"
```

```bash
opencode run -m opencode/big-pickle --auto "팀 용어집에서 SLO가 무슨 뜻인지 찾아줘"
```

## 기대 결과

`opencode mcp list`:

```
●  ✓ glossary-sdk connected
│      .venv/bin/python server.py
```

(Windows에서는 `.venv/Scripts/python.exe server.py`)

SDK가 만든 `tools/list` 응답 (발췌 — 우리가 쓴 건 함수와 `Field(description=...)`뿐이다):

```json
{"name": "lookup_term",
 "description": "팀 용어집에서 용어 하나의 뜻을 찾는다.\n\nADR, SLO, 롤백, ...",
 "inputSchema": {"properties": {"term": {"description": "찾을 용어. 예: 'ADR', '카나리 배포'", "title": "Term", "type": "string"}},
                 "required": ["term"], "type": "object", "title": "lookup_termArguments"},
 "outputSchema": {"properties": {"result": {"title": "Result", "type": "string"}}, "required": ["result"], "type": "object"}}
```

opencode에서 질문하면 모델이 도구를 부를 때 화면에 `⚙ glossary-sdk_lookup_term {"term":"SLO"}` 형태의 줄이 나온다. 도구 이름이 `서버이름_함수이름` 규칙(`glossary-sdk_lookup_term`)을 따른다는 점은 M1·M3와 같다.

## M1과 비교

| 항목 | M1 (직접 구현) | M2 (공식 SDK) |
|------|---------------|--------------|
| 코드 줄 수 (주석·빈 줄·docstring 제외) | 124줄 | 24줄 |
| 의존성 | 없음 (표준 라이브러리) | 28개 패키지, 가상환경 약 58 MB |
| 서버 시작(첫 `initialize` 응답까지) | 약 0.02초 | 약 0.7~1초 (import 시간) |
| 도구 스키마 | JSON을 손으로 작성 | 타입 힌트에서 자동 생성, `outputSchema`·`structuredContent`도 자동 |
| 알 수 없는 도구 이름 | JSON-RPC 오류 `-32602` | `isError: true` 결과 `Unknown tool: ...` |
| 필수 인자 누락 | JSON-RPC 오류 `-32602` | `isError: true` 결과 (pydantic 검증 메시지가 길게 붙는다) |
| 선언하는 capabilities | `tools` | `tools`, `prompts`, `resources` (사용하지 않아도 선언) |
| 원격(HTTP) 전환 | 직접 구현 (M4) | `mcp.run("streamable-http")` |
| 프로토콜 버전 변화 | 직접 따라가야 함 | SDK를 올리면 됨 |
| OS 차이 | `["python", "server.py"]` 한 줄 | venv 파이썬 경로가 OS마다 달라 설정 템플릿 2개 + 생성 스크립트 |
| 디버깅 | 코드가 곧 프로토콜이라 보이는 대로 | 프레임워크 안쪽은 불투명 (M1에서 본 줄 단위 대화를 알면 읽힌다) |

**판단 기준**: 도구가 많거나 인자 검증이 복잡하면 SDK, 설치가 불가능하거나 아주 작은 도구면 직접 구현. M1을 한 번 해 봤다면 SDK가 뒤에서 무슨 일을 하는지 알고 쓰는 것이므로 어느 쪽이든 문제 해결이 훨씬 쉽다.

## 동작 원리

1. `prepare.py`가 `python -m venv .venv`로 가상환경을 만들고 `requirements.txt`(`mcp==2.3.0`)를 설치한다.
2. 가상환경 안의 파이썬 경로는 **Windows `.venv\Scripts\python.exe`, Linux `.venv/bin/python`**으로 다르다. `opencode.json`은 상대 경로를 `command`에 쓰므로 OS별 템플릿 중 현재 OS 쪽을 `opencode.json`으로 복사한다. 그래서 `opencode.json`은 커밋하지 않는다.
3. opencode는 `[".venv/bin/python", "server.py"]`를 실행한다. 시스템 파이썬이 아니라 SDK가 설치된 **가상환경의 파이썬**을 직접 지정하는 것이 핵심이다. 이렇게 하면 `activate` 같은 셸 상태에 의존하지 않는다.
4. `server.py`의 `@mcp.tool()` 데코레이터가 함수 이름을 도구 이름으로, docstring을 `description`으로, 타입 힌트를 `inputSchema`로 바꾼다. `Annotated[str, Field(description=...)]`는 인자 설명을 붙이는 방법이다.
5. `raise ToolError(...)`는 SDK가 `isError: true` 결과로 바꿔 모델에게 돌려준다. 그 외 예외도 같은 방식으로 `Error executing tool ...: <메시지>`가 된다.
6. `mcp.run()`의 기본 전송 방식이 stdio라서 M1과 똑같이 stdin/stdout으로 JSON 줄을 주고받는다. (`opencode`가 보내는 `protocolVersion`은 `2025-11-25`이고 SDK도 같은 값으로 협상한다.)

### mcp 2.x 이름 변경 주의

`mcp` 패키지 2.0부터 1.x의 `FastMCP`가 `MCPServer`로 바뀌었고 import 경로도 `mcp.server.mcpserver`다. 인터넷 예제 대부분은 `from mcp.server.fastmcp import FastMCP`(1.x)를 쓰는데, 2.x에서 실행하면 이름이 바뀌었다는 안내와 함께 `ModuleNotFoundError`가 난다. 그 예제를 그대로 쓰려면 `requirements.txt`를 `mcp<2`로 바꾸고, 새 코드는 이 예제의 `MCPServer`를 따른다.

## 직접 바꿔 보기

1. **도구 추가** — `server.py`에 `@mcp.tool() def count_terms() -> int:`를 추가하고 `opencode mcp list` 후 질문해 본다. 스키마를 한 줄도 쓰지 않았는데 도구가 생긴다.
2. **전송 방식 바꾸기** — 마지막 줄을 `mcp.run("streamable-http", port=3918)`로 바꾸고 `.venv`의 파이썬으로 `server.py`를 실행한다. 기본 주소는 `http://127.0.0.1:포트/mcp`이고 포트 기본값은 8000이라 이미 쓰는 프로그램이 있으면 충돌하므로 `port=`로 지정한다. 이때는 `opencode.json`이 `type: "remote"`(+ `url`)여야 한다. (M4의 내용) 이 SDK 서버는 M4의 최소 서버와 달리 기본으로 응답을 `text/event-stream`(SSE) 형식으로 보내고 `Mcp-Session-Id` 헤더로 세션을 발급한다. (직접 `curl`로 `initialize`를 보내 확인했다.)
3. **버전 고정 확인** — `requirements.txt`의 `mcp==2.3.0`을 지우고 다시 `prepare.py`를 실행하면 어떤 일이 생길 수 있는지 생각해 보자. (고정 안 하면 새 메이저 버전에서 이름이 바뀔 수 있다.)

## 주의할 점 / 문제 해결

- **pip 설치 실패** — 인터넷이 막힌 환경이라면 패키지 미러 주소가 필요하다 (위 "준비" 참고). `check.py`는 pip 설치가 불가능하면 `WARN`만 남기고 이 예제의 SDK 검사를 건너뛴다.
- **`opencode.json`이 없다 / 틀린 OS용이다** — 다른 OS에서 복사해 왔다면 `python prepare.py`를 다시 실행한다. `.venv`도 OS별로 따로 만들어야 한다. Linux에서 만든 `.venv`를 Windows로 복사하면 동작하지 않는다.
- **`✗ glossary-sdk failed`** — `.venv/Scripts/python.exe server.py`(Windows) 또는 `.venv/bin/python server.py`(Linux)를 직접 실행해 보고, opencode를 **예제 폴더에서** 실행했는지 확인한다. (`command`의 상대 경로는 opencode를 실행한 폴더 기준이다.)
- **Windows 한글** — SDK는 stdio를 UTF-8로 직접 다루므로 한글 결과가 깨지지 않는다. `server.py`의 `reconfigure`는 디버깅 `print`를 위한 습관이다. (stdout에 `print`를 쓰면 안 되는 규칙은 SDK를 써도 같다.)
- **`python` 명령이 없는 Linux** — `python3 prepare.py`로 실행하면 `opencode.json`에는 `.venv/bin/python`이 들어가므로 이후 `python` 명령이 필요 없다.
