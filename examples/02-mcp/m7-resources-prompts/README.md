# M7 MCP의 resources와 prompts

> 구성: MCP 서버 1개 (`server.py`) + 런북 3개 + 점검 스크립트 | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: MCP — 도구 말고도 있다

## 무엇을 보여 주나

MCP 서버는 도구(tools)만 주는 것이 아닙니다. 읽을 수 있는 자료 목록인 **resources**와 미리 써 둔 요청문 틀인 **prompts**도 줄 수 있습니다.
이 예제의 서버는 도구 1개, 런북 resources 3개, prompts 2개를 모두 내놓고, opencode 1.19.5가 각각을 **어디에 어떻게 노출하는지**를 실제로 확인합니다.
결론부터 말하면 prompts는 `/서버:프롬프트` 슬래시 명령이 되고, resources는 TUI에서 `@`로 붙이거나 모델이 내장 도구로 읽습니다.
다만 `opencode run`(비대화형)에서는 일부가 막혀 있습니다. 그 한계도 아래에 표로 정리했습니다.

## 실무에서는

- 장애 대응 런북, 팀 위키 문서, API 명세처럼 "읽기 전용 참고 자료"를 도구 호출 없이 대화에 첨부하고 싶을 때 resources가 맞습니다.
- 자주 쓰는 요청문(장애 보고서 초안, 리뷰 체크리스트, 릴리스 노트 틀)을 팀 서버 한 곳에서 관리하고 모두가 같은 슬래시 명령으로 쓰게 하고 싶을 때 prompts가 맞습니다.
- 도구와 달리 resources와 prompts는 **사람이 고르는** 것입니다. 모델이 알아서 호출하는 도구와 달리 사용자가 `@`나 `/`로 명시하므로 "이 문서만 보고 답해"를 정확히 지시할 수 있습니다.

## 파일 구성

```
m7-resources-prompts/
├── README.md
├── opencode.json        # runbooks 서버 1개 등록 (command: python server.py)
├── server.py            # 표준 라이브러리만 쓴 MCP 서버: tools + resources + prompts
├── runbooks/            # resources 로 노출되는 마크다운 3개
│   ├── payment-restart.md   → runbook://payment/restart
│   ├── db-failover.md       → runbook://database/failover
│   └── cache-flush.md       → runbook://cache/flush
├── inspect_server.py    # 실행 중인 opencode serve 에게 슬래시 명령·리소스 목록을 물어 보는 스크립트
├── fake_llm.py          # 가짜 LLM 서버 (check.py 가 "모델이 무엇을 받았나"를 기록하는 데 사용)
└── check.py             # 자동 검증
```

## 따라 하기

> Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`opencode.json`의 `command` 첫 항목도 같이 바꿉니다.)

### 1. 서버가 resources/prompts 를 제대로 말하는지 직접 확인

PowerShell:

```powershell
cd examples\02-mcp\m7-resources-prompts
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}','{"jsonrpc":"2.0","id":2,"method":"prompts/list"}' | python server.py
```

Linux bash:

```bash
cd examples/02-mcp/m7-resources-prompts
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' '{"jsonrpc":"2.0","id":2,"method":"prompts/list"}' | python3 server.py
```

`[m7] request …` 줄은 stderr 로그이고, `{"jsonrpc"…}` 줄이 stdout 의 MCP 메시지입니다.

### 2. opencode 가 연결했는지 확인

```text
opencode mcp list
```

`✓ runbooks connected` 가 나오면 됩니다.

### 3. 슬래시 명령(prompts)과 @ 리소스(resources) 사용 — TUI

이 폴더에서 `opencode` 를 실행(평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 `opencode -m opencode/big-pickle`)한 뒤:

1. 입력창에 `/runb` 까지 치면 자동완성에 `/runbooks:incident-report` 와 `/runbooks:review-checklist` 가 `mcp` 표시와 함께 나옵니다.
2. `/runbooks:incident-report INC-4242` 를 보내면 서버의 `incident-report` 프롬프트가 펼쳐져(티켓 번호가 `$1` 자리에 들어감) 모델에게 전달됩니다.
3. `@pay` 를 치면 파일 목록 맨 위에 `payment-restart  운영 런북 (payment/restart)` 이 나옵니다. 고르고 `결제 서비스 재시작 절차를 3줄로 요약해줘` 를 이어서 보냅니다.
4. 또는 `@` 없이 "runbooks 서버의 리소스를 보고 DB 장애 조치 첫 단계를 알려줘" 라고 말하면 모델이 `list_mcp_resources` → `read_mcp_resource` 도구로 직접 읽습니다.

### 4. 비대화형(`opencode run`)

PowerShell / bash 공통:

```text
opencode run --command runbooks:incident-report INC-4242
opencode run "runbooks MCP 서버의 리소스 중 결제 서비스 재시작 런북을 읽어서 첫 번째 단계만 한 줄로 알려줘."
```

### 5. 목록 API 로 확인 (선택)

터미널 하나에서 `opencode serve --port 4096`, 다른 터미널에서:

```text
python inspect_server.py http://127.0.0.1:4096
```

### 6. 자동 검증

```text
python check.py            # 모델 없이 (가짜 LLM 사용)
python check.py --model    # 실제 모델이 read_mcp_resource 를 부르는지까지 (soft)
```

## 기대 결과

아래는 모두 opencode 1.19.5 에서 직접 캡처한 출력입니다.

`inspect_server.py` (opencode serve 의 `GET /command`, `GET /experimental/resource`):

```text
== MCP 프롬프트 → 슬래시 명령 (GET /command, source=mcp)
  /runbooks:incident-report     hints=['$1']  티켓 번호로 장애 보고서 초안을 쓰게 하는 프롬프트
  /runbooks:review-checklist    hints=[]  코드 리뷰 체크리스트로 변경분을 검토하게 하는 프롬프트
== MCP 리소스 (GET /experimental/resource)
  runbook://payment/restart      client=runbooks  name=payment-restart  mime=text/markdown
  runbook://database/failover    client=runbooks  name=database-failover  mime=text/markdown
  runbook://cache/flush          client=runbooks  name=cache-flush  mime=text/markdown
```

TUI 입력창에 `/runb` 를 쳤을 때의 자동완성 (tmux 로 캡처, 폭에 맞춰 잘림):

```text
┃ /runbooks:incident-report:mcp    티켓 번호로 장애 보고서 초안을 쓰게 하
┃ /runbooks:review-checklist:mcp   코드 리뷰 체크리스트로 변경분을 검토하
┃  /runb
```

`@pay` 를 쳤을 때 (리소스가 파일 목록 맨 위에 설명과 함께 나옴):

```text
┃ payment-restart 운영 런북 (payment/restart)
┃ runbooks/payment-restart.md
┃ server.py
┃ runbooks/db-failover.md
┃ runbooks/cache-flush.md
┃ opencode.json
┃  @pay
```

`@payment-restart  요약해줘` 를 보냈을 때 모델이 받은 사용자 메시지 (가짜 LLM 이 기록한 요청 본문):

```text
{"type":"text","text":"@payment-restart  요약해줘"}
{"type":"text","text":"Reading MCP resource: payment-restart (runbook://payment/restart)"}
{"type":"text","text":"# 결제 서비스 재시작 런북\n\n1. `payment-api` 인스턴스를 로드밸런서에서 분리한다(drain 30초). …"}
```

모델이 resources 를 도구로 읽는 경우 (`opencode run`, 모델 `opencode/big-pickle`):

```text
`payment-api` 인스턴스를 로드밸런서에서 분리한다(drain 30초).

> build · big-pickle

⚙ list_mcp_resources MCP resources: runbooks
⚙ list_mcp_resource_templates MCP resource templates: runbooks
⚙ runbooks_list_runbooks Unknown
⚙ read_mcp_resource MCP resource: runbook://payment/restart
```

## 동작 원리

1. `server.py` 는 `initialize` 응답의 `capabilities` 에 `tools`, `resources`, `prompts` 를 모두 선언합니다. 선언한 기능만 opencode 가 물어봅니다.
2. opencode 는 연결 직후 `tools/list` 와 `prompts/list` 를 호출합니다. 리소스 목록(`resources/list`)은 목록을 요청받을 때(`@` 자동완성, `GET /experimental/resource`) 가져오고, `resources/templates/list` 는 모델이 `list_mcp_resource_templates` 도구를 부를 때 쓰입니다. 서버 요청 순서는 서버를 감싸는 기록용 래퍼로 직접 관찰했습니다.
3. **prompts** 는 `source: "mcp"` 인 명령으로 명령 목록에 합쳐집니다. 이름은 `<서버 이름>:<프롬프트 이름>`, 프롬프트 인자는 `$1`, `$2`… 위치 인자(`hints`)로 보입니다.
   실행할 때 opencode 는 `prompts/get` 을 호출하는데, **인자 값으로 사용자 입력이 아니라 리터럴 문자열 `"$1"`을 넣어서** 보냅니다(`{"ticket_id": "$1"}`).
   서버가 돌려준 본문에서 `$1` 을 사용자 입력으로 opencode 가 직접 바꿔 모델에게 보냅니다. 그래서 **서버는 사용자가 친 실제 값을 볼 수 없고**,
   인자를 본문 어딘가에 그대로 끼워 넣는 프롬프트(이 예제처럼)만 의도대로 동작합니다. 인자로 DB 를 조회하거나 값을 검증하는 프롬프트는 1.19.5 에서 기대대로 안 됩니다.
4. **resources** 는 두 길로 쓰입니다.
   - 사람이 `@` 자동완성에서 고르면 첨부 파일 파트(`type: "file"`, `source.type: "resource"`, `clientName`, `uri`)가 만들어지고, opencode 가 `resources/read` 를 호출해 본문을 사용자 메시지에 `Reading MCP resource: …` 와 함께 붙입니다.
   - 서버가 resources 를 선언하면 모델에게 내장 도구 `list_mcp_resources`, `read_mcp_resource`(인자 `server`, `uri`), `list_mcp_resource_templates` 가 추가되어 모델이 스스로 읽을 수 있습니다. resources 를 선언하는 서버가 없으면 이 세 도구는 붙지 않습니다.
5. 서버의 stderr 로그(`[m7] request …`)는 opencode 화면에도 로그 파일에도 나오지 않는 것으로 관찰됐습니다. 서버를 직접 실행하거나 파일에 로그를 남겨야 합니다. (m9 참고)
6. opencode 는 `initialize` 에서 `protocolVersion: 2025-11-25`, `clientInfo: {name: "opencode", version: "1.19.5"}` 를 보냅니다(서버가 버전을 되돌려 주면 됩니다).

### 관찰한 한계와 주의 (모두 1.19.5 에서 확인)

| 하고 싶은 것 | TUI | `opencode run` / CLI |
| --- | --- | --- |
| MCP 프롬프트를 슬래시 명령으로 실행 | O (`/runbooks:incident-report INC-1`) | `--command runbooks:incident-report INC-1` 만 됨. 메시지 본문에 `/명령` 을 쓰면 펼쳐지지 않고 글자 그대로 모델에게 감 |
| 리소스를 `@` 로 첨부 | O | **불가**. `-f runbook://…` 는 `File not found` (`-f` 는 로컬 파일 경로만 받음) |
| 모델이 리소스를 스스로 읽기 | O | O (`list_mcp_resources` / `read_mcp_resource`) |
| 서버 API 로 첨부 | `POST /session/:id/message` 의 file 파트에 `source.type: "resource"` | 동일 |

- 슬래시 명령 이름의 콜론(`runbooks:incident-report`)은 서버 이름이 앞에 붙은 것입니다. 서버 이름을 바꾸면 명령 이름도 바뀝니다.
- 인자가 하나뿐인 프롬프트에 `INC-1 extra words` 처럼 여러 단어를 주면 **마지막 자리표시자가 나머지를 전부** 받습니다(`티켓 INC-1 extra words 에 대한…`). 인자를 비우면 빈 문자열로 치환됩니다.
- 위 이유로 서버 쪽에서 `ticket_id` 기본값(`INC-0000`)이나 형식 검사를 해도 소용없습니다. 서버가 받은 값을 확인하려면 `M7_TRACE_FILE=<파일>` 환경변수를 `opencode.json` 의 `environment` 에 주면 `prompts/get` 호출이 그 파일에 기록됩니다(`check.py` 가 이렇게 검증).
- resources 와 prompts 는 서버가 `capabilities` 에 선언해야 보입니다. 선언을 빼면 서버가 메서드를 구현해도 opencode 는 `prompts/list`·`resources/list` 를 부르지 않고 명령·리소스 목록이 비어 있습니다(`initialize` → `tools/list` 만 호출되는 것을 직접 확인).
- 자동화 스크립트에서 `opencode run` 을 서브프로세스로 띄울 때는 **환경변수 `PWD`** 를 작업 폴더에 맞추세요. `opencode run` 은 프로세스의 cwd 가 아니라 `PWD` 로 프로젝트 폴더를 정하는 것으로 관찰됐습니다. (부모 셸의 `PWD` 가 그대로 넘어가면 다른 폴더의 설정으로 실행되어 "Unexpected server error" 가 납니다. 일반 터미널에서 직접 실행할 때는 신경 쓰지 않아도 됩니다.)

## 직접 바꿔 보기

1. `server.py` 의 `PROMPTS` 에 `release-notes(version)` 프롬프트를 추가하고, `get_prompt` 에서 본문을 만들어 보세요. opencode 를 다시 시작하면 `/runbooks:release-notes` 가 보입니다.
2. `runbooks/` 에 마크다운을 하나 추가하고 `RUNBOOKS` 딕셔너리에 URI 를 등록해 보세요. `@` 자동완성에 새 항목이 나타납니다. `capabilities` 에서 `"resources": {}` 를 지우면 어떻게 되는지도 확인해 보세요.
3. `opencode.json` 의 서버 이름 `runbooks` 를 `ops-docs` 로 바꾸면 슬래시 명령과 리소스 키가 어떻게 변하는지 `inspect_server.py` 로 비교해 보세요.

## 주의할 점 / 문제 해결

- 서버를 고친 뒤에는 opencode 를 재시작해야 합니다(설정·MCP 목록은 시작할 때 한 번 읽습니다).
- `/runb` 를 쳐도 명령이 안 나오면 `opencode mcp list` 에서 `connected` 인지 먼저 보세요. Linux 에서 `python` 이 없으면 `Executable not found in $PATH: "python"` 으로 실패합니다.
- Windows 에서도 동작은 같습니다. 한글 런북이 깨지면 서버 맨 위의 `sys.stdout.reconfigure(encoding="utf-8")` 가 빠지지 않았는지 확인하세요(m9 참고).
- `check.py` 는 포트 하나(자동으로 빈 포트)를 잠깐 쓰는 `opencode serve` 를 띄웁니다. 다른 프로그램과 충돌하지 않는 임시 포트입니다.
