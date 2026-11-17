# P12 매 요청에 현재 상황을 넣어 주기 (context-injection)

> 구성: 플러그인(JS) `experimental.chat.system.transform` + `tool.definition` | 난이도: ★★☆ | 필요: opencode 1.19.5, git, Python 3.10+ (Node 는 단위 테스트에만) | 슬라이드: 플러그인 — 모델 요청 가공

> **이 예제의 핵심 훅은 이름이 `experimental.` 로 시작합니다.** opencode 버전이 바뀌면 이름이나 모양이 바뀌거나 사라질 수 있습니다(1.19.5 기준으로 확인). `check.py` 가 현재 동작을 고정해 두었으니, opencode 를 올린 뒤 `python check.py` 가 깨지면 이 훅부터 의심하세요. `tool.definition` 은 이름에 `experimental` 이 없지만, 이 역시 1.19.5 의 타입 정의(`@opencode-ai/plugin`)에 있는 훅이라는 것 외에 안정성을 보장받은 것은 아닙니다.

## 무엇을 보여 주나

"지금 브랜치", "작업 트리에 변경이 있는지", "오늘 날짜", "지금 하는 일" 같은 **시간에 따라 바뀌는 사실**은 정적인 AGENTS.md 에 적을 수 없습니다. 플러그인 훅은 모델 요청을 만들 때마다 불리므로, 그때그때의 사실을 시스템 프롬프트에 넣을 수 있습니다.

- **`context-injection.js`** — `experimental.chat.system.transform` 으로 시스템 프롬프트 끝에 작은 블록을 붙입니다.

  ```
  ## 지금 상황 (플러그인이 요청마다 갱신)
  - 오늘: 2026-11-17 (화)
  - git 브랜치: feat/alpha
  - 작업 트리: 깨끗함
  - 지금 하는 일 (.opencode/now.md):
    - 로그인 화면의 오류 메시지를 한국어로 바꾸는 중 (src/login 만 수정)
    - 끝나면 PR 을 열 것. 다른 폴더는 건드리지 않기
  ```

- **`bash-reminder.js`** — `tool.definition` 으로 `bash` 도구의 **설명** 끝에 프로젝트 규칙 한 줄(한 줄 명령 규칙)을 붙입니다.

## 실무에서는

- 에이전트가 "내가 지금 어느 브랜치에 있지", "오늘이 며칠이지"를 도구로 확인하느라 쓰는 턴을 줄입니다. 특히 날짜는 모델이 스스로 알 수 없는 사실입니다.
- 사람이 `.opencode/now.md` 한 파일에 "지금 하는 일, 건드리면 안 되는 곳"을 적어 두면 세션을 새로 열어도, 맥락이 압축돼도 다음 요청부터 다시 들어갑니다. 프롬프트로 매번 다시 말하지 않아도 됩니다.
- 특정 도구에만 해당하는 규칙(예: "bash 는 한 줄로")은 시스템 프롬프트가 아니라 그 도구의 설명에 붙이는 편이 모델이 도구를 쓰는 순간에 읽기 좋습니다.

### 어느 쪽을 쓸까: 고정 맥락을 넣는 세 곳

| | AGENTS.md | 스킬 | 이 훅 (`system.transform`) |
|---|---|---|---|
| 내용이 바뀌는가 | 사람이 파일을 고칠 때만 | 사람이 파일을 고칠 때만 | **요청마다** 코드가 새로 계산 |
| 언제 모델에게 가는가 | 항상 | **필요할 때만** (모델이 스킬을 불러야 본문이 들어옴) | 항상 |
| 담기 좋은 것 | 변하지 않는 규칙, 빌드·테스트 명령, 코드 스타일 | 길고 가끔 쓰는 절차(릴리스 방법, 마이그레이션 가이드) | 브랜치, 날짜, 작업 트리 상태, "지금 하는 일" |
| 비용 | 매 요청 그 글자 수만큼 (내용이 같아서 캐시되기 쉬움) | 이름·설명만 항상, 본문은 부를 때만 + 부르는 턴 | 매 요청 그 글자 수만큼 + 내용이 바뀌면 프롬프트 캐시에 불리 + 실행 비용(아래) |
| 쓰는 사람의 부담 | 마크다운 | 마크다운 | JS 플러그인, 실험 훅이라 버전 추적 |

이 예제에서 측정한 크기: 위 블록은 **191자**이고, 같은 폴더의 기본 시스템 프롬프트(플러그인 없음)는 **9591자**였습니다(약 2%). `now.md` 를 길게 쓰면 그만큼 모든 요청에서 늘어나므로 800자에서 잘라 넣습니다.

## 파일 구성

```
p12-context-injection/
├── README.md
├── fake_llm.py                            # 검증용 가짜 LLM (표준 라이브러리만, 복사본)
├── check.py                               # 자동 검증 (단위 테스트 + 가짜 모델로 모델 요청 본문 검사 + --model 검사)
├── .opencode/
│   ├── now.md                             # "지금 하는 일" (예시. 사람이 고치는 파일)
│   └── plugins/
│       ├── context-injection.js           # 플러그인 1: 시스템 프롬프트에 지금 상황 블록
│       └── bash-reminder.js               # 플러그인 2: bash 도구 설명에 규칙 한 줄 (tool.definition)
├── tests/hooks.test.mjs                   # 두 플러그인의 훅을 직접 호출하는 단위 테스트 (28건, node + git)
└── logs/                                  # 실행하면 생김: context-injection.log (요청마다 inject 한 줄)
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. (모델 설정이 없다면 무료 모델 `-m opencode/big-pickle` 을 붙이세요.) 실제 모델로는 이번에 돌리지 않아 **미검증**입니다.

1. 먼저 모델 없이 훅만 시험합니다. 임시 git 저장소를 만들어 브랜치·작업 트리·캐시를 확인합니다.

   PowerShell:
   ```powershell
   cd examples\03-plugins\p12-context-injection
   node tests\hooks.test.mjs
   ```
   Linux bash:
   ```bash
   cd examples/03-plugins/p12-context-injection
   node tests/hooks.test.mjs
   ```
   `context-injection: 28 checks, 0 failed` 가 나오면 정상입니다.

2. **연습용 저장소를 따로 만듭니다.** 블록의 `git 브랜치` 항목은 이 폴더가 git 저장소일 때만 나옵니다. 1번에서 들어간 이 예제 폴더에서 이어서, 복사본을 저장소로 만드세요. (복사본이 이미 있으면 먼저 지웁니다.)

   PowerShell:
   ```powershell
   Remove-Item -Recurse -Force $env:TEMP\ctx-demo -ErrorAction SilentlyContinue
   Copy-Item -Recurse . $env:TEMP\ctx-demo
   cd $env:TEMP\ctx-demo
   git init -b feat/alpha; git config user.name demo; git config user.email demo.invalid
   git add .; git commit -m init
   ```
   Linux bash:
   ```bash
   rm -rf /tmp/ctx-demo
   cp -r . /tmp/ctx-demo && cd /tmp/ctx-demo
   git init -b feat/alpha && git config user.name demo && git config user.email demo.invalid
   git add . && git commit -m init
   ```
   (`demo.invalid` 는 이메일 형태가 아닌 자리 채움 값입니다. git 은 이 값으로도 커밋합니다.)

3. opencode 를 실행합니다. 처음 실행하면 opencode 가 `.opencode/` 안에 `@opencode-ai/plugin` 을 npm 으로 설치하려고 합니다. 인터넷이 막혀 있고 패키지 미러도 없으면 첫 시작이 70초쯤 멈췄다가 계속 진행됩니다. 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 아주 처음, 새 환경에서의 첫 시작은 약 130초까지 걸렸습니다(패킷을 조용히 버리는 레지스트리면 200초를 넘을 수도 있습니다). 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다. (이 단계는 패키지 미러가 필요할 수 있습니다.)

   ```
   opencode
   ```

4. `도구를 쓰지 말고 답해 줘: 지금 브랜치 이름, 오늘 날짜, 지금 하는 일이 뭐야?` → 모델이 블록의 내용을 답해야 합니다(실제 모델 **미검증**). 다른 터미널에서 `git switch -c feat/beta` 를 하고 다음 질문을 하면 답이 `feat/beta` 로 바뀝니다(최대 5초 캐시 이후).

5. 기록 확인 (요청마다 한 줄):

   PowerShell: `Get-Content -Encoding UTF8 logs\context-injection.log`
   Linux bash: `cat logs/context-injection.log`

6. 자동 검증: 3~5번은 연습용 저장소(`ctx-demo`)에서 했으므로, 1번과 같은 예제 폴더로 돌아가서 실행합니다. `python check.py` / `python check.py --model` (Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요).

## 기대 결과

아래는 `check.py` 가 쓰는 **가짜 LLM**(`fake_llm.py`)이 받은 **요청 본문**을 그대로 분석해 얻은 것입니다. 샌드박스의 임시 git 저장소(`feat/alpha` 브랜치)에서 실제 `opencode 1.19.5`(Linux)를 실행했습니다. 가짜 LLM 이 `bash` 를 두 번 호출한 뒤 답했으므로 모델 요청은 도구가 붙은 것 3번 + 제목 생성용 1번(도구 없음)이었습니다.

모든 요청의 `messages` 는 `system`(기본 프롬프트, 9591자) → `system`(플러그인 블록) → … 순서였습니다. 첫 요청에 들어간 블록은 위 "무엇을 보여 주나" 의 그것과 같고(191자), 브랜치를 `feat/beta` 로 바꾼 다음 실행에서는:

```
## 지금 상황 (플러그인이 요청마다 갱신)
- 오늘: 2026-11-17 (화)
- git 브랜치: feat/beta
- 작업 트리: 깨끗함
- 지금 하는 일 (.opencode/now.md):
  - 로그인 화면의 오류 메시지를 한국어로 바꾸는 중 (src/login 만 수정)
  - 끝나면 PR 을 열 것. 다른 폴더는 건드리지 않기
```

`bash` 도구 설명(모델에게 간 `tools[].function.description`)의 끝:

```
… Use `gh` for GitHub tasks, including PRs, issues, checks, and releases; return the PR URL when done.

프로젝트 규칙: 명령은 한 줄로 쓰고, 여러 명령은 &&(PowerShell 5.1 에서는 ;)로 잇습니다. heredoc 이나 줄바꿈이 든 명령은 쓰지 않습니다.
```

확인한 사실(모두 `check.py` 가 고정):

- 블록은 도구가 붙은 **모든** 모델 요청에 정확히 하나씩 들어갑니다(3번 모두). 제목 생성 같은 **보조 요청(도구 없음)에도** 같은 블록이 들어갑니다. 훅은 모델을 부르는 모든 곳에서 불립니다. 기본 시스템 프롬프트는 대조군(플러그인 없음)과 같고(작업 폴더 경로만 다름) 블록은 별도의 `system` 메시지로 맨 끝에 붙습니다.
- `bash` 설명은 원래 설명 + 빈 줄 + 규칙 한 줄이고, 3번의 요청 모두에서 **한 번만** 들어 있습니다(누적되지 않음). `bash` 이외 도구의 설명은 대조군과 한 글자도 다르지 않았습니다.
- 브랜치를 바꾸면 다음 실행의 블록이 바뀝니다(`feat/alpha` → `feat/beta`).
- **캐시**: 기본 TTL(5초) 안에서는 도구가 파일을 만든 뒤에도 다음 요청의 블록이 `작업 트리: 깨끗함` 으로 남습니다(오래된 값). `CONTEXT_TTL_MS=0` 이면 `깨끗함` → `커밋되지 않은 변경 있음` → `커밋되지 않은 변경 있음` 으로 바로 반영되고, 그때 시스템 프롬프트 본문이 두 가지로 갈라집니다. 기본(flag)에서는 변경이 1개든 10개든 문구가 같고, `CONTEXT_DIRTY=count` 를 켜야 `변경 1개` 처럼 개수가 들어갑니다(둘 다 확인).
- git 저장소가 아니고 `now.md` 도 없으면 날짜 한 줄만 들어갑니다.
- 비용(Linux, 작은 저장소, 20회 중앙값): git 조회 포함 3.6ms(최대 4.1ms), 캐시 적중 0.0ms(최대 0.1ms).

`logs/context-injection.log`:

```
2026-11-17T07:55:17.310Z context-injection loaded
2026-11-17T07:55:18.194Z inject session=ses_… chars=191 gitCached=false
2026-11-17T07:55:18.872Z inject session=ses_… chars=191 gitCached=true
2026-11-17T07:55:18.992Z inject session=ses_… chars=191 gitCached=true
2026-11-17T07:55:19.083Z inject session=ses_… chars=191 gitCached=true
```

(요청 4번 = 훅 4번. 첫 번째만 git 을 실제로 조회했습니다.)

```
$ node tests/hooks.test.mjs
context-injection: 28 checks, 0 failed
$ python3 check.py
== 20 checks, 0 failed, 0 warnings
```

## 동작 원리

1. **`experimental.chat.system.transform(input, output)`**: `output.system` 은 문자열 배열이고 `push` 한 것이 시스템 프롬프트의 끝에 붙습니다. `input` 은 `{sessionID?, model}` 입니다. 이 플러그인은 날짜(로컬 시간대), `git symbolic-ref -q --short HEAD`(브랜치), `git status --porcelain`(변경 개수. 플러그인이 만드는 `logs/` 는 세지 않음), `.opencode/now.md` 를 모아 한 블록으로 만듭니다. git 은 셸 없이 인자 배열로 실행합니다(3초 제한).
2. **작고 싸게**: git 조회 결과는 `CONTEXT_TTL_MS`(기본 5000)ms 동안 캐시합니다. 날짜와 `now.md` 읽기는 매번 합니다(싸고, `now.md` 를 고치면 바로 반영되기를 기대하므로). `now.md` 는 800자에서 자르고, 변경은 있음/없음만(선택 시 개수) 적으며 파일 목록은 넣지 않습니다.
3. **절대 throw 하지 않음**: git 이 없음/저장소 아님/폴더 없음/`now.md` 없음/이상한 입력 모두 해당 항목을 빼거나 블록 전체를 건너뜁니다(`logs/context-injection.log` 에 `ERROR`). 훅이 터져서 모든 요청이 실패하는 것이 가장 나쁜 결과이기 때문입니다.
4. **`tool.definition(input, output)`**: `input.toolID` 가 `bash` 일 때 `output.description` 뒤에 한 줄을 붙입니다. 도구 정의는 요청마다 새로 만들어지고 훅도 그때마다 불리지만, 매번 새 정의에 한 번 붙이는 것이므로 쌓이지 않습니다(확인). `output.parameters` 도 바꿀 수 있습니다.

### 시스템 프롬프트 vs 도구 설명: 언제 무엇을

- **모든 작업에 해당하는 사실**(브랜치, 날짜, 지금 하는 일) → `system.transform`. 어떤 도구를 쓰든 모델이 알고 있어야 하는 것.
- **특정 도구를 쓸 때만 해당하는 규칙**(bash 명령은 한 줄로, 파일 쓰기는 이 폴더에만) → `tool.definition`. 모델이 그 도구를 고르고 인자를 만드는 순간 읽는 곳에 있어서 지켜질 가능성이 높고, 그 도구를 안 쓰는 요청에는 영향이 없습니다. (지켜질 가능성이 얼마나 높아지는지는 측정하지 않았습니다.)
- **지키지 못하면 안 되는 규칙** → 둘 다 부탁일 뿐입니다. [P2](../p2-dangerous-command-guard/README.md), [P10](../p10-branch-guard/README.md) 처럼 `tool.execute.before` 로 막으세요.

## 직접 바꿔 보기

1. `.opencode/now.md` 를 고치고(임시 저장소에서) 다음 질문에서 모델 답이 바뀌는지 보세요. 5초 안에 연속으로 물으면 git 정보만 이전 값입니다.
2. `CONTEXT_DIRTY=count` 로 실행해 `작업 트리` 줄에 `커밋되지 않은 변경 N개` 가 들어가는지 보고, 파일을 고칠 때마다 블록이 바뀌는 것을 `logs`/모델 요청으로 확인해 보세요. 기본값(flag)은 `있음`/`깨끗함` 두 가지뿐입니다.
3. `gitLines()` 에 `git log -1 --format=%s` (마지막 커밋 제목) 줄을 추가하고, `tests/hooks.test.mjs` 에 사례를 넣어 보세요.
4. `BASH_REMINDER="모든 명령 앞에 cd 로 프로젝트 루트로 이동하지 마세요."` 처럼 환경변수로 문장을 바꿔 실행하고, 모델이 받은 `bash` 설명이 바뀌는지 `check.py` 의 방식으로 확인해 보세요.

## 주의할 점 / 문제 해결

- **실험 훅입니다.** `experimental.chat.system.transform` 은 이름이 바뀌거나 사라질 수 있고, 지금 보이는 동작(제목 생성 요청에도 불림, `system` 메시지가 별도로 붙음)이 바뀔 수 있습니다. `check.py` 의 해당 검사가 FAIL 하면 opencode 버전부터 확인하세요.
- **프롬프트 캐시.** 시스템 프롬프트는 요청의 맨 앞이라, 이 블록의 내용이 바뀌면 그 뒤의 대화 전체가 공급자의 프롬프트 캐시 접두부에서 달라질 수 있습니다. 가짜 모델로는 공급자 쪽 캐시 효과를 **측정하지 못했습니다**. 확인한 것은 "작업 트리 상태가 바뀐 요청부터 시스템 프롬프트 본문이 달라진다"는 사실뿐입니다. 그래서 기본값을 `CONTEXT_DIRTY=flag`(있음/없음)로 했습니다. 파일을 고칠 때마다 바뀌는 개수를 시스템 블록에 넣으면 매 편집마다 프롬프트 캐시가 깨질 수 있다는 설계상의 고려이며, 여기서 측정한 것은 아닙니다. 개수가 꼭 필요하면 `CONTEXT_DIRTY=count` 로 켜고, TTL 을 늘리거나 날짜만 넣는 식으로도 조절하세요. 오래 걸리는 긴 대화일수록 영향이 큽니다.
- **오래된 값.** 캐시 때문에 최대 `CONTEXT_TTL_MS` 동안은 실제와 다를 수 있습니다(위에서 확인). 모델은 이 블록을 사실로 믿습니다. 정확해야 하는 판단(예: 커밋 가능 여부)은 [P10](../p10-branch-guard/README.md) 처럼 실행 시점에 다시 확인하세요.
- **작업 트리 변경에는 untracked 파일이 포함됩니다.** `.gitignore` 에 없는 임시 파일만 있어도 `변경 있음` 이 됩니다.
- **`now.md` 는 신뢰할 수 있는 입력이어야 합니다.** 파일 내용이 그대로 시스템 프롬프트에 들어가므로, 외부에서 받은 파일을 가리키게 하면 프롬프트 주입 경로가 됩니다.
- 윈도에서는 `git` 이 PATH 에 있어야 하고, **Windows 에서의 확인**: 네이티브 Windows(Windows Python 3.12, Windows 용 opencode 1.19.5, PowerShell 5.1)에서 `check.py` 20건과 단위 테스트(28건)가 통과했습니다. 그곳의 기본 시스템 프롬프트는 9529자(Linux 9591자)이고 주입 블록은 같은 191자였습니다. 다만 Windows 에서는 요청 사이가 5초를 넘기도 해서(관찰: 첫 요청과 네 번째 요청이 5.4초 간격) 기본 TTL(5초)의 캐시 시나리오는 시간에 따라 결과가 달라졌고, 그래서 `check.py` 는 그 시나리오를 `CONTEXT_TTL_MS=600000` 으로 고정하며 TTL 자체는 단위 테스트가 확인합니다. 실제 모델과 PowerShell 7 은 **미검증**입니다. 날짜는 로컬 시간대이고 요일은 직접 만든 표를 쓰므로 ICU 에 의존하지 않습니다.
- **export 는 플러그인 함수만 하세요.** 숫자·문자열·객체 같은 함수가 아닌 값(`export const X = 1`)을 export 하면 opencode 가 **파일 전체를 건너뜁니다.** 평소 실행에는 아무 출력도 없고 `opencode --print-logs` 에만 `Plugin export is not a function` 오류가 보입니다. 보조 함수를 export 하면 그 함수까지 플러그인으로 호출됩니다. 그래서 `WEEKDAYS`, `git()`, `today()` 는 export 하지 않습니다. `.opencode/plugins/` 안의 모든 `.js` 가 플러그인으로 로드되므로 테스트는 그 폴더 밖(`tests/`)에 둡니다. 이 폴더에는 플러그인이 두 파일이고, 각각 플러그인 함수 하나만 export 합니다.
- `node` 나 `git` 이 없으면 `check.py` 가 경고(WARN)를 내고 해당 검사를 건너뜁니다. opencode 실행에는 Node 가 필요 없습니다.
