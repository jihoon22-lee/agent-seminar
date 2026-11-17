# M15 opencode가 MCP의 새 기능을 어디까지 받아 주나

> 구성: Python 서버 1개 + 관찰 스크립트(probe.py) | 난이도: ★★★ | 필요: opencode 1.19.5, Python 3.10+ (모델 불필요, 가짜 모델 사용) | 슬라이드: MCP — 클라이언트 지원 범위

## 무엇을 보여 주나

MCP 스펙에는 "도구 호출" 말고도 진행 알림, 구조화된 결과, 도구 목록 변경 알림, 서버가 클라이언트에게 거꾸로 요청하는 기능(sampling, elicitation) 같은 것이 있다. 서버가 이것을 **보낸다고 해서** 에이전트가 **쓰는 것은 아니다.** 클라이언트가 받아서 무엇을 하는지는 클라이언트마다 다르다.

이 예제는 그 기능들을 일부러 전부 보내 보는 서버(`server.py`)와, 진짜 opencode 1.19.5를 붙여 놓고 **무슨 일이 일어났는지(혹은 아무 일도 안 일어났는지)** 기록해서 표로 출력하는 `probe.py`로 이루어져 있다. 모델은 가짜 모델이라서 항상 같은 결과가 나오고 인터넷이 필요 없다. `check.py` 는 관찰한 동작을 그대로 못 박아 둔다. opencode가 업데이트되어 동작이 바뀌면 검사가 실패해서 알려 준다.

## 실무에서는

- **서버를 만들기 전에 "클라이언트가 이것을 받아 주나?"를 확인하는 방법**이다. 스펙에 있는 기능을 믿고 서버를 설계했다가, 에이전트가 무시해서 아무 효과가 없는 경우가 생긴다. 이 예제의 표가 그 확인표다.
- 결론 세 줄(자세한 근거는 아래 표):
  1. **중요한 결과는 항상 `content` 의 text 블록에 넣는다.** `structuredContent` 만 있으면 모델이 JSON 문자열을 받고, text 도 같이 있으면 `structuredContent` 는 모델에게 가지 않는다.
  2. **sampling 과 elicitation 에 기대지 않는다.** opencode 1.19.5는 이 기능을 선언하지 않고, 요청하면 `-32601` 로 거절한다.
  3. **도구 목록을 동적으로 바꾸는 것은 된다.** `list_changed` 를 보내면 다음 모델 요청부터 새 도구가 보인다. 오래 걸리는 도구는 **진행 알림을 보내면** 도구 호출 제한 시간이 늘어난다. 단, 화면에는 아무것도 보이지 않는다.

## 파일 구성

```
m15-client-features/
  README.md        이 문서
  server.py        관찰용 MCP 서버. 도구 5개 + late_tool. 관찰한 사실을 M15_LOG 파일에 JSON 한 줄씩 남긴다
  probe.py         opencode를 가짜 모델로 4번 돌려 관찰 결과와 요약표를 출력 (Sandbox 안에서만 실행)
  opencode.json    mcp.features: ["python", "server.py"]
  check.py         서버 단독 검사 + opencode 동작 고정 검사
  fake_llm.py      가짜 LLM 서버
```

서버의 도구:

| 도구 | 하는 일 |
|---|---|
| `slow_count` | 단계마다 1초 걸린다. 받은 `_meta.progressToken` 으로 `notifications/progress` 를, 그리고 `notifications/message` 를 보낸다. 토큰이 없으면 progress 를 보내지 않는다 |
| `both_text_and_structured` | `content`(text)와 `structuredContent` 를 같이 돌려준다. `outputSchema` 선언 |
| `structured_only` | `content` 는 빈 배열, `structuredContent` 만 돌려준다. `outputSchema` 선언 |
| `add_tool` | 새 도구 `late_tool` 을 추가하고 응답 뒤에 `notifications/tools/list_changed` 를 보낸다 |
| `client_request_probe` | 서버가 거꾸로 `roots/list`, `sampling/createMessage`, `elicitation/create` 요청을 보내고 3초 기다린다 |

## 따라 하기

> Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`opencode.json` 의 `command` 도 `["python3", "server.py"]` 로)

모든 명령은 이 예제 폴더(`examples/02-mcp/m15-client-features`)에서 실행한다. 모델 설정이나 인터넷은 필요 없다.

**1. 관찰 결과 보기 (약 40초)**

```powershell
cd examples\02-mcp\m15-client-features
python probe.py
```

```bash
cd examples/02-mcp/m15-client-features
python3 probe.py
```

`probe.py` 는 opencode 를 격리된 임시 환경(`tools/octest.py` 의 `Sandbox`)에서 네 번 실행한다. 실제 `~/.config/opencode` 와 세션 기록은 건드리지 않는다.

**2. 서버만 연결해 보기**

```powershell
opencode mcp list
```

```bash
opencode mcp list
```

**3. 진짜 모델로 직접 해 보기 (선택)**

```powershell
opencode run -m opencode/big-pickle --auto "features_slow_count 도구를 steps 3으로 호출해 줘"
```

```bash
opencode run -m opencode/big-pickle --auto "features_slow_count 도구를 steps 3으로 호출해 줘"
```

3초 동안 화면에는 `⚙ features_slow_count {"steps":3}` 한 줄뿐이고 진행 상황은 보이지 않는다. 서버가 무엇을 받았는지는 `M15_LOG=events.jsonl` 환경 변수를 주고 실행한 뒤 그 파일을 열어 본다.

## 기대 결과

`python probe.py` (Linux, 2026-11-17 측정. 줄이 긴 부분은 일부 줄임):

```
client initialize : protocolVersion=2025-11-25 clientInfo={'name': 'opencode', 'version': '1.19.5'}
                    capabilities={"roots": {}}
progressToken     : {'slow_count': 2, 'both_text_and_structured': 3, 'structured_only': 4, 'add_tool': 5, 'late_tool': 7, ...}
notifications/cancelled : tools/call 8번 중 8번
opencode 화면(⚙ 줄) : ['⚙ features_slow_count {"steps":3}', '⚙ features_both_text_and_structured Unknown', ...]
'progress'라는 글자가 opencode 출력에 있는가 - 기본 화면+--print-logs DEBUG: 아니오, --format json 이벤트: 아니오
--format json 도구 이벤트의 metadata : {'truncated': False}
notifications/message(로그)가 --print-logs DEBUG에 나오는가: 예 / --print-logs 없이 돌린 세션에 나오는가: 아니오
    예) level=INFO run=859c8abc message="MCP server log" server=features logger=m15 level=info data="slow_count 1/3"
서버의 stderr가 --print-logs DEBUG에 나오는가: 아니오
모델이 받은 결과 (text+structured) : '항목 2개: alpha, beta (이 문장은 text 블록)'
모델이 받은 결과 (structured만)    : '{"count":3,"items":["x","y","z"]}'
모델에게 간 도구 정의의 키          : ['description', 'name', 'parameters']
  structured_only 정의 전체        : {"name": "features_structured_only", "description": "...", "parameters": {"type": "object", "properties": {}, "additionalProperties": false}}
outputSchema가 모델에게 갔는가      : 아니오
tools/list 호출 횟수 2번, list_changed 뒤에 다시 불렀는가: 예
late_tool이 처음 보인 모델 요청 : 5번째 (add_tool 결과가 처음 간 요청 : 5번째, 전체 9번)
그 요청에서 바로 late_tool을 불렀는가: 예
서버 -> 클라이언트 요청 roots/list: {"roots": [{"uri": "file:///.../m15-client-features"}]}
서버 -> 클라이언트 요청 sampling/createMessage: {"code": -32601, "message": "Method not found"}
서버 -> 클라이언트 요청 elicitation/create: {"code": -32601, "message": "Method not found"}
timeout=3000ms, 5초짜리 도구: 진행 알림 있음 -> '5단계를 모두 마쳤다. 토큰: 있음'
timeout=3000ms, 5초짜리 도구: 진행 알림 없음 -> 'MCP error -32001: Request timed out'
```

## 동작 원리

### 정리표

| 기능 | 서버가 보낸 것 | opencode 1.19.5가 한 일 | 그래서 서버를 이렇게 만든다 |
|---|---|---|---|
| 클라이언트 capabilities | (서버가 받는다) | `{"roots": {}}` 만 선언. protocolVersion `2025-11-25`, clientInfo `opencode` `1.19.5` | `initialize` 에서 `capabilities` 를 보고 기능을 쓸지 정한다. 선언 없는 기능은 쓰지 않는다 |
| `_meta.progressToken` | (클라이언트가 보낸다) | **모든** `tools/call` 에 정수 토큰을 붙인다. 값은 그 요청의 id 와 같다 (`notifications/cancelled` 의 `requestId` 와 일치) | 토큰이 있을 때만 progress 를 보낸다. 토큰이 없는 클라이언트도 있으니 `None` 을 처리한다 |
| `notifications/progress` | 단계마다 토큰·progress·total·message 전송 | 오류 없이 받는다. **화면, `--print-logs DEBUG`, `--format json` 이벤트 어디에도 나오지 않는다.** 대신 **도구 호출 제한 시간을 늘려 준다** (`timeout: 3000` 에서 5초짜리 도구: 알림 있으면 완료, 없으면 `MCP error -32001: Request timed out`) | 사용자에게 보여 줄 목적으로는 쓸 수 없다. 오래 걸리는 도구가 제한 시간에 걸릴 때 "살아 있다"는 신호로는 쓸 수 있다. 결과는 끝에 text 로 정리해서 준다 |
| `notifications/message` | `level=info` 로그 전송 | `--print-logs --log-level DEBUG` 로그에 `MCP server log server=features logger=m15 level=info data="..."` 줄로만 나온다. 옵션 없이는 안 나온다 | 사용자에게 보일 정보가 아니라 디버깅용이다 |
| 서버 stderr | `[m15] ...` 로그 | `--print-logs DEBUG` 에도 나오지 않는다 | 서버 쪽 진단은 파일로 남긴다 (이 서버의 `M15_LOG`). 화면에 나올 거라고 기대하지 않는다 |
| `structuredContent` + text | `content` 에 text, `structuredContent` 에 JSON, `outputSchema` 선언 | 모델은 **text 블록만** 받는다 | 중요한 결과는 text 에 넣는다. `structuredContent` 는 모델에게 가지 않는다 |
| `structuredContent` 만 | `content: []`, `structuredContent` 에 JSON | 모델은 `{"count":3,"items":["x","y","z"]}` 같은 **compact JSON 문자열**을 받는다 | 모델이 읽을 수는 있지만, text 로 설명을 같이 주는 편이 안전하다 |
| `outputSchema` | `tools/list` 의 도구 정의에 포함 | 모델에게 가는 도구 정의에는 **들어가지 않는다** (`name`, `description`, `parameters` 만) | 출력 모양에 대한 설명은 `description` 에 글로 쓴다 |
| `notifications/tools/list_changed` | `add_tool` 응답 뒤에 전송 | `tools/list` 를 다시 요청하고, **add_tool 결과가 가는 바로 그 모델 요청**(5번째)부터 새 도구가 목록에 있다. 그 요청에서 모델이 `late_tool` 을 불러 성공했다 | 동적 도구 목록을 써도 된다. `capabilities.tools.listChanged: true` 를 선언한다 |
| `roots/list` (서버→클라이언트) | 요청 | 프로젝트 폴더의 `file://` URI 하나를 답한다 | 서버가 "어느 폴더에서 일하나"를 알아야 하면 쓸 수 있다 (경로가 서버로 간다는 점에 유의) |
| `sampling/createMessage`, `elicitation/create` | 요청 | 즉시 `-32601 Method not found` 로 거절 (초 단위 대기 없음) | 이 기능에 기대는 서버는 opencode 에서 동작하지 않는다. 사용자에게 물어봐야 하면 도구 결과로 질문을 돌려주고 모델이 대신 묻게 한다 |
| `notifications/cancelled` | (클라이언트가 보낸다) | 호출이 끝날 때마다 `reason: "AbortError: The operation was aborted."` 로 온다 (8번 호출에 8번) | 알림이므로 답하지 않는다. 정상 호출 뒤에도 오므로 오류로 취급하지 않는다 |

### 읽을 때 주의할 것

- `⚙ features_late_tool Unknown` 처럼 `Unknown` 이 붙는 것은 구조화 결과나 도구 종류 때문이 아니라 **인자가 없는 호출**의 표시다. 인자가 있는 호출은 `⚙ features_slow_count {"steps":3}` 처럼 JSON 이 나온다.
- 진행 알림이 시간 제한을 늘려 주는지는 `timeout: 3000` 으로 줄인 설정에서 5초짜리 도구(단계마다 1초, 5단계)로 확인했다. 알림이 없을 때는 약 3초에 실패했다. 알림이 있을 때 **얼마나 오래** 늘려 주는지(총 상한이 있는지)는 확인하지 못했다.
- `notifications/message` 는 `--print-logs --log-level DEBUG` 로 확인했다. `INFO`, `ERROR` 수준에서 나오는지는 따로 시험하지 않았다.
- 이미지나 리소스 링크 같은 다른 결과 형식은 이 예제에서 다루지 않았다.

### 서버가 관찰하는 방법

`server.py` 는 환경 변수 `M15_LOG` 가 가리키는 파일에 이벤트를 JSON 한 줄씩 남긴다. opencode 가 서버를 띄울 때 환경 변수를 그대로 물려주므로 `probe.py` 와 `check.py` 가 이 파일을 읽어 "서버가 무엇을 받았는지"를 알아낸다.

```
{"event": "initialize", "protocolVersion": "2025-11-25", "clientCapabilities": {"roots": {}}, "clientInfo": {"name": "opencode", "version": "1.19.5"}}
{"event": "call", "tool": "slow_count", "progressToken": 2, "meta": {"progressToken": 2}}
{"event": "cancelled", "params": {"requestId": 2, "reason": "AbortError: The operation was aborted."}}
```

서버가 클라이언트에게 요청을 보내고 답을 기다리는 동안에도 stdin 을 읽어야 해서, 읽기는 별도 스레드가 맡는다(M1 의 `for line in sys.stdin` 과 다른 점).

## 직접 바꿔 보기

1. **토큰 무시해 보기** — `slow_count` 에서 `token = None` 으로 고정하고 `probe.py` 를 실행한다. 진행 알림이 사라지고 `timeout: 3000` 시험에서 5초 도구가 실패하는지 본다.
2. **text 빼 보기** — `both_text_and_structured` 의 `content` 를 `[]` 로 바꾸면 모델이 받는 것이 JSON 문자열로 바뀐다.
3. **`outputSchema` 에 표식 넣기** — `LIST_SCHEMA` 에 눈에 띄는 속성 이름을 넣고 `probe.py` 의 `output_schema_in_tool_def` 가 여전히 "아니오"인지 확인한다.
4. **늦게 알리기** — `add_tool` 에서 `list_changed` 를 응답 **앞에** 보내거나 보내지 않고 `probe.py` 를 실행해, 새 도구가 몇 번째 모델 요청부터 보이는지 비교한다. (이 예제는 응답 뒤에 보내는 경우만 시험했다.)
5. **opencode 를 올린 뒤** — `check.py` 의 `[opencode]` 검사가 실패하면 어떤 동작이 달라졌는지 `probe.py` 로 확인하고 위 표를 고친다.

## 주의할 점 / 문제 해결

- **이 표는 opencode 1.19.5 한 버전, 가짜 모델 기준이다.** 실제 모델이 같은 도구를 어떻게 쓰는지는 `check.py` 를 `--model` 로 실행했을 때의 소프트 검사 한 가지(도구를 부르는가)만 있다. 다른 클라이언트(Claude Code, 다른 에디터 등)는 다르게 동작할 수 있다. 미검증.
- **세션이 네 번 도는 검사라 느리다** (약 40초). `check.py` 의 `[opencode]` 검사들은 `probe.observe()` 한 번의 결과를 같이 쓴다.
- **새 도구가 보이는 시점은 타이밍에 영향을 받을 수 있다.** 가짜 모델은 도구 결과를 받자마자 다음 요청을 보내는데, 이 환경에서는 `list_changed` 직후의 첫 모델 요청(5번째)에 이미 새 도구가 들어 있었고 여러 번 반복해도 같았다. `tools/list` 응답이 느린 서버에서는 확인하지 않았다.
- `probe.py` 가 출력하는 `roots/list` 답에는 이 PC 의 예제 폴더 경로가 들어 있다. 기대 결과 예시에서는 `...` 로 줄였다.
- 임시 이벤트 파일은 `probe.py` 가 끝나면 지운다. 예제 폴더에 생성물은 남지 않는다(`__pycache__` 제외).
- **Windows**: Windows(PowerShell 5.1, opencode 1.19.5)에서 이 예제의 `check.py` 를 실행해 통과했습니다(실패 0). `probe.py` 를 손으로 따라 하는 과정과 실제 모델은 Windows 에서 확인하지 않았습니다.
