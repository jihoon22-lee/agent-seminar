# S5b 스킬을 "직접 부를 때만" 쓰게 하기 — 수동 호출과 권한

> 구성: 스킬 4개 + 에이전트 1개 + opencode.json | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: 스킬 (자동 사용 제어)

## 무엇을 보여 주나

스킬은 기본적으로 모델이 마음대로 열 수 있습니다. 하지만 배포 체크리스트나 야간 정리처럼 **사람이 "지금 해"라고 했을 때만** 돌아야 하는 스킬도 있습니다.
이 예제는 opencode 1.19.5에서 그 목적에 **실제로 통하는 방법과 통하지 않는 방법**을 가짜 모델로 하나씩 재현해 보여 줍니다.
결론부터: `permission.skill` 의 `deny` 로 모델의 시야와 호출을 막고, 사람은 `/skills` 선택창이나 `opencode run --command` 로 부르는 조합이 통합니다. 다른 도구에서 흔히 보는 frontmatter 플래그(`disable-model-invocation` 등)는 **1.19.5에서는 아무 효과가 없습니다.**

## 실무에서는

- 운영 배포, 데이터 삭제, 결제 취소 같은 절차 스킬을 모델이 "도움이 될 것 같아서" 먼저 꺼내 들면 곤란합니다. `deny` 로 모델 쪽 문을 닫고, 담당자가 직접 부를 때만 쓰게 합니다.
- 같은 스킬을 `release` 같은 전용 에이전트에서만 허용해, 릴리스 담당자가 그 에이전트로 전환했을 때만 모델이 쓰게 할 수도 있습니다.
- CI나 스크립트에서 `opencode run --command 이름 인자…` 로 "정해진 절차 + 오늘의 인자"를 그대로 모델에 넘깁니다.
- 팀 저장소의 `opencode.json` 에 `permission.skill` 규칙을 커밋해 두면, clone 한 모든 사람에게 같은 안전장치가 적용됩니다.

## 파일 구성

```
s5b-manual-and-permission/
  README.md
  opencode.json                          permission.skill = { "*": "allow", "deploy-*": "deny" }
  .opencode/
    skills/
      deploy-checklist/SKILL.md          deny 로 막은 스킬 (사람이 직접 부르는 용도)
      team-glossary/SKILL.md             아무 제한 없는 보통 스킬 (비교용)
      nightly-cleanup/SKILL.md           frontmatter 플래그만 붙인 스킬 (효과 없음을 보여 줌)
      scratch-notes/SKILL.md             description 이 없는 스킬
    agents/release.md                    deploy-* 스킬을 다시 허용하는 에이전트
  demo.py                                모든 시나리오를 가짜 모델로 돌려 표로 보여 줌 (모델·인터넷 불필요)
  show_prompt.py                         모델이 처음부터 받는 스킬 목록을 그대로 출력
  mock_llm.py                            127.0.0.1 에서 도는 가짜 모델 서버 (요청 기록 + skill 도구 호출 흉내)
  lab.py                                 임시 샌드박스를 만드는 공용 도우미
  check.py                               자동 검증
```

> 이 폴더에는 `.opencode/` 가 있으므로 처음 실행할 때 opencode 가 `@opencode-ai/plugin` 을 npm 에서 `.opencode/` 안에 자동 설치합니다 (`package.json`, `node_modules/` 생성, 모두 git 에서 제외됨). 레지스트리에 접근할 수 없는 환경에서는 첫 실행이 약 70초 멈췄다가 계속됩니다. 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다.

## 따라 하기

모든 명령은 이 예제 폴더에서 실행합니다. Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. 평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 무료 모델 `-m opencode/big-pickle` 을 붙이세요.

### 1. 가짜 모델로 전체 결과 한 번에 보기 (약 1분)

PowerShell:

```powershell
cd examples\01-skills\s5b-manual-and-permission
python demo.py
python show_prompt.py
```

Linux bash:

```bash
cd examples/01-skills/s5b-manual-and-permission
python3 demo.py
python3 show_prompt.py
```

`demo.py` 는 임시 샌드박스(임시 XDG 폴더)에서 `opencode run -m mock/m` 을 여러 번 실행합니다. 가짜 모델은 프롬프트에 `[[skill:이름]]` 이 있으면 `skill` 도구를 그 이름으로 호출하는 척하므로, "모델이 목록에서 볼 수 있는가"와 "불러 보면 어떻게 되는가"가 매번 똑같이 재현됩니다.

### 2. 직접 써 보기 (TUI)

1. 이 폴더에서 `opencode` 를 실행합니다.
2. 프롬프트에 `배포 체크리스트 알려줘` 라고 입력합니다. `deploy-checklist` 는 모델 목록에 없으므로 모델이 스킬 없이 대답합니다.
3. 프롬프트에 `/skills` 를 입력하고 Enter 를 누릅니다. 스킬 선택창에 **deploy-checklist 도 보입니다**(deny 여도). 위/아래로 고르고 Enter 를 누르면 프롬프트에 `/deploy-checklist ` 가 들어갑니다.
4. 뒤에 `프로덕션 v2.3` 처럼 인자를 붙여 Enter. 스킬 본문과 인자가 그대로 사용자 메시지가 되어 모델에게 전달됩니다.

### 3. 터미널 한 줄로 부르기

PowerShell:

```powershell
opencode run --command deploy-checklist "프로덕션" "v2.3"
# 모델 설정이 없다면
opencode run -m opencode/big-pickle --command deploy-checklist "프로덕션" "v2.3"
```

Linux bash:

```bash
opencode run --command deploy-checklist 프로덕션 v2.3
opencode run -m opencode/big-pickle --command deploy-checklist 프로덕션 v2.3
```

### 4. release 에이전트로 전환해서 모델이 직접 쓰게 하기

TUI 에서 Tab 키로 `release` 에이전트로 바꾸거나, `opencode run --agent release "v2.3 배포 직전 점검해 줘"` 처럼 실행하면, 이 에이전트에서는 `deploy-checklist` 가 모델 목록에 다시 나타납니다.

### 5. 자동 검증

```bash
python3 ../../../tools/run_checks.py s5b            # 가짜 모델만 사용, 모델 쿼터 안 씀
python3 ../../../tools/run_checks.py s5b --model    # 실제 모델 1회 추가
```

## 기대 결과

`python demo.py` (Linux, opencode 1.19.5, 가짜 모델):

```
== 1. 이 예제의 설정 그대로 (permission.skill = {'*': allow, 'deploy-*': deny})
  - team-glossary (아무 제한 없음)
      모델 목록에서 보임 / 모델이 skill 도구로 부르면: 로드됨
  - nightly-cleanup (frontmatter 플래그만 있음)
      모델 목록에서 보임 / 모델이 skill 도구로 부르면: 로드됨
  - scratch-notes (description 없음)
      모델 목록에서 안 보임 / 모델이 skill 도구로 부르면: 로드됨
  - deploy-checklist (permission deny)
      모델 목록에서 안 보임 / 모델이 skill 도구로 부르면: deny 규칙에 막힘

== 2. 에이전트별 규칙
  - release 에이전트 (agent 파일이 deploy-* 허용)
      모델 목록에서 보임 / 모델이 skill 도구로 부르면: 로드됨
  - build 에이전트에만 deny
      모델 목록에서 안 보임 / 모델이 skill 도구로 부르면: deny 규칙에 막힘
  - 같은 설정에서 plan 에이전트
      모델 목록에서 보임 / 모델이 skill 도구로 부르면: 로드됨

== 3. 규칙 순서와 ask
  - 순서를 거꾸로: deploy-* deny 다음에 * allow
      모델 목록에서 보임 / 모델이 skill 도구로 부르면: 로드됨
  - deploy-* ask + opencode run --auto
      모델 목록에서 보임 / 모델이 skill 도구로 부르면: 로드됨
  - deploy-* ask + opencode run (--auto 없음)
      모델 목록에서 보임 / 모델이 skill 도구로 부르면: ask → run 모드가 자동 거절

== 4. 사람이 직접 부르기: opencode run --command deploy-checklist 프로덕션 v2.3
  deny 상태인데도 스킬 본문이 사용자 메시지로 들어감: True, 인자가 끝에 붙음: True
  (이때 모델은 skill 도구를 쓰지 않았음: 도구 호출 표식 없음 = True)
```

deny 된 스킬을 모델이 억지로 불러 봤을 때 `opencode run` 이 보여 주는 메시지:

```
✗ Skill "deploy-checklist" failed
Error: The user has specified a rule which prevents you from using this specific tool call. Here are some of the relevant rules [..., {"permission":"skill","pattern":"deploy-*","action":"deny"}]
```

`ask` 인데 `--auto` 없이 `opencode run` 을 실행했을 때:

```
! permission requested: skill (deploy-checklist); auto-rejecting
✗ Skill "deploy-checklist" failed
Error: The user rejected permission to use this specific tool call.
```

서버(`opencode serve`)의 `GET /command` 는 스킬을 `source: "skill"` 명령으로 돌려줍니다 (deny 된 `deploy-checklist` 도 포함. `template` 은 줄임):

```json
{ "name": "deploy-checklist", "description": "운영 배포 직전에 확인하는 체크리스트. …", "source": "skill", "template": "# 배포 체크리스트 (DEPLOY-CHECKLIST-V3)…", "hints": [] }
{ "name": "init",             "description": "guided AGENTS.md setup", "source": "command", … }
```

TUI 에서 `/skills` 를 입력하면 (Linux, 가짜 모델로 pty 에서 확인한 화면):

```
 Skills
 Search skills…
 Skills
 customize-opencode Use ONLY when the user is editing or creating opencode's own configuration…
 deploy-checklist   운영 배포 직전에 확인하는 체크리스트. 사람이 /deploy-checklist 로 직접 불렀을 때만…
 team-glossary      …
```

`deploy-checklist` 를 고르고 `프로덕션 v2.3` 을 붙여 보내면 사용자 메시지는 다음과 같이 만들어집니다.

```
# 배포 체크리스트 (DEPLOY-CHECKLIST-V3)
…(SKILL.md 본문)…

Base directory for this skill: <스킬 폴더>
Relative paths in this skill (e.g., scripts/, references/) are relative to this base directory.

프로덕션 v2.3
```

실제 모델로 `--command` 를 실행한 결과는 이 문서를 쓸 때 **확인하지 못했습니다** (무료 모델이 사용량 한도 오류로 응답하지 않았습니다). 위 결과는 모두 가짜 모델로 얻은 것이라 "모델에게 무엇이 전달되는가"는 결정적으로 확인된 반면, 실제 모델이 그 체크리스트를 얼마나 잘 따르는지는 직접 확인해야 합니다. check.py `--model` 에 해당 항목이 있습니다.

## 동작 원리

**1. 모델이 처음부터 보는 것.** opencode 는 system 프롬프트에 `<available_skills>` 블록(이름, description, 위치)을 넣고, 모델은 `skill` 도구로 이름을 지정해 본문을 불러옵니다. `show_prompt.py` 가 이 블록을 그대로 보여 줍니다. 본문은 처음부터 들어 있지 않습니다.

**2. frontmatter 플래그는 효과가 없습니다 (1.19.5).** `nightly-cleanup` 에는 `disable-model-invocation: true` 와 `metadata: {"opencode/autoinvoke": "false"}` 를 둘 다 붙였지만, `opencode debug skill` 에도, 모델의 `<available_skills>` 에도 그대로 나타나고 모델이 불러올 수 있습니다. opencode 는 frontmatter 에서 `name` 과 `description` 만 의미 있게 읽고 나머지 키는 무시하는 것으로 관찰됩니다. 다른 도구용 SKILL.md 를 가져와도 이 플래그만으로는 자동 사용이 막히지 않습니다.

**3. `permission.skill` 이 진짜 안전장치입니다.**

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": { "skill": { "*": "allow", "deploy-*": "deny" } }
}
```

- 키는 스킬 이름(와일드카드 `*` 가능), 값은 `allow` / `ask` / `deny`.
- **마지막으로 일치한 규칙이 이깁니다.** 그래서 넓은 규칙(`*`)을 먼저, 좁은 규칙(`deploy-*`)을 나중에 씁니다. `{"deploy-*": "deny", "*": "allow"}` 처럼 거꾸로 쓰면 모든 스킬이 허용되어 deny 가 무효가 됩니다 (demo 3번에서 확인).
- `deny` 는 이중으로 막습니다. 그 에이전트의 `<available_skills>` 에서 빠지고, 이름을 알고 억지로 불러도 호출이 거부됩니다.
- `ask` 는 목록에는 보이지만 불러오는 순간 확인을 받습니다. TUI 에서는 `Permission required` 창(Allow once / Allow always / Reject)이 뜹니다. `opencode run` 에서는 `--auto` 가 있으면 자동 승인, 없으면 자동 거절됩니다. `--auto` 는 **명시적으로 deny 하지 않은 것만** 승인하므로 deny 는 `--auto` 로도 뚫리지 않습니다.
- 규칙이 없으면 기본값은 허용입니다(`--auto` 없이도 로드됨).

**4. 에이전트별 규칙.** 에이전트의 `permission` 은 전역 규칙 뒤에 붙으므로 에이전트 쪽이 이깁니다. `.opencode/agents/release.md` 의 frontmatter 에 `permission: { skill: { "deploy-*": allow } }` 를 쓰면 `release` 에이전트에서만 deploy-checklist 가 목록에 다시 나타납니다. 반대로 `opencode.json` 의 `agent.build.permission.skill` 에 deny 를 두면 build 에서만 막히고 plan 에서는 허용됩니다 (demo 2번).

**5. 사람이 직접 부르는 길.** 모든 스킬은 `source: "skill"` 인 명령으로도 등록됩니다 (서버의 `GET /command` 에서 확인, check.py 가 검증).
- `opencode run --command 이름 인자…`: 스킬 본문 + `Base directory for this skill: …` 안내 + 인자가 사용자 메시지가 됩니다. **모델은 skill 도구를 쓰지 않고**, `permission` 의 deny 에도 영향을 받지 않습니다.
- TUI: `/` 입력 창의 자동완성 목록에는 스킬이 나오지 않습니다(Linux 확인). 대신 내장 명령 `/skills` 가 모든 스킬을 검색하는 선택창을 열고, 선택하면 `/이름 ` 이 프롬프트에 들어갑니다. deny 된 스킬도 이 창에 보입니다.
- `@이름` 은 스킬을 부르지 않습니다. TUI 의 `@` 자동완성은 에이전트, 파일(`.opencode/skills/deploy-checklist/SKILL.md` 같은 경로), 참조 폴더를 보여 줄 뿐입니다 (Linux 확인).

**6. description 이 없는 스킬.** `scratch-notes` 처럼 description 을 생략하면 모델 목록에서 빠집니다. 다만 이름을 아는 모델이 `skill` 도구로 부르면 로드되고(막는 장치가 아님), 사람은 `/skills`·`--command` 로 부를 수 있습니다. "목록에서만 숨기기"로는 쓸 수 있지만 안전장치는 아닙니다.

## 직접 바꿔 보기

1. `opencode.json` 의 `deny` 를 `ask` 로 바꾸고 TUI 에서 `deploy-checklist` 를 모델이 쓰게 유도해 보세요. 확인 창이 뜨는지, `Allow always` 를 누르면 같은 세션에서 다시 묻지 않는지 살펴보세요.
2. 규칙 순서를 `{"deploy-*": "deny", "*": "allow"}` 로 뒤집고 `python demo.py` 의 1번 결과가 어떻게 달라지는지 보세요.
3. `.opencode/agents/release.md` 를 복사해 `ops.md` 를 만들고 `nightly-cleanup` 만 허용하는 전용 에이전트를 만들어 보세요. (규칙: `"nightly-*": allow`)
4. `scratch-notes` 에 `description` 을 달았다 지웠다 하면서 `python show_prompt.py` 의 목록이 어떻게 달라지는지 보세요.

## 주의할 점 / 문제 해결

- **`disable-model-invocation` 은 믿지 마세요.** 다른 도구의 문서에서 본 플래그를 그대로 쓰면 아무 일도 일어나지 않고, 에러도 경고도 없습니다. `opencode debug skill` 은 모델 목록이 아니라 발견된 스킬 전체를 보여 주므로(deny 스킬도 나옴) 이것으로는 막혔는지 알 수 없습니다. 모델이 실제로 받는 목록은 `python show_prompt.py` 로 확인하세요.
- **규칙 순서.** 마지막 일치 규칙이 이기므로 `"*"` 는 항상 맨 앞에 둡니다. JSON 객체에 쓴 키 순서가 그대로 규칙 순서가 됩니다. `opencode debug config` 의 `permission.skill` 에서 실제 순서를 확인할 수 있습니다.
- **`deny` 해도 사람은 부를 수 있습니다.** 이 동작이 이 패턴의 핵심이지만, 같은 컴퓨터를 쓰는 누구나 `/skills` 로 부를 수 있다는 뜻이기도 합니다. 접근 통제 수단이 아니라 "모델의 자율 호출을 막는 장치"입니다.
- **스크립트에서 `opencode run` 을 띄울 때 `PWD`.** `opencode run` 은 프로세스의 현재 폴더가 아니라 환경변수 `PWD` 를 작업 폴더로 삼는 것으로 관찰됩니다(Linux). Python 의 `subprocess.run(cwd=...)` 만 쓰면 `PWD` 는 부모의 폴더로 남아 엉뚱한 폴더의 스킬이 보입니다. `lab.py` 는 `PWD` 도 함께 맞춥니다. `opencode debug …` 는 영향을 받지 않았습니다.
- **TUI 확인은 Linux 에서만.** `/skills` 선택창, `@` 자동완성, `ask` 확인 창은 Linux 의 pty 에서 확인했고 Windows 의 TUI 는 확인하지 않았습니다. `opencode run`·`debug`·서버 `/command` 는 Windows 에서도 check.py 로 확인했습니다.
- **가짜 모델 서버 포트.** `mock_llm.py` 는 운영체제가 비어 있는 포트를 골라 주므로(`127.0.0.1` 에만 열림) 충돌하지 않습니다.
- **환경.** Windows PowerShell 에서도 `python demo.py` 가 그대로 동작합니다. 한글이 깨지면 `$env:PYTHONUTF8=1` 을 설정하세요 (스크립트는 stdout 을 UTF-8 로 재설정하지만 파이프로 넘길 때 필요할 수 있습니다).
