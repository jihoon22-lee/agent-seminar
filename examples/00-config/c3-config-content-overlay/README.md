# C3 실행할 때만 설정 얹기 (`OPENCODE_CONFIG_CONTENT`)

> 구성: launch.py + 작은 MCP 서버 1개 | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: 설정 (환경변수로 덧씌우기)

## 무엇을 보여 주나

설정 파일을 하나도 고치지 않고, **이번에 띄우는 opencode 프로세스에서만** MCP 서버와 설정을 추가하는 방법입니다.
`OPENCODE_CONFIG_CONTENT` 환경변수에 JSON 을 넣어 실행하면 그 JSON 이 **가장 높은 우선순위**로 병합됩니다. 프로젝트 `opencode.json` 이 `username: project-user` 라고 해도 얹은 JSON 이 `overlay-user` 라고 하면 후자가 이깁니다.
`launch.py` 가 이 일을 대신 해 주고, 시계 도구 하나만 가진 `clock_server.py` 를 이번 실행에만 붙입니다. 어떤 `opencode.json` 에도 clock 서버는 적혀 있지 않습니다.

## 실무에서는

실제로 쓰이는 사례가 공개되어 있습니다. [agent-browser](https://github.com/jihoon22-lee/agent-browser) 는 브라우저를 다루는 MCP 서버를 쓰는 도구입니다. 이 도구는 자신이 직접 띄우는 opencode 서버 프로세스를 시작할 때, 그 프로세스의 `OPENCODE_CONFIG_CONTENT` 에 자기 MCP 항목(`mcp.browser`)을 얹습니다. 이미 환경변수에 JSON 이 있으면 그것을 읽어서 `mcp` 아래에 항목을 더하는 방식이라, 사용자가 쓰던 모델·로그인·다른 MCP 설정은 그대로 살아 있고 **사용자의 전역 설정 파일은 한 글자도 바뀌지 않습니다.** 서버에 넘겨야 하는 값은 같은 항목의 `environment` 로 전달합니다. 이 예제의 `launch.py` 는 그 패턴을 작게 줄인 것입니다. (해당 저장소의 `docs/architecture.md` 와 `bridge/src/runtime/mod.rs` 의 overlay 부분 참고)

- 어떤 프로그램이 opencode 를 **자식 프로세스로 띄울 때**, 자기 도구를 사용자 설정을 건드리지 않고 붙일 때
- CI 에서 일회성 MCP 서버(테스트용 목 서버)를 붙여서 에이전트를 돌릴 때
- "오늘만 이 MCP 를 켜 보고 싶다"처럼 설정 파일에 흔적을 남기고 싶지 않을 때

## 파일 구성

```
c3-config-content-overlay/
  README.md
  launch.py          OPENCODE_CONFIG_CONTENT 를 만들어 opencode 를 실행 (--print-config / --run / 기본 TUI)
  clock_server.py    도구 하나(current_time)만 가진 stdlib MCP 서버. 이번 실행에만 등록됨
  opencode.json      프로젝트 설정. username: project-user 만 있고 MCP 는 없음
  fake_llm.py        가짜 모델 서버. check.py 가 launch.py --run 을 모델 없이 재현할 때 쓴다
  check.py           자동 검증
```

## 따라 하기

아래 명령은 이 폴더에서 실행합니다. 평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 `-m opencode/big-pickle` 을 붙이세요.

PowerShell:
```powershell
cd examples\00-config\c3-config-content-overlay
python launch.py --print-config
python launch.py --run "current_time 도구로 지금 시각을 알려줘"
python launch.py                       # opencode TUI
```
Linux bash:
```bash
cd examples/00-config/c3-config-content-overlay
python3 launch.py --print-config
python3 launch.py --run "current_time 도구로 지금 시각을 알려줘"
python3 launch.py                      # opencode TUI
```

1. `--print-config`: 모델을 쓰지 않습니다. 덧씌우기 전후의 `username` 과 `mcp` 항목을 보여 줍니다.
2. `--run "프롬프트"`: `opencode run --auto` 로 프롬프트 하나를 실행합니다. 모델에게 시각을 묻고 `clock_current_time` 도구가 호출되는 것을 봅니다. (`-m provider/model` 로 모델을 지정할 수 있습니다.)
3. 인자 없이 실행하면 TUI 가 열립니다. 입력창에 "지금 몇 시야? 시계 도구를 써 줘" 라고 입력해 보세요. 이렇게 연 TUI 에서는 clock 도구를 쓸 수 있고, 그냥 `opencode` 로 연 TUI 에는 이 도구가 없습니다.
4. 비교: 같은 폴더에서 `opencode mcp list` 를 실행하면 clock 이 **없습니다.** `launch.py` 를 끝낸 뒤에도 파일에는 아무 흔적이 남지 않습니다. (`opencode.json` 은 그대로, `~/.config/opencode` 도 그대로)

Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`launch.py` 는 자기를 실행한 파이썬의 절대 경로를 MCP 명령에 적으므로 `python3` 로 실행해도 서버가 뜹니다.)

`--auto` 는 허용되지 않은 권한 요청을 자동 승인하는 옵션입니다. clock 서버는 읽기 전용 도구 하나뿐이지만, 같은 폴더에서 다른 작업을 시키는 용도로 `--run` 을 쓰지는 마세요.

## 기대 결과

`python launch.py --print-config` (opencode 1.19.5, Linux. 샌드박스 전역 설정을 쓴 출력이며 경로는 줄였습니다):

```
프로젝트 opencode.json 의 username : project-user
덧씌운 설정 후 username            : overlay-user
mcp 항목                           : clock
mcp.clock                          : {"type": "local", "command": ["/usr/bin/python3", ".../clock_server.py"], "enabled": true}
instructions                       : ['project-rules.md']
```

프로젝트의 `instructions` 는 그대로 남아 있고(덮어쓴 키만 바뀜), `username` 만 얹은 값으로 바뀝니다. 내 전역 설정에 MCP 가 있다면 `mcp 항목` 에 함께 나타납니다.

같은 폴더에서 `opencode mcp list` 를 덧씌우기 **없이** 실행했을 때와 `OPENCODE_CONFIG_CONTENT` 를 **얹고** 실행했을 때의 차이입니다. (전역 설정이 비어 있는 상태에서 확인한 출력이며 경로는 줄였습니다)

```
덧씌우기 없음                      덧씌우기 있음
┌  MCP Servers                     ┌  MCP Servers
▲  No MCP servers configured       ●  ✓ clock connected
                                   │      /usr/bin/python3 .../clock_server.py
```

`launch.py --run` 의 출력입니다. 진짜 모델 대신 `fake_llm.py`(정해진 대로 `clock_current_time` 을 호출하는 가짜 모델)를 붙여 확인한 결과이며, 모델 응답이 아니라 opencode 의 출력 형식을 보여 줍니다.

```
[launch] OPENCODE_CONFIG_CONTENT 를 얹어 실행: .../opencode run --auto ...

> build · echo
⚙ clock_current_time Unknown
DONE
```

`⚙ clock_current_time` 줄이 도구 호출 표시입니다. 가짜 모델에 도구 목록이 전달될 때 `clock_current_time` 이 들어 있고, 도구 결과로 `2026-11-17 01:30:12 (KST, UTC+0900)` 같은 형식의 문자열이 모델에게 돌아가는 것도 확인했습니다. 이때 `launch.py` 는 이미 환경변수에 있던 가짜 모델 설정을 지우지 않고 그 위에 clock 만 얹었습니다.
진짜 모델로 `python launch.py --run "..."` 를 실행했을 때의 응답은 모델에 따라 다릅니다. `python check.py --model` 이 소프트 검사로 한 번 시도합니다.

## 동작 원리

1. `launch.py` 가 `OPENCODE_CONFIG_CONTENT` 에 이미 JSON 이 있으면 읽어서 그 위에 얹고, 없으면 빈 객체에서 시작합니다. JSON 객체가 아니면 오류로 멈춥니다.
2. `username: overlay-user` 와 `mcp.clock`(`type: local`, `command: [파이썬 경로, clock_server.py 절대 경로]`, `enabled: true`)을 더합니다.
3. 만든 JSON 문자열을 **자식 프로세스의 환경변수로만** 넣어 `subprocess.run` 으로 opencode 를 실행합니다. 내 셸의 환경변수는 바뀌지 않습니다.
4. opencode 는 설정을 이렇게 쌓습니다: 전역 → `OPENCODE_CONFIG` → 프로젝트 `opencode.json` → `.opencode/opencode.json` → **`OPENCODE_CONFIG_CONTENT`**. 마지막 층이 이기므로 프로젝트 설정의 같은 키가 덮입니다. 배열(`instructions`)은 이어 붙고 객체(`mcp`)는 키 단위로 합쳐져서, 프로젝트 설정의 다른 값은 남습니다. (C1 참고)
5. 덧씌운 JSON 에는 "설정 파일의 위치"가 없어서 `{file:...}` 같은 상대 경로가 **실행 위치(cwd)** 기준이 됩니다. 그래서 `launch.py` 는 서버 경로를 절대 경로로 적습니다.
6. `clock_server.py` 는 줄바꿈으로 구분된 JSON-RPC 를 stdin 으로 받아 stdout 으로 답하는 표준 MCP(stdio)입니다. 규칙: **stdout 에는 MCP 메시지만** 쓰고 로그는 stderr 로 보냅니다.

## 직접 바꿔 보기

1. `launch.py` 의 `OVERLAY_USERNAME` 을 바꾸고 `--print-config` 를 다시 실행해 보세요. 프로젝트 `opencode.json` 의 `username` 을 지워도 결과가 같다는 것도 확인해 보세요. (덧씌운 값이 항상 이깁니다)
2. 미리 `OPENCODE_CONFIG_CONTENT` 를 설정하고 실행해 보세요. 기존 JSON 에 `instructions` 가 있으면 보존됩니다.
   PowerShell: `$env:OPENCODE_CONFIG_CONTENT = '{"instructions":["extra.md"]}'; python launch.py --print-config`
   bash: `OPENCODE_CONFIG_CONTENT='{"instructions":["extra.md"]}' python3 launch.py --print-config`
3. `build_overlay()` 에 `permission` 을 추가해 이번 실행에서만 `bash` 를 `ask` 로 바꿔 보세요. (C5 참고)
4. `--dir 다른폴더` 로 다른 프로젝트에서 같은 덧씌우기를 실행해 보세요.

## 주의할 점 / 문제 해결

- 덧씌우기는 **프로세스 단위**입니다. 이미 떠 있는 opencode 에는 적용되지 않고, 별도로 띄운 다른 opencode 에도 적용되지 않습니다.
- JSON 이 깨져 있으면 opencode 가 시작할 때 설정 오류로 멈춥니다. 직접 쓸 때는 셸 따옴표에 주의하세요. PowerShell 에서는 바깥을 작은따옴표, 안쪽 JSON 을 큰따옴표로 쓰는 것이 편합니다.
- `debug config` 는 `OPENCODE_CONFIG_CONTENT` 의 `{env:...}` 와 `{file:...}` 도 치환합니다. (C2 참고) 비밀 값을 이 환경변수에 직접 넣으면 같은 사용자의 다른 프로세스가 볼 수 있으니, 토큰은 `{env:NAME}` 으로 참조하세요.
- 덧씌우기가 전역 설정보다 우선하므로, 사용자가 전역에 켜 둔 MCP 를 같은 이름으로 정의하면 덮어쓰게 됩니다. 서버 이름이 겹치지 않게 짓는 편이 안전합니다.
- `.opencode/` 폴더가 없는 예제라 `@opencode-ai/plugin` 자동 설치는 일어나지 않습니다.
