# C8 에이전트 정의: 역할마다 다른 권한

> 구성: `.opencode/agent/*.md` + opencode.json 의 `agent` 키 + 실험용 sandbox | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, git | 슬라이드: 설정 (에이전트)

## 무엇을 보여 주나

에이전트는 **프롬프트 + 권한 + (선택) 모델**을 한 묶음으로 이름 붙인 것입니다. `opencode --agent reviewer` 처럼 고르면 그 역할로 시작합니다. 정의하는 방법은 두 가지이고 결과는 같습니다.

- `.opencode/agent/이름.md`: frontmatter(`description`, `mode`, `permission`) + **본문이 시스템 프롬프트**
- `opencode.json` 의 `agent` 키: `{"이름": {"description", "mode", "prompt", "permission"}}`

이 예제에는 세 에이전트가 있습니다.

| 이름 | 정의한 곳 | mode | 하는 일 |
|---|---|---|---|
| `reviewer` | `.opencode/agent/reviewer.md` | primary | 읽기 전용 리뷰어. `edit`·`bash`·`task` deny |
| `docs` | `opencode.json` 의 `agent.docs` | primary | `docs/**` 만 고칠 수 있는 문서 작성자 (경로별 edit 권한) |
| `researcher` | `.opencode/agent/researcher.md` | subagent | 다른 에이전트가 `task` 도구로 부르는 읽기 전용 조사원 |

핵심 사실 하나: **`permission` 에서 통째로 deny 한 도구는 모델이 받는 도구 목록에서 아예 빠집니다.** 모델은 "금지된 도구를 시도했다가 거절당하는" 것이 아니라 그런 도구가 있는지도 모릅니다.

## 실무에서는

- 코드 리뷰만 맡길 때 `--agent reviewer` 로 시작하면, 프롬프트에 "고치지 마"라고 쓰는 것과 달리 **고칠 수단 자체가 없습니다.**
- 문서 담당 에이전트가 코드를 건드리지 못하게 `docs/**` 에만 쓰기를 열어 둡니다.
- 팀 저장소에 `.opencode/agent/` 를 커밋해 두면 모두 같은 역할 정의를 씁니다.
- 큰 조사를 다른 대화로 넘기고 요약만 받고 싶을 때 `subagent` 를 둡니다. 기본 `build` 에이전트가 필요하면 알아서 `task` 로 부릅니다.

## 파일 구성

```
c8-agents/
  README.md
  opencode.json                      agent.docs (JSON 형태의 정의)
  .opencode/agent/reviewer.md        읽기 전용 리뷰어 (primary)
  .opencode/agent/researcher.md      읽기 전용 조사원 (subagent)
  prepare.py                         sandbox/ 생성 (자체 git 저장소 + docs/guide.md + src/calc.py)
  lab.py  fake_llm.py                가짜 모델로 모델이 받은 요청을 읽는 도우미
  check.py                           자동 검증
  sandbox/                           prepare.py 가 만드는 폴더 (git 에 올라가지 않음)
```

`reviewer.md`:

```markdown
---
description: 읽기 전용 코드 리뷰어. 파일을 고치지 않고 명령도 실행하지 않는다
mode: primary
permission:
  edit: deny
  bash: deny
  task: deny
---
당신은 코드 리뷰어입니다. 파일을 읽기만 하고 절대 고치지 않습니다.
(... 본문이 곧 시스템 프롬프트 ...)
```

같은 정의를 `opencode.json` 에 쓰면 이렇습니다. (`check.py` 가 이 둘이 같은 권한 규칙·프롬프트·mode 를 낳는지 확인합니다.)

```json
{
  "agent": {
    "reviewer": {
      "description": "읽기 전용 코드 리뷰어",
      "mode": "primary",
      "prompt": "당신은 코드 리뷰어입니다. ...",
      "permission": { "edit": "deny", "bash": "deny", "task": "deny" }
    }
  }
}
```

## 따라 하기

1. 실험용 저장소를 만듭니다. **sandbox 가 자체 git 저장소여야 합니다.** `docs/**` 같은 경로 규칙은 git 저장소 루트 기준이기 때문입니다(아래 주의할 점).

   PowerShell:
   ```powershell
   cd examples\00-config\c8-agents
   python prepare.py
   cd sandbox
   ```
   Linux bash (`python` 명령이 없으면 `python3`):
   ```bash
   cd examples/00-config/c8-agents
   python3 prepare.py
   cd sandbox
   ```

2. **모델 없이** 에이전트가 어떻게 해석됐는지 봅니다.

   ```
   opencode debug agent reviewer
   opencode debug agent docs
   ```
   `permission` 배열에서 `edit`/`bash`/`task` 항목을, 끝의 `tools` 에서 `edit`/`write`/`bash`/`task` 가 `false` 인지 보세요. `docs` 의 `edit` 는 `* deny` 다음에 `docs/** allow` 순서입니다.

3. **모델 없이** 경로별 권한을 직접 시험합니다. (`--params` 는 작은따옴표를 쓰면 PowerShell 과 bash 에서 같은 모양입니다.)

   ```
   opencode debug agent docs --tool write --params "{ filePath: 'docs/new.md', content: 'hi' }"
   opencode debug agent docs --tool write --params "{ filePath: 'src/new.py', content: 'hi' }"
   opencode debug agent reviewer --tool edit --params "{ filePath: 'docs/guide.md', oldString: 'a', newString: 'b' }"
   ```
   첫 줄은 실행되고, 둘째 줄은 `The user has specified a rule which prevents you from using this specific tool call.`, 셋째 줄은 `Tool edit is disabled for agent reviewer` 입니다. 파일 경로가 상대 경로이므로 반드시 `sandbox` 에서 실행하세요.

4. 평소 쓰는 모델로 역할을 골라 시작합니다. 모델 설정이 없으면 `-m opencode/big-pickle` 을 붙이세요.

   ```
   opencode run --agent reviewer "src/calc.py 를 리뷰하고 add 를 subtract 로 바꿔 줘"
   opencode run --agent docs "docs/guide.md 의 첫 문장을 더 친절하게 고쳐 줘"
   ```
   실행 헤더가 `> reviewer · 모델이름`, `> docs · 모델이름` 으로 찍힙니다. 실제 모델의 응답은 이 문서를 쓸 때 확인하지 못했습니다(미검증). 아래 결과는 가짜 모델로 확인한 것입니다.

5. TUI 에서도 `opencode --agent reviewer` 처럼 `--agent` 옵션이 있습니다(`opencode --help` 에서 확인). 하지만 TUI 를 실제로 띄워 보지는 못했습니다. 에이전트 선택 화면에서 이름과 description 이 어떻게 보이는지도 **미검증**입니다.

## 기대 결과

(opencode 1.19.5, Linux. `check.py` 가 가짜 모델로 모델이 받은 요청을 읽어 확인한 결과입니다.)

### 모델이 받는 도구 목록

| 에이전트 | 도구 목록 |
|---|---|
| 기본 `build` | bash, edit, glob, grep, read, skill, task, todowrite, webfetch, write |
| `reviewer` | glob, grep, read, skill, todowrite, webfetch |
| `docs` | edit, glob, grep, read, skill, todowrite, webfetch, write |
| `researcher` (task 로 불린 하위 작업) | glob, grep, read, skill, webfetch |

- `docs` 는 `edit` 이 `* deny` 로 끝나지 않고 `docs/** allow` 로 끝나므로 `edit`·`write` 가 목록에 남고, 경로는 실행할 때 검사합니다. 반면 `bash: deny` 같은 통째 deny 는 목록에서 사라집니다.
- 본문(프롬프트)은 시스템 프롬프트에 들어갑니다. `reviewer` 의 "파일을 읽기만 하고 절대 고치지 않습니다", `docs` 의 JSON `prompt` 가 각각 확인됐습니다.

### 목록에 없는 도구를 모델이 부르면

`reviewer` 에게 `edit`(또는 `bash`)를 부르게 했을 때 모델이 받은 도구 결과입니다. 도구는 실행되지 않고, 종료 코드는 0 이며 대화는 이어집니다. 실행 기록에는 `✗ Invalid Tool` 이 찍힙니다.

```
The arguments provided to the tool are invalid: Model tried to call unavailable tool 'edit'. Available tools: glob, grep, invalid, read, skill, todowrite, webfetch.
```

### 경로별 edit (`docs`)

| 시도 | 결과 |
|---|---|
| `docs/guide.md` 수정 | 실행됨 (묻지 않음, `--auto` 없이도) |
| 새 파일 `docs/new.md`, 하위 폴더 `docs/sub/x.md` 쓰기 | 실행됨 |
| `src/calc.py` 수정, 새 파일 `src/new.py` 쓰기 | 거부 (`...prevents you from using this specific tool call`, 규칙 목록이 함께 나옴) |
| 같은 폴더인데 `.git` 이 없음 | `docs/guide.md` 수정도 **거부** |

마지막 줄이 중요합니다. 경로 규칙은 **git 저장소 루트를 기준으로 한 상대 경로**와 비교됩니다. 루트 아래 하위 폴더에 있는 `sub/docs/g.md` 도 `docs/**` 에 걸리지 않아 거부되는 것을 확인했습니다(임시 폴더 실험, `check.py` 에는 넣지 않음).

### `mode`: primary 와 subagent

| | `mode: primary` | `mode: subagent` |
|---|---|---|
| `--agent 이름` 으로 시작 | 됨 (`> reviewer`) | 안 됨. `agent "researcher" is a subagent, not a primary agent. Falling back to default agent` 경고 후 `build` 로 실행 |
| 다른 에이전트의 `task` 도구 설명 | 나오지 않음 | 나옴: `- researcher: 코드가 어디에...` (내장 `explore`, `general` 과 함께) |
| 사용 방식 | 사용자가 고른 대화의 주인공 | 주인공이 `task` 로 넘기는 하위 작업. 자기 프롬프트와 권한으로 새 대화처럼 돎 |

- 없는 이름(`--agent nosuch`)도 `agent "nosuch" not found. Falling back to default agent` 경고 후 `build` 로 실행합니다. 종료 코드 0 이라 **오타가 조용히 넘어갑니다.** 실행 헤더(`> build`)를 확인하세요.
- `build` 가 `task` 로 `researcher` 를 부르면 하위 작업의 요청에는 researcher 의 프롬프트("코드 조사원")가 시스템 프롬프트로 들어가고, `edit`·`bash`·`task` 가 없는 도구 목록을 받습니다.
- `reviewer` 와 `docs` 는 primary 라서 `build` 의 `task` 목록에 나오지 않습니다.

### 함정: 읽기 전용인데 `task` 가 열려 있으면 우회됩니다

`reviewer.md` 에서 `task: deny` 만 지운 사본으로 확인했습니다. `edit` 이 목록에 없는 reviewer 가 `task` 로 내장 `general` 하위 에이전트를 부르자, `general` 은 자기 권한(edit 허용)으로 `src/calc.py` 를 **실제로 고쳤습니다.** 그래서 이 예제의 `reviewer` 와 `docs` 에는 `task: deny` 가 들어 있습니다. 읽기 전용 에이전트를 만들 때는 `edit`, `bash` 만큼 `task` 도 막으세요.

### 에이전트 vs 스킬 vs 명령

| | 에이전트 (이 예제) | 스킬 ([S1a](../../01-skills/s1a-commit-message/README.md)) | 명령 ([C6](../c6-custom-commands/README.md)) |
|---|---|---|---|
| 정의하는 것 | 역할: 프롬프트 + 권한 (+ 모델) | 절차·지식 (본문은 필요할 때 로드) | 지시문 한 덩어리 |
| 누가 시작 | 사용자(`--agent`) 또는 모델(`task`) | 모델 (description 을 보고) | 사용자 (`/이름`, `--command`) |
| 모델 요청에 들어가는 때 | 고르면 시스템 프롬프트·도구 목록이 바뀜 | 이름+description 은 항상, 본문은 로드할 때 | 부를 때 사용자 메시지로 |
| 권한을 바꾸나 | **예** (도구가 목록에서 빠짐) | 아니오 | `agent:` 키로 에이전트를 고르면 간접적으로 |

## 동작 원리

1. 시작할 때 `.opencode/agent/*.md` 와 `opencode.json` 의 `agent` 가 하나의 에이전트 표로 합쳐집니다. `.md` 본문은 `prompt` 가 됩니다. 확인은 `opencode debug agent 이름` 입니다.
2. `permission` 은 내장 기본 규칙 뒤에 쌓이고 마지막으로 맞는 규칙이 이깁니다 ([C5](../c5-permissions/README.md)). 어떤 도구의 **모든 사용**이 deny 로 끝나면 그 도구는 모델에게 보내는 도구 목록에서 빠집니다.
3. 도구 목록에 있는 도구는 실행하기 직전에 규칙으로 검사합니다. `docs` 의 `edit` 은 `docs/**` 만 통과합니다.
4. 모델이 목록에 없는 도구를 부르면 opencode 가 그 호출을 `invalid` 도구 호출로 바꿔 위 오류 문장을 돌려줍니다.
5. `task` 도구는 subagent 를 실행합니다. 하위 작업은 **자기 에이전트의** 프롬프트와 권한을 씁니다. 부른 쪽 에이전트의 제한을 물려받지 않습니다(위 함정).

## 직접 바꿔 보기

1. `reviewer.md` 의 `bash: deny` 를 아래처럼 바꾸고 `debug agent reviewer` 의 `tools.bash` 와 도구 목록을 비교하세요. `check.py` 에서 확인한 대로 마지막 규칙이 `*` deny 가 아니면 `bash` 가 목록에 남습니다.
   ```yaml
   bash:
     "*": deny
     "git diff*": allow
   ```
2. `docs` 의 `docs/**` 를 `docs/*.md` 로 바꾸고 `docs/sub/x.md` 쓰기가 거부되는지 보세요. (이 패턴은 시험하지 않았습니다)
3. `researcher.md` 의 `mode` 를 `primary` 로 바꾸고 `--agent researcher` 가 되는지, `task` 목록에서 사라지는지 보세요.
4. `reviewer.md` 에 `model: provider/모델` 을 추가하면 그 에이전트만 다른 모델을 쓰는지 보세요. (`model` 키는 이 예제에서 시험하지 않았습니다. 미검증)

## 주의할 점

- **경로 규칙은 git 루트 기준입니다.** `docs/**` 가 동작하려면 프로젝트가 git 저장소의 루트여야 합니다. 이 저장소의 예제 폴더에서 바로 실행하면 루트가 세미나 저장소가 되므로 같은 이유로 `docs/**` 가 맞지 않을 것입니다(추정, 직접 시험하지 않음). 그래서 `prepare.py` 가 sandbox 를 자체 git 저장소로 만듭니다.
- **읽기 전용이라면 `task` 도 막으세요.** 위 함정 참고.
- `--agent` 에 틀린 이름이나 subagent 를 주면 오류가 아니라 경고 한 줄과 함께 `build` 로 실행됩니다. 권한을 믿고 돌리기 전에 헤더를 보세요.
- `permission` 은 도구 호출을 막을 뿐입니다. `bash` 를 일부 열어 두면(`git diff*` 등) 그 명령이 만드는 부작용은 패턴 설계에 달려 있습니다 ([C5](../c5-permissions/README.md) 참고).
- 이 예제의 `.opencode/` 가 있는 폴더에서 opencode 를 시작하면 `@opencode-ai/plugin` 을 설치하려고 시도하고 `.opencode/` 안에 `package.json`, `node_modules/` 가 생길 수 있습니다(모두 git 에서 제외). 자세한 내용은 [S1a README](../../01-skills/s1a-commit-message/README.md#주의할-점--문제-해결) 를 보세요.
- Linux 에서 `python` 명령이 없으면 `python3` 로 바꾸세요. 이 예제의 `opencode.json` 은 실행 명령을 쓰지 않아 그대로 둡니다.
