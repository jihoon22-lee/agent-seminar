# C5 선언형 권한: `permission`

> 구성: opencode.json + 실험용 sandbox | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, git | 슬라이드: 설정 (권한)

## 무엇을 보여 주나

`opencode.json` 의 `permission` 키로 에이전트가 **무엇을 물어보고(ask), 바로 하고(allow), 못 하게(deny)** 할지 코드 없이 선언합니다.
`edit`(파일 수정), `bash`(명령어 패턴별 규칙), `external_directory`(프로젝트 밖 경로)를 다룹니다.
핵심 규칙은 하나입니다. 규칙은 **적은 순서대로 평가되고 마지막으로 맞는 규칙이 이깁니다.** 그래서 `"*"` 처럼 넓은 규칙을 **먼저**, 구체적인 예외를 **뒤에** 적어야 합니다.

## 실무에서는

- 저장소의 `opencode.json` 에 "읽기성 git 명령은 허용, `rm`·배포 명령은 거부, 나머지는 물어보기"를 넣어 두면 팀원 모두 같은 안전선에서 시작합니다.
- 파일 수정은 `ask` 로 두어 에이전트가 쓰는 diff 를 사람이 눈으로 확인하게 합니다.
- 프로젝트 밖(홈 폴더, 다른 저장소)을 에이전트가 건드리지 못하게 `external_directory: deny` 를 겁니다.
- CI 에서 `opencode run --auto` 로 돌릴 때, `--auto` 가 승인해 주는 범위를 `deny` 로 미리 좁혀 둡니다.

## 파일 구성

```
c5-permissions/
  README.md
  opencode.json   permission 설정. 모델 설정은 없음
  prepare.py      실험용 sandbox/ (git 저장소 + notes.txt + victim.txt)와 프로젝트 밖 파일을 만든다
  fake_llm.py     가짜 모델 서버 (check.py 가 run 전체 경로를 모델 없이 재현할 때 사용)
  check.py        자동 검증
  sandbox/        prepare.py 가 만드는 폴더 (git 에 올라가지 않음)
```

`opencode.json` 의 핵심:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "edit": "ask",
    "bash": {
      "*": "ask",
      "git status*": "allow",
      "rm *": "deny"
    },
    "external_directory": "deny"
  }
}
```

| 키 | 값 | 의미 |
|---|---|---|
| `edit` | `"ask"` | 파일 수정 전에 사람에게 묻는다 |
| `bash` | `"*": "ask"` | 모든 명령은 기본적으로 묻는다 (가장 먼저 적은 넓은 규칙) |
| | `"git status*": "allow"` | `git status` 로 시작하는 명령은 묻지 않고 실행 |
| | `"rm *": "deny"` | `rm ` 으로 시작하는 명령은 아예 거부 |
| `external_directory` | `"deny"` | 프로젝트 폴더 밖의 파일 접근 거부 |

## 따라 하기

1. 실험용 폴더를 만듭니다. (다시 실행해도 안전합니다. sandbox 를 지우고 새로 만듭니다.)

   PowerShell:
   ```powershell
   cd examples\00-config\c5-permissions
   python prepare.py
   cd sandbox
   ```
   Linux bash:
   ```bash
   cd examples/00-config/c5-permissions
   python3 prepare.py
   cd sandbox
   ```

2. **모델 없이** 규칙 목록을 봅니다. `opencode debug agent build` 가 에이전트가 쓰는 최종 규칙을 순서대로 보여 줍니다. 맨 앞의 `*` allow 가 opencode 의 기본값이고, 내 규칙이 그 뒤에 쌓입니다.

   ```
   opencode debug agent build
   ```
   JSON 의 `permission` 배열에서 `"permission": "bash"` 항목 세 개가 `*` → `git status*` → `rm *` 순서로 있는지 확인하세요.

3. **모델 없이** 규칙을 실제로 적용해 봅니다. `--tool` 과 `--params` 를 쓰면 모델을 거치지 않고 그 에이전트의 권한 규칙으로 도구를 직접 실행합니다. 이 방식으로는 `ask` 가 자동 승인되므로 allow 와 ask 는 구분되지 않지만, **deny 와 평가 순서**는 정확히 확인할 수 있습니다. 반드시 `sandbox` 폴더에서 실행하세요. (`--params` 는 JSON 이나 JS 객체 표기를 받습니다. 작은따옴표를 쓰면 PowerShell 과 bash 에서 같은 모양으로 쓸 수 있습니다.)

   ```
   opencode debug agent build --tool bash --params "{ command: 'git status', description: 'x' }"
   opencode debug agent build --tool bash --params "{ command: 'rm victim.txt', description: 'x' }"
   opencode debug agent build --tool bash --params "{ command: 'echo x && rm victim.txt', description: 'x' }"
   opencode debug agent build --tool bash --params "{ command: 'git rm -f victim.txt', description: 'x' }"
   ```
   `git rm` 은 `rm *` 에 걸리지 않습니다. sandbox 의 `victim.txt` 는 git 에 올라가 있으므로 이 명령은 **실제로 지워 버립니다.** 네 번째 줄은 결과를 이해하고 나서 실행하고, 지워졌다면 `python prepare.py` 를 다시 실행하세요.

4. **순서를 뒤집어 봅니다.** `opencode.json` 의 `bash` 를 아래처럼 바꾸고 3번의 명령을 다시 실행해 보세요. (실험이 끝나면 원래대로 되돌립니다.)

   ```json
   "bash": { "echo order*": "allow", "*": "deny" }
   ```
   `*` 가 마지막이 되어 모든 명령이 deny 입니다. opencode 는 이 경우 `bash` 도구 자체를 끄고 `Tool bash is disabled for agent build` 라고 알려 줍니다. 두 줄의 순서를 바꿔 `{ "*": "deny", "echo order*": "allow" }` 로 하면 `echo order-test` 만 실행되고 나머지는 거부됩니다.

5. 평소 쓰는 모델로 `opencode` 를 열고 아래 프롬프트를 차례로 입력합니다. 모델 설정이 없다면 `opencode -m opencode/big-pickle` 로 시작하세요. 승인 창이 어떻게 보이는지는 TUI 에서 직접 확인해야 합니다.

   | 프롬프트 | 기대 동작 |
   |---|---|
   | `git status 를 실행해 줘` | 묻지 않고 바로 실행 (`git status*` allow) |
   | `ls 를 실행해 줘` | 승인 창이 뜸 (`*` ask) |
   | `victim.txt 를 rm 으로 지워 줘` | 승인 창 없이 거부됨 (`rm *` deny) |
   | `notes.txt 끝에 한 줄을 추가해 줘` | 수정 승인 창이 뜸 (`edit` ask) |
   | `<prepare.py 가 알려 준 프로젝트 밖 파일 경로> 를 읽어 줘` | 거부됨 (`external_directory` deny) |

6. 비대화형 실행도 해 봅니다. `--auto` 는 **명시적으로 deny 되지 않은** 권한 요청을 자동 승인합니다.

   ```
   opencode run --auto "bash 도구로 정확히 'echo ask-demo > ask-marker.txt' 를 실행해 줘"
   opencode run --auto "bash 도구로 정확히 'rm victim.txt' 를 실행해 줘"
   ```
   첫 명령은 `*` ask 에 해당하지만 `--auto` 가 승인하므로 `ask-marker.txt` 가 만들어지고, 두 번째는 `rm *` deny 라서 막혀 `victim.txt` 가 남아야 합니다. 같은 프롬프트에서 `--auto` 를 빼면 첫 명령도 거절됩니다. 모델의 응답 속도와 도구 선택에 따라 결과가 달라질 수 있습니다.

## 기대 결과

3번의 직접 실행 결과입니다. (opencode 1.19.5, Linux, 모델 없음. 오류 메시지는 길어서 앞부분만 적었습니다.)

```
$ opencode debug agent build --tool bash --params "{ command: 'git status', description: 'x' }"
  -> 종료 코드 0, 결과 JSON 의 output: "On branch master\nnothing to commit, working tree clean\n"

$ opencode debug agent build --tool bash --params "{ command: 'rm victim.txt', description: 'x' }"
  -> 종료 코드 1
     Error: Unexpected error
     The user has specified a rule which prevents you from using this specific tool call.
     Here are some of the relevant rules [{"permission":"*","action":"allow","pattern":"*"}, ... ,
     {"permission":"bash","pattern":"*","action":"ask"},{"permission":"bash","pattern":"git status*","action":"allow"},
     {"permission":"bash","pattern":"rm *","action":"deny"}, ...]

$ ... command: 'echo x && rm victim.txt'   -> 같은 거부 (복합 명령은 부분별로 평가되어 rm 부분이 deny)
$ ... command: 'git rm -f victim.txt'      -> 실행됨. output: "rm 'victim.txt'\n"  (rm * 패턴에 걸리지 않음!)
```

거부 메시지가 현재 적용 중인 **규칙 목록 전체**를 보여 주므로, 왜 막혔는지 순서까지 그대로 읽을 수 있습니다.

그 밖에 같은 방식으로 확인한 결과입니다.

| 설정 | 실행한 도구 | 결과 |
|---|---|---|
| 기본 설정 | `bash` `echo hello` (`*` ask) | 실행됨 (이 호출에서는 ask 가 자동 승인) |
| 기본 설정 | `read` 프로젝트 밖 파일 | 거부 (`external_directory` deny) |
| 기본 설정 | `read` 프로젝트 안 파일 | 실행됨 |
| `bash: { "echo order*": "allow", "*": "deny" }` | `bash` `echo order-test` | `Tool bash is disabled for agent build` |
| `bash: { "*": "deny", "echo order*": "allow" }` | `bash` `echo order-test` | 실행됨 |
| 〃 | `bash` `echo other` | 거부 |
| `edit: "deny"` | `edit` | `Tool edit is disabled for agent build` |
| 설정 없음 | `plan` 에이전트의 `edit` | 거부 (plan 은 기본이 읽기 전용) |
| `edit: "ask"` | `plan` 에이전트의 `edit` | **실행됨** (plan 의 기본 deny 가 사라지고 ask 로 바뀜) |

**`opencode run` 전체 경로** (가짜 모델 `fake_llm.py` 가 정해진 도구 호출을 흉내 내도록 해서 확인한 결과입니다. 진짜 모델이 아니라서 매번 같습니다. 모델 없이는 승인 창을 띄울 사람이 없으므로 `--auto` 없는 `run` 에서 `ask` 는 거절됩니다.)

| 설정 | 가짜 모델의 도구 호출 | `--auto` | 결과 |
|---|---|---|---|
| 기본(예제 설정) | `bash` `echo ask-demo > ask-marker.txt` (`*` ask) | 없음 | `auto-rejecting` 으로 거절, 파일 안 생김 |
| 〃 | 〃 | 있음 | 자동 승인, 파일 생김 |
| 〃 | `bash` `git status` (allow) | 없음 | 바로 실행, 결과가 모델에게 돌아감 |
| 〃 | `bash` `rm victim.txt` (deny) | 있음 | 거부 사유가 모델에게 돌아가고 파일이 남음 |
| 〃 | `read` 프로젝트 밖 파일 (`external_directory` deny) | 있음 | 파일 내용이 모델에게 가지 않음 |
| 〃 | `edit` `notes.txt` (ask) | 없음 / 있음 | 거절·파일 그대로 / 승인·파일 바뀜 |
| `bash: { "git status*": "allow", "*": "ask" }` | `bash` `git status` | 없음 | `*` ask 가 마지막이라 **거절** (마지막 일치가 이김) |
| `bash: { "echo order*": "allow", "*": "deny" }` | (모델에게 가는 도구 목록) | - | `bash` 가 목록에서 사라짐 |

6번 단계처럼 실제 모델로 돌리는 경우 결과는 모델의 응답에 좌우됩니다. `python check.py --model` 이 소프트 검사로 한 번 시도하지만, 무료 모델이 혼잡하면 시간 초과로 끝날 수 있습니다.

## 동작 원리

1. 설정의 `permission` 은 여러 층(전역 → `OPENCODE_CONFIG` → 프로젝트 → `.opencode` → `OPENCODE_CONFIG_CONTENT`)이 키 단위로 병합된 뒤, 에이전트별 규칙 **목록**으로 펼쳐집니다. `opencode debug agent build` 가 그 목록을 보여 줍니다. (C1 참고)
2. 목록의 맨 앞에는 opencode 의 기본 규칙이 있습니다. 모든 도구 `* allow`, `.env` 파일 읽기는 `ask`, `external_directory` 는 `ask`(단 opencode 자신의 임시·도구 출력 폴더는 `allow`) 등입니다. 그 뒤에 내 설정이 키 순서대로 쌓입니다. 그래서 `permission` 을 아무것도 적지 않으면 `bash` 와 `edit` 은 **기본 allow** 입니다.
3. 객체 안의 키 순서가 규칙 순서입니다. 층이 여러 개일 때는 낮은 층의 키가 먼저, 높은 층에서 새로 나온 키가 뒤에 옵니다. 같은 키를 높은 층에서 다시 적으면 그 키의 값은 바뀌고 **위치는 처음 나온 자리에 남습니다.**
   - 예: 팀 파일에 `"git status*": "allow"`, 프로젝트 파일에 `"*": "ask"` 가 있으면 목록은 `git status* allow` → `* ask` 입니다(목록 순서는 확인함). 마지막 규칙이 이기므로 `git status` 도 ask 가 됩니다(`--auto` 없는 `run` 에서 거절되는 것을 확인했습니다).
4. 도구가 실행되기 직전 opencode 가 목록을 평가합니다. `bash` 는 명령 문자열을 패턴(`*` 는 임의 문자열)과 비교하고, `&&` 로 이은 복합 명령은 부분별로 평가합니다(둘 중 하나라도 deny 면 거부). 결과가 `allow` 면 실행, `ask` 면 사람에게 승인을 요청, `deny` 면 위 기대 결과의 오류가 모델에게 돌아갑니다.
   - 도구의 **모든 사용**이 deny 이면(`edit: "deny"`, 또는 마지막 `*` 규칙이 deny) 오류가 아니라 도구가 아예 꺼져서 모델 목록에서 사라집니다(`Tool ... is disabled for agent ...`).
5. `opencode run --auto` 는 `ask` 를 자동으로 승인합니다. 그러나 `deny` 는 승인 대상이 아니므로 그대로 막힙니다. 그래서 `--auto` 를 쓸 때일수록 `deny` 가 안전장치입니다. (위 기대 결과의 `opencode run` 표에서 확인했습니다. `--auto` 없이는 `ask` 가 `auto-rejecting` 으로 거절됩니다.)
6. 주의할 부작용: 읽기 전용 `plan` 에이전트의 기본 규칙은 `edit * deny` 인데, 내 `"edit": "ask"` 는 그 뒤에 쌓이므로 마지막 `edit *` 규칙이 `ask` 가 됩니다. 위 표처럼 `plan` 에이전트도 수정을 **시도할 수 있게** 되고(사람이 승인하면 실행), 기본 읽기 전용 성격이 사라집니다. `edit` 을 전역으로 바꿀 때는 `opencode debug agent plan` 도 확인하세요.

## 선언형 권한 vs 플러그인 가드

같은 "위험한 명령 막기"를 두 방식으로 할 수 있습니다. 플러그인 쪽 예제는 `examples/03-plugins/p2-dangerous-command-guard` 를 보세요.

| | 선언형 `permission` (이 예제) | 플러그인 가드 (`tool.execute.before`) |
|---|---|---|
| 만드는 법 | `opencode.json` 몇 줄 | JS/TS 플러그인 코드 |
| 표현력 | 명령 문자열 **패턴**(`rm *`)과 allow/ask/deny | 코드로 무엇이든 판단: 인자 파싱, 경로 검사, 외부 정책 조회, 로그 기록 |
| 막았을 때 | 사람에게 묻거나 거부 (ask 가 있음) | 예외를 던져 막고, 메시지를 직접 정함 |
| 우회 | `&&` 등으로 이은 복합 명령은 부분별로 나뉘어 각각 평가되므로 `cd x && rm y` 의 `rm y` 도 `rm *` 에 걸린다(위 3번 단계에서 확인). 하지만 `sh -c "rm y"` 처럼 다른 명령 안에 감싼 변형은 패턴 설계에 달림 | 코드로 명령을 해석해 더 촘촘히 막을 수 있지만 그만큼 코드를 관리해야 함 |
| 위험 | 규칙 순서 실수 | 플러그인 버그, 로드 실패(`--pure` 로 꺼짐) |
| 적합한 때 | 팀 공통 기본 안전선, 사람이 승인하는 흐름 | 기본 규칙으로 표현 못 하는 조건, 감사 기록, 정책 서버 연동 |

권장: 기본 안전선은 선언형으로 두고(코드 없이 읽기 쉬움), 패턴으로 표현할 수 없는 조건만 플러그인으로 보강합니다. 둘은 함께 쓸 수 있습니다.

## 직접 바꿔 보기

1. `bash` 에 `"git rm *": "deny"` 를 `"rm *"` 뒤에 추가하고, 3번 단계의 `git rm -f victim.txt` 가 이제 거부되는지 확인하세요. (먼저 `python prepare.py` 로 sandbox 를 되돌립니다)
2. `edit` 을 객체로 바꿔 보세요: `"edit": { "*": "ask", "notes.txt": "allow" }`. `debug agent build` 에서 `edit` 규칙이 두 개로 나뉘는지, 순서가 어떤지 확인하세요.
3. `external_directory` 를 `ask` 로 바꾸고 프로젝트 밖 파일을 읽게 해서 승인 창이 뜨는지 보세요.
4. 4번 단계(순서 뒤집기)의 두 순서를 `debug agent build` 의 규칙 목록에서도 비교해 보세요. 목록 순서와 실행 결과가 어떻게 대응하는지 보입니다.

## 주의할 점 / 문제 해결

- **순서가 전부입니다.** 구체적인 예외를 `*` 보다 먼저 적으면 `*` 가 이겨 버립니다. 규칙이 의도대로인지는 `opencode debug agent build` 로 순서와 함께 확인하세요.
- `--auto` 는 `ask` 를 모두 승인합니다. 프로젝트에서 신뢰할 수 없는 프롬프트를 처리한다면 `ask` 가 아니라 `deny` 로 막으세요.
- 규칙은 **문자열 패턴**입니다. 명령의 의미를 이해하지 못하므로 `rm *` 를 막아도 `git rm -f 파일`(실제로 지워졌음), `unlink`, `find -delete`, 스크립트 안의 삭제는 막지 못합니다. 위험한 동작은 허용 목록(`"*": "deny"` 로 시작해 필요한 것만 allow) 방식이 더 안전합니다.
- 프로젝트 밖으로의 접근을 막은 상태에서도 opencode 가 자기 임시 폴더나 도구 출력 폴더를 읽는 것은 기본 allow 로 유지됩니다.
- Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (이 예제는 MCP 서버를 쓰지 않아 `opencode.json` 은 그대로 둡니다.)
- `sandbox/` 와 프로젝트 밖 파일(`<임시폴더>/c5-outside/note.txt`)은 실험용입니다. 실험 후 `sandbox/` 폴더를 지워도 됩니다.
