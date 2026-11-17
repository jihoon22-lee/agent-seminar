# M8 MCP 서버·도구 켜고 끄고 막기

> 구성: MCP 서버 3개(한 파일에서 프로필로 구분) + 비용 측정 스크립트 + 모델이 받은 도구 확인 스크립트 | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: MCP — 많이 붙이면 생기는 일

## 무엇을 보여 주나

MCP 서버를 붙일수록 모델에게 가는 **도구 정의가 매 요청마다** 늘어납니다. 안 쓰는 도구도 컨텍스트를 차지하고, 도구가 많으면 모델이 고르기도 어려워집니다.
이 예제는 서버 통째로 끄기(`enabled: false`), 도구 단위로 숨기기(`permission` deny), 호출 때마다 허락받기(`ask`), 에이전트별로 다르게 주기(`agent.<이름>.tools`)를 직접 해 보고,
**모델이 실제로 받는 도구 목록**을 눈으로 확인하는 방법과 도구가 차지하는 크기를 어림하는 방법을 함께 보여 줍니다.

## 실무에서는

- 팀 공용 MCP 서버 하나가 도구를 수십 개 내놓는데 내 작업에는 서너 개만 필요할 때: 필요한 것만 남기고 나머지는 `deny` 합니다.
- 운영 서버를 건드리는 도구(재시작, 삭제)는 `ask` 로 두어 매번 확인하고, 읽기 전용 점검 도구는 그냥 허용합니다.
- 코드 리뷰 에이전트에는 파일 수정 도구와 운영 도구를 빼서 "읽기만 하는" 에이전트를 만듭니다.
- 예전에 붙여 둔 서버는 지우지 말고 `enabled: false` 로 꺼 두면 설정은 남고 비용은 사라집니다.

## 파일 구성

```
m8-enable-disable-deny/
├── README.md
├── opencode.json            # 서버 3개 + permission 규칙 + reviewer 에이전트
├── mcp_server.py            # --profile docs | ops | legacy 로 도구 묶음이 달라지는 MCP 서버
├── count_tool_tokens.py     # 서버를 직접 띄워 tools/list 크기를 재고 토큰을 어림 (chars/4)
├── show_model_tools.py      # 가짜 LLM 으로 "모델이 받은 도구 목록"을 출력
├── overlays/legacy-on.json  # show_model_tools.py --overlay 용 설정 조각
├── fake_llm.py              # 가짜 LLM 서버 (요청 본문 기록용)
└── check.py                 # 자동 검증
```

`opencode.json` 의 핵심:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "docs":   { "type": "local", "command": ["python", "mcp_server.py", "--profile", "docs"] },
    "ops":    { "type": "local", "command": ["python", "mcp_server.py", "--profile", "ops"] },
    "legacy": { "type": "local", "command": ["python", "mcp_server.py", "--profile", "legacy"], "enabled": false }
  },
  "permission": { "ops_noisy_*": "deny", "ops_restart": "ask" },
  "agent": {
    "reviewer": {
      "description": "검토 에이전트: edit·write 와 ops_* 도구를 쓰지 못한다 (bash, task 는 열려 있다)",
      "mode": "primary",
      "tools": { "ops_*": false, "write": false, "edit": false }
    }
  }
}
```

## 따라 하기

> Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`opencode.json` 의 `command` 첫 항목도 같이 바꿉니다.)

### 1. 도구가 컨텍스트를 얼마나 차지하는지

PowerShell:

```powershell
cd examples\02-mcp\m8-enable-disable-deny
python count_tool_tokens.py
```

Linux bash:

```bash
cd examples/02-mcp/m8-enable-disable-deny
python3 count_tool_tokens.py
```

### 2. opencode 가 보는 서버 상태

```text
opencode mcp list
```

`legacy` 는 `○ legacy disabled` 로 나오고 프로세스도 띄우지 않습니다.

### 3. 모델이 실제로 받는 도구 목록

```text
python show_model_tools.py                    # 기본(build) 에이전트
python show_model_tools.py --agent reviewer   # reviewer 에이전트
python show_model_tools.py --overlay overlays/legacy-on.json   # legacy 를 켠 경우와 비교
```

`overlays/legacy-on.json` 은 `{"mcp":{"legacy":{"enabled":true}}}` 한 줄짜리 설정 조각으로, 스크립트가 `OPENCODE_CONFIG_CONTENT` 로 얹어서 실행합니다(프로젝트 `opencode.json` 은 그대로). JSON 문자열을 직접 줄 수도 있지만 PowerShell 은 따옴표 처리가 까다로워서 파일을 권장합니다.
이 스크립트는 가짜 LLM 서버를 모델로 지정해 `opencode run` 을 한 번 실행합니다. 인터넷도 계정도 필요 없습니다. opencode 는 임시 폴더로 격리해서 실행하므로 내 전역 설정의 MCP 서버가 섞이지 않고 세션 기록도 남지 않습니다.

### 4. 실제 모델로 (평소 쓰는 모델로 실행하면 됩니다)

```text
opencode run --auto "ops MCP 서버의 status 도구로 payment 서비스 상태를 확인해서 한 줄로 알려줘."
opencode run --agent reviewer "ops 서버의 status 도구로 payment 상태를 확인해줘."
```

모델 설정이 없다면 `-m opencode/big-pickle` 을 붙이세요. 두 번째 명령에서는 reviewer 에게 `ops_*` 가 없으므로 도구를 쓰지 못합니다. (이 문서를 쓸 때는 무료 모델이 응답하지 않아 실제 모델의 출력은 캡처하지 못했습니다. 도구 목록과 호출 결과는 위의 가짜 모델 실험으로 확인한 것입니다.)
`ops_restart` 는 `ask` 라서 `opencode run` 에서 `--auto` 없이 호출되면 `permission requested: ops_restart (*); auto-rejecting` 으로 거절됩니다.

### 5. 자동 검증

```text
python check.py            # 모델 없이
python check.py --model    # 실제 모델이 ops_status 를 호출하는지까지 (soft)
```

## 기대 결과

`python count_tool_tokens.py` (opencode.json 의 서버를 직접 띄워 측정):

```text
규칙(적용 순서, 마지막 일치가 이김): ops_noisy_*=deny, ops_restart=ask

server  state tools desc_chars def_chars ~tokens   sent to the model
docs    on        2         42       181      45   2 tools, ~45 tokens per request
ops     on        6       1623      1972     493   2 tools, ~52 tokens per request
legacy  off      12       4623      5415    1353   0 tools, ~0 tokens per request

합계: 모델에게 가는 MCP 도구 정의 ≈ 98 토큰 (매 요청마다)
```

`python show_model_tools.py` (가짜 LLM 이 기록한, opencode 가 모델에게 보낸 `tools` 배열):

```text
에이전트: build(기본)   모델이 받은 도구: 14개
  (내장·기타) 10개  bash, edit, glob, grep, read, skill, task, todowrite, webfetch, write
  docs      2개  docs_lookup, docs_outline
  ops       2개  ops_restart, ops_status
도구 정의 JSON 전체 21506자 (그중 MCP 도구 722자 ≈ 180 토큰)

에이전트: reviewer   모델이 받은 도구: 10개
  (내장·기타)  8개  bash, glob, grep, read, skill, task, todowrite, webfetch
  docs      2개  docs_lookup, docs_outline
도구 정의 JSON 전체 18154자 (그중 MCP 도구 347자 ≈ 86 토큰)

--overlay overlays/legacy-on.json 을 주면:
에이전트: build(기본)   모델이 받은 도구: 26개
  legacy   12개  legacy_op_01 … legacy_op_12
도구 정의 JSON 전체 27941자 (그중 MCP 도구 7157자 ≈ 1789 토큰)
```

서버 하나를 켰을 뿐인데 요청마다 약 1,600 토큰이 늘었습니다. 대화 20번이면 같은 정의가 20번 전송됩니다.

`opencode mcp list`:

```text
●  ✓ docs connected
●  ✓ ops connected
●  ○ legacy disabled
```

`opencode debug agent build` 의 권한 규칙 끝부분 (`permission` 이 규칙으로 번역된 모습):

```text
{'permission': 'ops_noisy_*', 'action': 'deny', 'pattern': '*'}
{'permission': 'ops_restart', 'action': 'ask', 'pattern': '*'}
```

모델이 숨겨진 도구를 억지로 호출했을 때 (가짜 모델이 `ops_noisy_heap_dump` 를 호출하도록 시킨 실험):

```text
✗ Invalid Tool
The arguments provided to the tool are invalid: Model tried to call unavailable tool 'ops_noisy_heap_dump'. Available tools: bash, docs_lookup, docs_outline, edit, glob, grep, invalid, ops_restart, ops_status, read, skill, task, todowrite, webfetch, write.
```

`ask` 도구를 `--auto` 없이 `opencode run` 으로 호출했을 때:

```text
! permission requested: ops_restart (*); auto-rejecting
✗ ops_restart {"service":"pay"} failed
Error: The user rejected permission to use this specific tool call.
```

## 동작 원리

1. **서버 이름 + 도구 이름 = 모델이 보는 이름.** MCP 도구는 `<서버>_<도구>` (`ops_status`) 로 모델에게 전달됩니다. 규칙(`ops_noisy_*`)은 이 합친 이름에 걸립니다.
2. **`mcp.<서버>.enabled: false`**: 서버 프로세스를 띄우지 않고 도구도 목록에 없습니다. `opencode mcp list` 에는 `disabled` 로 보입니다. 상위 설정에서 `false` 인 서버를 프로젝트에서 `true` 로 켤 수도 있습니다(검증: `mcp.legacy.enabled: true` 오버레이로 12개 도구가 나타남).
3. **`permission` 의 `deny`**: 도구 이름 패턴에 `deny` 를 주면 그 도구는 **모델에게 보내는 목록에서 빠집니다**. 컨텍스트를 아끼는 효과는 이쪽에서만 납니다.
   - `ask` 는 도구는 보이되 호출 때 사용자 허락을 받습니다. 목록 크기는 줄지 않습니다. 비대화형 `opencode run` 은 `--auto` 가 없으면 자동 거절, `--auto` 면 승인합니다.
   - `allow` 는 기본값입니다. 규칙은 **나중에 쓴 것이 이깁니다**(마지막 일치 규칙). `{"ops_*": "deny", "ops_status": "allow"}` 는 `ops_status` 만 살리지만, 순서를 바꿔 `{"ops_status": "allow", "ops_*": "deny"}` 로 쓰면 전부 막힙니다. 둘 다 이 폴더에서 확인했습니다.
4. **최상위 `"tools": {"ops_noisy_*": false}`** 도 같은 효과입니다. 1.19.5 는 이 옛 단축형을 `permission` 의 `deny` 규칙으로 번역합니다(`opencode debug agent build` 로 확인). 새로 쓸 때는 `permission` 을 권장합니다.
5. **에이전트별 `tools`**: `agent.reviewer.tools` 는 그 에이전트에만 적용됩니다. `build` 는 그대로입니다. `write: false` 와 `edit: false` 는 둘 다 `edit` 권한의 `deny` 하나로 번역됩니다. 전역에서 `deny` 한 도구를 특정 에이전트에서만 되살리는 것도 됩니다. `"agent": {"debugger": {"mode": "primary", "tools": {"ops_noisy_*": true}}}` (또는 그 에이전트의 `permission` 에 `"ops_noisy_*": "allow"`)를 더하면 `--agent debugger` 일 때만 `ops_noisy_*` 4개가 다시 나타납니다. 에이전트 설정이 전역 설정을 덮어씁니다.
   - **`reviewer` 가 막는 것과 막지 않는 것.** 막는 것: `ops_*` 전부(MCP 쓰기·운영 도구), `edit`, `write`. 모델이 받는 도구 10개(위 `show_model_tools.py` 출력)에는 **`bash` 와 `task` 가 그대로 남아 있습니다.** 그래서 이 에이전트는 MCP 도구와 파일 편집 도구만 막은 검토용 에이전트일 뿐 **읽기 전용이 아닙니다.** `bash` 로 명령을 실행할 수 있고, `task` 로 부른 하위 에이전트는 자기 권한으로 파일을 고칠 수 있습니다(후자는 C8에서 실제로 파일이 바뀌는 것을 확인했습니다. 이 예제에서 `bash`/`task` 를 실행해 보지는 않았고, 목록에 남아 있다는 것만 확인했습니다). 파일을 정말 못 고치는 에이전트가 필요하면 `edit`, `bash`, `task` 를 모두 `deny` 하는 [C8의 `reviewer`](../../00-config/c8-agents/README.md)를 참고하세요.
6. **리소스가 없는 서버만 있으면** `list_mcp_resources`, `read_mcp_resource` 같은 보조 도구는 붙지 않습니다(m7 참고).
7. **크기 어림**: `count_tool_tokens.py` 는 `tools/list` 의 이름·설명·입력 스키마(JSON) 글자 수를 4로 나눕니다. 한글은 글자당 토큰이 더 많아 실제로는 더 클 수 있고, 실제 요청에는 JSON 래퍼가 더 붙습니다. 절대값보다 **서버 간 비교**에 쓰세요.
8. **`opencode debug agent build` 의 한계**: 권한 규칙과 내장 도구만 보여 주고 MCP 도구는 목록에 없습니다. 그래서 `show_model_tools.py` 는 가짜 LLM 이 받은 요청 본문을 읽습니다.

## 직접 바꿔 보기

1. `opencode.json` 의 `permission` 에서 `"ops_noisy_*": "deny"` 를 지우고 `show_model_tools.py` 를 다시 실행해 보세요. `ops_noisy_*` 4개가 나타나고 MCP 도구 크기가 커집니다. 대신 최상위 `"tools": {"ops_noisy_*": false}` 로 바꿔도 결과가 같은지 확인해 보세요.
2. `{"ops_*": "deny", "ops_status": "allow"}` 와 반대 순서를 `permission` 에 써 보세요.
3. `reviewer` 에 `"docs_*": false` 를 더하면 도구가 어떻게 되는지, 새 에이전트 `ops-only` 를 만들어 `docs_*` 만 빼 보세요.

## 주의할 점 / 문제 해결

- 설정을 바꾼 뒤에는 opencode 를 재시작해야 반영됩니다.
- 서버를 켰는데 도구가 안 보이면 `opencode mcp list` 에서 `failed` 인지 보세요(m9 참고). Linux 에서 `python` 이 없으면 `Executable not found in $PATH: "python"` 입니다.
- `deny` 규칙이 의도와 다르게 먹으면 이름 패턴을 `<서버>_<도구>` 기준으로 쓰고 있는지, 패턴 순서(마지막 일치가 이김)를 확인하세요.
- `show_model_tools.py` 가 "모델 요청이 없었다" 로 실패하면 `opencode run` 이 먼저 실패한 것입니다. 메시지에 stderr 가 같이 나옵니다.
- Windows 의 `opencode mcp list` 출력은 세로선을 `│` 대신 `|` 로 그립니다. 사람이 읽는 데는 영향이 없습니다.
