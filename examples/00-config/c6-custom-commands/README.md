# C6 커스텀 명령: 내가 부르는 지시문

> 구성: opencode.json + `.opencode/command/*.md` + 비교용 스킬 1개 | 난이도: ★☆☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: 설정 (커스텀 명령)

## 무엇을 보여 주나

자주 다시 치는 지시문("계획대로 끝까지 진행해 줘. PR 단위로, 검사 통과 후 병합, ...")을 **명령**으로 저장해 두고 `/finish` 처럼 부르는 방법입니다.
정의 방법은 두 가지이고 결과는 같습니다.

- `.opencode/command/이름.md`: frontmatter(설명 등) + 본문이 곧 지시문
- `opencode.json` 의 `command` 키: `{"이름": {"template": "...", "description": "..."}}`

핵심은 **스킬과의 차이**입니다. 명령은 사용자가 부를 때만 그 글이 대화에 들어갑니다. 스킬은 이름과 description 이 **모든 요청**에 들어 있고, 부를지는 모델이 정합니다. 이 예제는 같은 지시문을 명령(`/finish`)과 스킬(`finish-plan`)로 한 프로젝트에 같이 두고, 가짜 모델이 받은 요청을 글자 수까지 비교합니다. (`python demo.py`)

## 실무에서는

- "계획대로 끝까지 진행해 줘. PR 단위로, 검사 통과 후 병합, 문서는 후속 커밋, 실행한 명령과 결과는 표로" 같은 문단을 매번 붙여 넣는 대신 `/finish` 한 단어로 부릅니다. 저장소에 커밋해 두면 팀원 모두 같은 문장을 씁니다.
- `/review src/app.py` 처럼 **인자**를 받는 명령은 리뷰 기준을 고정하고 대상만 바꿉니다. (`$ARGUMENTS`)
- 읽기 전용 점검(`/status`)에는 `agent: plan` 을 붙여 수정 권한이 없는 에이전트로 돌립니다.
- 반대로 "이런 일을 하라는 말이 나오면 알아서 적용"되길 원하면 명령이 아니라 스킬입니다. 아래 표를 보세요.

## 파일 구성

```
c6-custom-commands/
  README.md
  opencode.json                     command 키로 정의한 /status (agent: plan)
  .opencode/command/finish.md       /finish: 인자 없는 지시문 (frontmatter description + 본문)
  .opencode/command/review.md       /review: $ARGUMENTS 를 쓰는 지시문
  .opencode/skills/finish-plan/     비교용. /finish 와 본문이 글자 하나 다르지 않은 스킬
  src/app.py                        /review 연습용 작은 파일 (함수 두 개)
  lab.py  fake_llm.py               가짜 모델로 모델이 받은 요청을 읽는 도우미
  demo.py                           명령과 스킬이 모델에게 무엇을 보내는지 비교해서 출력
  check.py                          자동 검증
```

`opencode.json` 의 `command` 키 (같은 일을 `.md` 대신 JSON 으로 쓴 형태):

```json
{
  "command": {
    "status": {
      "description": "지금 저장소 상태를 세 줄로 요약",
      "agent": "plan",
      "template": "git status 와 git log -5 --oneline 을 읽고, 지금 어떤 상태인지 세 줄로 요약해 줘. 파일은 고치지 않는다."
    }
  }
}
```

`.md` 에서는 frontmatter 가 `description`·`agent` 같은 키가 되고 **본문이 `template`** 이 됩니다. `opencode debug config` 의 `command` 항목으로 확인할 수 있습니다.

## 따라 하기

1. 모델 없이 opencode 가 명령을 읽었는지 봅니다. 이 폴더에서 실행합니다.

   PowerShell:
   ```powershell
   cd examples\00-config\c6-custom-commands
   opencode debug config
   ```
   Linux bash:
   ```bash
   cd examples/00-config/c6-custom-commands
   opencode debug config
   ```
   JSON 의 `command` 아래에 `status`(opencode.json), `finish`, `review`(.md) 세 개가 있어야 합니다.

2. **모델 없이** 명령과 스킬의 차이를 봅니다. 가짜 모델이 받은 요청을 읽어 옵니다. 실제 `~/.config/opencode` 는 건드리지 않습니다.

   ```
   python demo.py
   ```
   (Linux 에서 `python` 이 없으면 `python3 demo.py`)

3. 평소 쓰는 모델로 명령을 실행합니다. 모델 설정이 없으면 `-m opencode/big-pickle` 을 붙이세요.

   ```
   opencode run --command finish
   opencode run --command review "src/app.py"
   opencode run --command review "src/my app.py"
   ```
   마지막 줄은 공백이 있는 인자입니다. PowerShell 과 bash 모두 따옴표로 묶어 하나의 인자로 넘깁니다. (`src/my app.py` 라는 파일은 예제에 없습니다. 인자가 따옴표를 달고 하나로 들어가는 모양만 보는 줄이라, 실제 모델로 실행하면 모델이 파일이 없다고 답할 수 있습니다. `src/app.py` 는 있습니다.)

4. TUI 에서는 입력창에 `/finish` 처럼 슬래시와 이름을 입력하는 것이 opencode 의 방식입니다. **TUI 는 이 예제에서 직접 확인하지 못했습니다(미검증).** 아래 표의 동작은 모두 `opencode run --command` 로 확인한 것입니다.

## 기대 결과

`python demo.py` 의 실제 출력 전체입니다. (opencode 1.19.5, Linux, 가짜 모델. 시스템 프롬프트 전체 길이(9938자)는 설치된 opencode 와 환경에 따라 달라질 수 있습니다.)

```
[1] 아무것도 부르지 않았을 때 모델이 받은 요청
    시스템 프롬프트 전체: 9938자
    스킬 finish-plan 항목: 이름+설명 103자 (파일 경로 <location> 까지 포함하면 308자, 경로는 설치 위치마다 다름)
      <- 이 항목은 어떤 요청에든 들어 있다
    스킬 본문 길이: 280자  요청에 본문이 있는가: False
    명령 /finish 본문 길이: 280자  요청에 본문이 있는가: False
    'PR 단위로 나눠서' 구절이 요청에 있는가: False  (스킬 항목에도 없음)

[2] opencode run --command finish 로 불렀을 때 모델이 받은 사용자 메시지
    사용자 메시지 1개, 길이 280자, 명령 본문과 같은가: True
    --- 받은 내용 ---
    계획대로 끝까지 진행해 줘. 중간에 멈추고 묻지 말고, 아래 규칙을 지켜 줘.
    
    1. 작업은 PR 단위로 나눠서 진행한다. PR 하나는 한 가지 목적만 담는다.
    2. PR마다 검사(테스트, 린트)를 돌리고, 모두 통과한 뒤에만 병합한다. 실패하면 원인을 고치고 다시 돌린다. 검사를 건너뛰거나 끄지 않는다.
    3. 문서는 코드 PR에 섞지 말고 후속 커밋으로 올린다.
    4. 끝나면 실행한 명령과 결과를 표로 보고한다. 열은 `단계 | 명령 | 결과` 로 한다. 실행하지 않은 것은 "미실행"으로 적는다.

[3] 스킬은 모델이 skill 도구로 불러야 본문이 들어온다 (가짜 모델이 부른 것으로 흉내)
    두 번째 요청의 도구 결과에 본문이 있는가: True
```

| | 명령 (`/finish`) | 스킬 (`finish-plan`) |
|---|---|---|
| 부르기 전 모델 요청에 있는 것 | **아무것도 없음** (이름·설명·본문 모두) | 이름+description 103자 (+ 파일 경로) |
| 본문(280자)이 들어오는 때 | 사용자가 부를 때, **사용자 메시지**로 | 모델이 `skill` 도구를 부를 때, **도구 결과**로 |
| 부를지 정하는 쪽 | 사용자 | 모델 (description 을 보고) |
| 인자 | `$ARGUMENTS`, `$1` `$2` | 없음 (대화 맥락에서 읽음) |

이 예제의 지시문처럼 짧은(280자) 글에서는 스킬의 목록 항목(103자)이 본문과 같은 자릿수라서 스킬로 둬도 이득이 크지 않습니다. 스킬은 본문이 길고 **가끔만** 필요할 때, 명령은 **내가 정확히 그 순간에 부르고 싶을 때** 맞습니다.

### 인자 동작 (`--command args ...`, 본문: `ALL=[$ARGUMENTS] ONE=[$1] TWO=[$2] THREE=[$3]`)

| 넘긴 인자 | 모델이 받은 사용자 메시지 |
|---|---|
| `x` | `ALL=[x] ONE=[x] TWO=[] THREE=[]` |
| `"a b"` `c` (두 인자) | `ALL=["a b" c] ONE=[a b] TWO=[c] THREE=[]` |
| `a` `b` `c` `d` | `ALL=[a b c d] ONE=[a] TWO=[b] THREE=[c d]` |
| `one "two three" four` (한 인자 안에 큰따옴표) | `ALL=["one \"two three\" four"] ONE=[one \] TWO=[two] THREE=[three\  four]` |

- 공백이 있는 인자는 `$ARGUMENTS` 에 **따옴표가 붙어** 들어갑니다. `$1` 은 따옴표를 뗀 값입니다.
- 없는 위치(`$2`, `$3`)는 빈 문자열입니다.
- 인자가 `$3` 보다 많으면 **가장 큰 번호의 자리표시자가 나머지를 모두** 받습니다(`THREE=[c d]`).
- 인자 안에 큰따옴표가 들어가면 위 마지막 줄처럼 깨진 모양이 됩니다. 이 모양에 기대지 말고, 따옴표가 필요한 값은 파일로 넘기세요.
- 본문에 `$ARGUMENTS` 가 **없는데** 인자를 주면 본문 뒤에 빈 줄을 두고 인자가 덧붙습니다: `...적는다.\n\n"issue 12 부터"`.

### frontmatter / JSON 키 (확인한 것만)

| 키 | 확인한 동작 |
|---|---|
| `description` | `debug config` 의 `command` 에 보임. 모델 요청에는 들어가지 않음(위 표). TUI 의 `/` 목록에 보이는지는 미검증 |
| `agent` | `agent: plan` → 실행 헤더가 `> plan · ...`, 사용자 메시지 끝에 plan 모드 안내(`# Plan Mode - System Reminder`)가 붙음 |
| `model` | `model: fake/other` → 모델 요청의 model 이 `other`. `-m` 으로 준 모델보다 우선. 가리키는 모델이 설정에 없으면 모델 호출 없이 실패(종료 코드 비0) |
| `subtask` | `subtask: true` → 하위 에이전트 작업으로 실행됨(실행 기록에 `Build Agent` 줄, 그 작업의 도구 목록에 `task` 없음) |

위 네 개 밖의 키는 시험하지 않았으므로 적지 않습니다.

### 그 밖에 확인한 것

- `.opencode/commands/` (복수형) 폴더의 `.md` 도 읽힙니다.
- 같은 이름을 `.opencode/command/dup.md` 와 `opencode.json` 의 `command.dup` 에 모두 정의하면 `.md` 가 이깁니다(`debug config` 로 확인. 설정 층 순서는 [C1](../c1-scope-merge/README.md)과 같음).
- **없는 명령 이름**: `opencode run --command nosuch hi` → 종료 코드 1, 모델 호출 없음. 메시지는 `UnknownError ... Unexpected server error. Check server logs for details.` 뿐이라 오타라는 말이 없습니다. `--print-logs --log-level ERROR` 로 봐도 스택(`SessionPrompt.command`)만 나오고 이름은 안 나옵니다. 오타가 의심되면 `opencode debug config` 로 이름을 확인하세요.

## 동작 원리

1. 시작할 때 opencode 가 `.opencode/command/*.md`(와 `commands/`)를 읽어 `opencode.json` 의 `command` 와 함께 하나의 명령 표로 합칩니다. `.md` 의 본문은 `template` 이 됩니다.
2. 명령을 부르면 `template` 의 `$ARGUMENTS`, `$1`... 을 인자로 바꾼 글이 **사용자 메시지 한 개**로 대화에 들어갑니다. 시스템 프롬프트에는 아무것도 추가되지 않습니다.
3. 그래서 명령은 부르기 전에는 **토큰을 쓰지 않고**, 불렀을 때 한 번 대화 기록에 남습니다(이후 요청에도 대화 기록으로 계속 실려 가는 것을 확인했습니다).
4. 스킬은 반대입니다. 이름·description 이 매 요청의 시스템 프롬프트(`<available_skills>`)에 있고, 모델이 필요하다고 판단하면 `skill` 도구로 본문을 불러옵니다.

| | 명령 | 스킬 | 에이전트 ([C8](../c8-agents/README.md)) |
|---|---|---|---|
| 누가 시작하나 | 사용자 | 모델 | 사용자(`--agent`)나 모델(하위 에이전트) |
| 들어가는 곳 | 사용자 메시지 | 도구 결과 | 시스템 프롬프트와 도구·권한 |
| 평소 비용 | 없음 | 이름+description | 고른 에이전트 외에는 거의 없음(단 subagent 의 description 은 모든 요청의 `task` 도구 설명에 들어감, [C8](../c8-agents/README.md)) |

## 직접 바꿔 보기

1. `review.md` 의 `$ARGUMENTS` 를 `$1` 로 바꾸고 `opencode run --command review "src/my app.py"` 를 다시 실행해 보세요. 공백 있는 인자가 어떻게 달라지는지 `check.py` 의 인자 표와 비교합니다.
2. `review.md` frontmatter 에 `agent: plan` 을 추가하고, 실행 헤더가 `plan` 으로 바뀌는지 보세요.
3. `.opencode/commands/` 폴더를 만들어 `hello.md` 를 넣고 `opencode debug config` 에 나타나는지 보세요.
4. `finish.md` 와 `finish-plan` 스킬의 본문을 일부러 5배로 늘린 뒤 `python demo.py` 를 다시 돌려, 스킬의 항목(103자)은 그대로인데 명령은 부르지 않는 한 비용이 0 이라는 점이 어떻게 보이는지 확인하세요.

## 주의할 점

- `finish.md` 와 `finish-plan/SKILL.md` 는 비교를 위해 본문을 똑같이 둔 것입니다. 실제 프로젝트에서는 둘 중 하나만 두세요. 둘 다 있으면 모델이 스킬을 불러 같은 지시를 두 번 받을 수 있습니다.
- 인자 안의 큰따옴표는 깨집니다(위 표). 긴 입력은 인자 대신 파일 경로를 넘기고 본문에서 읽게 하세요.
- 명령은 모델에게 보내는 **글**일 뿐이라 모델이 어길 수 있습니다. 반드시 지켜야 하는 제약은 [C5 권한](../c5-permissions/README.md)이나 에이전트 권한으로 거세요.
- 명령 이름을 틀리면 이유 없이 `UnknownError` 가 나옵니다(위). `debug config` 로 이름을 확인하세요.
- Linux 에서 `python` 명령이 없으면 `python3` 로 바꾸세요. (`check.py` 는 어느 쪽이든 동작합니다.)
- 이 예제의 `.opencode/` 가 있는 폴더에서 opencode 를 시작하면 `@opencode-ai/plugin` 을 npm 에서 설치하려고 시도하고 `.opencode/` 안에 `package.json`, `node_modules/` 가 생길 수 있습니다(모두 git 에서 제외). 플러그인 파일이 없는 이 예제에서는 레지스트리에 닿지 않아도 눈에 띄는 멈춤은 없었습니다. 자세한 내용은 [S1a README](../../01-skills/s1a-commit-message/README.md#주의할-점--문제-해결) 를 보세요.
- **Windows**: Windows(PowerShell 5.1, opencode 1.19.5)에서 이 예제의 `check.py` 를 실행해 통과했습니다(실패 0). `opencode run --command` 를 손으로 따라 하는 과정과 실제 모델은 Windows 에서 확인하지 않았습니다.
