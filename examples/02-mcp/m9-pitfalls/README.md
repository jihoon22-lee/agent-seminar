# M9 MCP 서버가 고장 났을 때: 디버깅 갤러리

> 구성: 일부러 고장 낸 서버 4개 + 고친 서버 1개 + 진단 스크립트(demo.py) | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: MCP — 안 될 때 어디를 보나

## 무엇을 보여 주나

MCP 서버가 안 붙거나 이상하게 동작할 때 opencode 화면에는 `failed` 한 단어만 보이는 경우가 많습니다. 이 예제는 흔한 고장 네 가지를 일부러 만들어 두고,
`opencode mcp list`가 알려 주는 것과 **알려 주지 않는 것**, 서버를 직접 띄워 보는 방법, 로그 위치를 한 번에 보여 줍니다.
핵심 한 줄: **stdio MCP 서버의 stdout 은 프로토콜 메시지 전용이고, 로그·배너·디버깅 출력은 stderr 로 보낸다.**
(공개 프로젝트 [agent-browser](https://github.com/jihoon22-lee/agent-browser)도 `docs/handoff.md` 에서 MCP 프로세스의 출력 규칙으로 같은 원칙을 개발 지침에 못 박아 두었습니다.
사람이 읽을 출력은 표준 에러나 파일로 돌리고, 표준 출력에는 프로토콜 메시지만 둔다는 내용입니다.)

## 실무에서는

- 새로 만든 팀 공용 도구 서버가 `failed` 로 뜰 때: 먼저 서버를 터미널에서 직접 실행해 첫 줄에 JSON 이 나오는지 봅니다. `print()` 디버깅이 남아 있는 경우가 가장 흔합니다.
- 모델/인덱스를 읽어 오는 무거운 서버: 시작이 30초를 넘으면 연결에 실패합니다. 시작을 가볍게 하거나 서버별 `timeout` 을 늘립니다.
- 한국어 Windows 에서만 한글이 깨진다는 제보가 올 때: 서버가 UTF-8 로 맞추지 않았을 가능성이 큽니다. Linux 에서는 재현되지 않아 놓치기 쉽습니다.
- "연결은 되는데 도구를 부르면 에러" 일 때: 도구 코드의 예외 처리입니다. `mcp list` 로는 보이지 않습니다.

## 파일 구성

```
m9-pitfalls/
├── README.md
├── opencode.json       # 서버 6개 등록 (고장 4 + 시간 제한 실험용 1 + 고친 서버 1)
├── broken_stdout.py    # 고장 1: stdout 에 배너가 섞임
├── broken_encoding.py  # 고장 2: UTF-8 로 맞추지 않음 (한국어 Windows 에서 한글 깨짐)
├── slow_start.py       # 고장 3: 시작이 느림 (SLOW_START_SECONDS, SLOW_CALL_SECONDS 환경변수)
├── crash_on_call.py    # 고장 4: tools/call 에서 예외로 프로세스가 죽음
├── fixed_server.py     # 위 네 가지를 모두 피한 서버
├── demo.py             # 진단 데모: mcp list → 직접 probe → 호출 실험 → 진단 표 → 로그 위치
├── fake_llm.py         # 가짜 LLM 서버 (도구 호출 때 모델이 받는 결과를 기록)
└── check.py            # 자동 검증
```

## 따라 하기

> Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`opencode.json` 의 `command` 첫 항목도 같이 바꿉니다. 안 바꾸면 모든 서버가 `Executable not found in $PATH: "python"` 으로 실패합니다.)

### 1. 한 번에 보기

PowerShell:

```powershell
cd examples\02-mcp\m9-pitfalls
python demo.py
```

Linux bash:

```bash
cd examples/02-mcp/m9-pitfalls
python3 demo.py
python3 demo.py --simulate-cp949    # Linux 에서도 한국어 Windows 의 인코딩 문제를 흉내 내 보기
```

약 40초 걸립니다(느린 서버를 일부러 기다리기 때문). 모델·인터넷·계정이 필요 없습니다. 도구 호출 실험에는 가짜 LLM 이 쓰입니다. opencode 는 임시 폴더로 격리해서 실행하므로 내 설정, 세션 기록, 전역 MCP 서버와 섞이지 않고, 끝나면 임시 폴더를 지웁니다.

### 2. 하나씩 손으로

```text
opencode mcp list                  # 서버별 connected / failed 와 사유
python broken_stdout.py            # 서버를 직접 실행: 첫 줄에 배너가 붙어 나오는 것이 보임 (Ctrl+C 로 종료)
```

### 3. 실제 모델로 (평소 쓰는 모델로 실행하면 됩니다)

```text
opencode run --auto "fixed_server 의 greet 도구로 홍길동에게 인사해 줘."
opencode run --auto "crash_on_call 의 greet 도구로 홍길동에게 인사해 줘."
```

모델 설정이 없다면 `-m opencode/big-pickle` 을 붙이세요. 첫 번째는 `⚙ fixed_server_greet {"name":"홍길동"}` 이 보이고, 두 번째는 `✗ crash_on_call_greet … failed / Error: MCP error -32000: Connection closed` 가 보이는 것이 정상입니다(도구 호출 부분은 가짜 모델로 확인한 것과 같음). 그 뒤 모델이 어떻게 반응하는지는 모델마다 다르며, 이 문서를 쓸 때는 무료 모델이 응답하지 않아 실제 모델의 반응은 확인하지 못했습니다.

### 4. 로그 보기

```text
opencode debug paths                                      # log 줄이 로그 폴더
opencode run --print-logs --log-level DEBUG "안녕"         # 로그를 화면(stderr)으로 함께 출력
```

### 5. 자동 검증

```text
python check.py            # 모델 없이 (약 1.5분)
python check.py --model    # 실제 모델이 fixed_server_greet 를 부르는지까지 (soft)
```

## 기대 결과

`python demo.py` (Linux, Python 3.14, opencode 1.19.5, 모델 불필요):

```text
== 1. opencode mcp list (서버 6개를 한 번에 연결해 본다)
  broken_stdout    failed     Operation timed out after 5000ms
  broken_encoding  connected  
  slow_start       failed     Operation timed out after 3000ms
  slow_start_ok    connected  
  crash_on_call    connected  
  fixed_server     connected  

== 2. probe: 서버를 직접 띄워 한글 인사를 요청해 본다
  broken_stdout    init=- json첫줄=False utf8=True greet=None 호출후생존=None
  broken_encoding  init=0.0 json첫줄=True utf8=True greet='안녕하세요, 홍길동님!' 호출후생존=True
  slow_start       init=8.0 json첫줄=True utf8=True greet='안녕하세요, 홍길동님!' 호출후생존=True
  crash_on_call    init=0.0 json첫줄=True utf8=True greet=None 호출후생존=False
  fixed_server     init=0.0 json첫줄=True utf8=True greet='안녕하세요, 홍길동님!' 호출후생존=True

== 3. 도구 호출 때 모델에게 보이는 것 (가짜 모델이 도구를 호출)
  [crash_on_call] 사용자 화면:
      ✗ crash_on_call_greet {"name":"홍길동"} failed
      Error: MCP error -32000: Connection closed
      ✗ Invalid Tool
  [crash_on_call] 모델이 받은 결과 1: 'MCP error -32000: Connection closed'
  [crash_on_call] 모델이 받은 결과 2: "The arguments provided to the tool are invalid: Model tried to call unavailable tool 'crash_on_call_greet'. Av…"
  [fixed_server] 모델이 받은 결과 1: '도구 실행 실패: database connection lost'
  [fixed_server] 모델이 받은 결과 2: '도구 실행 실패: database connection lost'

== 4. 진단 표
  broken_stdout    failed     stdout 에 JSON 이 아닌 글자가 섞임: 'My MCP Server v1.0 starting... {"jsonrpc": "2.0"' → 로그는 stderr 로
  broken_encoding  connected  문제 없음
  slow_start       failed     initialize 까지 8.0초 > timeout 3000ms → timeout 늘리거나 시작을 가볍게
  crash_on_call    connected  tools/call 중 프로세스 종료(exit 1): RuntimeError: database connection lost → try/except 후 isError 반환
```

같은 `demo.py` 를 **한국어 Windows**(코드 페이지 949, Python 3.12)에서 실행했을 때 달라지는 부분:

```text
  broken_encoding  init=0.1 json첫줄=True utf8=False greet='�ȳ��ϼ���, 홍길동��!' 호출후생존=True
  [broken_encoding] 사용자 화면:
      ⚙ broken_encoding_greet {"name":"홍길동"}
  [broken_encoding] 모델이 받은 결과 1: '�ȳ��ϼ���, 홍길동��!'
  broken_encoding  connected  UTF-8 아님/한글 불일치: '�ȳ��ϼ���, 홍길동��!' → reconfigure(encoding='utf-8')
```

Linux 에서는 같은 서버가 멀쩡하고(`greet='안녕하세요, 홍길동님!'`), `--simulate-cp949` 를 주면 서버가 한글을 받자마자 죽습니다.

로그 파일(`opencode debug paths` 의 log 폴더, 파일 이름 `opencode.log`)에 남는 경고:

```text
level=WARN message="server unavailable" key=slow_start type=local status=failed
level=WARN message="MCP connection closed" server=crash_on_call
```

## 동작 원리

### 고장 1. stdout 오염 (`broken_stdout.py`)

opencode 는 서버의 stdout 을 **줄 단위 JSON-RPC** 로 읽습니다. 1.19.5 에서 관찰한 것:

| 서버가 stdout 에 한 짓 | 결과 |
| --- | --- |
| 줄바꿈 있는 잡음 한 줄 (`print("배너")`, `{ starting`, JSON 이지만 MCP 메시지가 아닌 줄) | **무시되고 정상 동작** (`STDOUT_MODE=line` 으로 확인) |
| **줄바꿈 없는** 잡음 (`sys.stdout.write("배너 ")`, `print("…", end="")`) | 다음 JSON 응답 앞에 붙어 그 줄이 통째로 깨짐 → initialize 응답이 없는 것처럼 되어 제한 시간 뒤 `failed (Operation timed out after …ms)` |

즉 "배너가 있어도 되더라" 는 우연일 뿐입니다. 다른 MCP 클라이언트가 같은 관대함을 보인다는 보장은 없고(이 예제에서는 opencode 만 확인), 한 번 줄바꿈 없이 쓰는 순간 서버가 통째로 죽습니다. 규칙은 단순하게: **stdout 에는 MCP 메시지만.**
`failed` 의 사유가 시간 초과로만 나오므로, 서버를 직접 실행해 첫 줄을 눈으로 보는 것이 가장 빠릅니다. (`demo.py` 의 probe 가 이 일을 합니다.)

### 고장 2. UTF-8 가 아님 (`broken_encoding.py`)

MCP 는 UTF-8 JSON 을 주고받지만 Python 의 stdout/stdin 은 기본적으로 OS 로케일 인코딩을 씁니다.

- **Linux**: UTF-8 이라 문제가 드러나지 않습니다. 이 서버도 멀쩡합니다. (그래서 Linux 에서만 개발하면 놓칩니다.)
- **한국어 Windows (코드 페이지 949)**: 서버가 보낸 한글이 cp949 바이트로 나가고 opencode 는 UTF-8 로 읽으므로 대체 문자(`�`)가 됩니다. `mcp list` 는 `connected`, 도구 호출도 성공으로 보이는데 **모델이 받는 텍스트가 깨져** 있습니다. 조용히 틀립니다.
  사용자가 보낸 한글 인자(`홍길동`)는 우연히 원래 바이트로 되돌아와 멀쩡해 보이는 점이 오히려 원인 찾기를 어렵게 합니다.
- 영어 Windows(cp1252)처럼 한글을 표현할 수 없는 로케일에서는 `UnicodeEncodeError` 로 서버가 죽을 것으로 예상되지만 **이 예제에서 확인하지는 않았습니다.**
- 고치는 법: 서버 맨 위에 `sys.stdout.reconfigure(encoding="utf-8")`, `sys.stdin.reconfigure(encoding="utf-8")`. 파일은 `open(..., encoding="utf-8")`. 또는 `opencode.json` 의 `environment` 에 `"PYTHONUTF8": "1"` 을 주는 우회도 있습니다(`environment` 가 프로세스 환경변수를 덮어쓰는 것은 확인함). 그래도 서버 코드에서 고치는 쪽이 이식성이 좋습니다.
- `opencode.json` 의 이 서버에는 `"environment": {"PYTHONUTF8": "0"}` 이 들어 있습니다. 내 환경에 `PYTHONUTF8=1` 이 켜져 있어도 고장이 재현되도록 UTF-8 모드를 끄는 설정입니다.

### 고장 3. 느린 시작 (`slow_start.py`)와 타임아웃 키

실험 결과(모두 직접 측정):

| 설정 | 결과 |
| --- | --- |
| 키 없음, 시작 8초 | connected |
| 키 없음, 시작 40초 | failed (기본 연결 제한 시간은 약 30초) |
| `mcp.<서버>.timeout: 3000` (ms), 시작 8초 | failed — 사유 `Operation timed out after 3000ms` |
| `mcp.<서버>.timeout: 15000`, 시작 8초 | connected |
| `experimental.mcp_timeout: 3000`, 시작 8초 | **connected** — 이 키는 시작 제한이 아닙니다 |
| `experimental.mcp_timeout: 2000`, 도구 호출에 5초 | 모델이 받는 결과 `MCP error -32001: Request timed out` |
| 키 없음, 도구 호출에 5~8초 | 성공 / 65초는 시간 초과 (호출 기본 제한은 약 60초로 보임) |
| `mcp.<서버>.timeout: 3000`, 도구 호출에 8초 | 시간 초과 (서버별 `timeout` 은 호출에도 적용되는 것으로 관찰) |

정리: **서버별 `timeout`(밀리초)은 연결(시작+도구 목록)과 도구 호출에 모두 적용**되고, `experimental.mcp_timeout` 은 도구 호출에만 적용됩니다(시작 제한이 아님). 이 예제의 `opencode.json` 은 데모가 빨리 끝나도록 일부러 `slow_start` 를 3초, `slow_start_ok` 를 15초로 둡니다.
시작이 느린 진짜 원인은 보통 무거운 초기화입니다. 입력을 읽기 전에 끝내려 하지 말고, 첫 도구 호출 때 하거나 백그라운드 스레드로 미루세요.

### 고장 4. 호출 시 크래시 (`crash_on_call.py`)

- 시작과 `tools/list` 는 정상이라 `mcp list` 는 `connected` 입니다. 도구를 부르는 순간 서버 프로세스가 죽습니다.
- 사용자 화면: `✗ crash_on_call_greet {...} failed` + `Error: MCP error -32000: Connection closed`. 모델이 받는 결과도 같은 문장입니다. 원인(`database connection lost`)은 모델에게도 사용자에게도 전달되지 않습니다.
- 한 번 죽으면 opencode 는 그 서버의 도구를 목록에서 뺍니다. 같은 실행 안에서 같은 도구를 다시 부르면 `Model tried to call unavailable tool` 이 돌아옵니다. (TUI 에서 MCP 서버를 다시 연결하는 방법이 있는지는 확인하지 않았습니다. 확실한 방법은 opencode 를 다시 시작하는 것입니다.)
- 서버의 traceback 은 stderr 로 나가는데 opencode 화면에도 로그 파일(DEBUG 포함)에도 **나오지 않는 것으로 관찰**됐습니다. 로그에는 `MCP connection closed server=crash_on_call` 한 줄뿐입니다. 서버를 직접 실행해야 원인이 보입니다.
- 고친 방식(`fixed_server.py`): 도구 실행을 `try/except` 로 감싸 `{"isError": true, "content": [...]}` 결과를 돌려줍니다. 서버는 살아 있고 모델은 `도구 실행 실패: database connection lost` 를 읽고 대응할 수 있습니다. 두 번째 호출도 같은 방식으로 응답합니다.

### 로그는 어디에

- 위치: `opencode debug paths` 가 출력하는 `log` 줄. 파일 이름은 `opencode.log` 하나이고 `<XDG_DATA_HOME 또는 ~/.local/share>/opencode/log` 아래에 있었습니다. (Windows 기본 위치는 이 예제에서 확인하지 않았으니 `debug paths` 로 확인하세요.)
- 화면으로: `--print-logs`, 자세히: `--log-level DEBUG`. `mcp list` 에도 붙습니다.
- 서버 연결 실패는 `WARN … message="server unavailable" key=<서버> … status=failed`, 도구 호출 중 끊김은 `WARN … message="MCP connection closed" server=<서버>` 입니다.
- 서버가 stderr 로 쓴 내용은 opencode 로그에 없으므로, 서버 안에서 파일 로그(`logging.FileHandler`)를 쓰거나 서버를 직접 실행하세요.

## 직접 바꿔 보기

1. `opencode.json` 에서 `broken_stdout` 의 환경변수를 `"STDOUT_MODE": "line"` 으로 바꿔 보세요(`environment` 추가). `mcp list` 가 `connected` 가 되고 도구도 동작합니다. 그래도 왜 고쳐야 하는지 `demo.py` 의 probe 줄(`json첫줄=False`)로 설명해 보세요.
2. `fixed_server.py` 에 5초 걸리는 도구를 추가하고 `experimental.mcp_timeout` 을 2000 으로 줄여 `Request timed out` 을 직접 만들어 보세요.
3. `broken_encoding.py` 에 `sys.stdout.reconfigure(encoding="utf-8")` 와 `sys.stdin.reconfigure(encoding="utf-8")` 두 줄만 추가하고 `python demo.py --simulate-cp949` 의 결과를 비교하세요.

## 주의할 점 / 문제 해결

- `opencode.json` 에 `python` 이 적혀 있습니다. Linux 에 `python` 이 없으면 `Executable not found in $PATH: "python"` 으로 6개 모두 실패합니다.
- `demo.py` 가 서버를 직접 띄울 때는 현재 Python(`sys.executable`)을 씁니다. `opencode.json` 의 `python` 과 다른 Python 일 수 있습니다.
- Windows 의 `opencode mcp list` 는 세로선을 `│` 대신 `|` 로 그립니다. `demo.py` 는 둘 다 처리합니다.
- 자동화에서 `opencode run` 을 띄울 때는 `PWD` 환경변수를 작업 폴더에 맞추세요(`opencode run` 은 cwd 가 아니라 `PWD` 를 보는 것으로 관찰됨. m7 참고).
- `demo.py` 는 `mcp list` 에서 가장 느린 서버(5초 제한)를 기다리느라 몇 초 걸립니다. 도구 호출 실험은 가짜 LLM 이라 즉시 끝납니다.
