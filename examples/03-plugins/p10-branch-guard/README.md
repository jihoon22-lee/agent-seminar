# P10 상태를 보고 막는 가드 (branch-guard)

> 구성: 플러그인(JS) `tool.execute.before` + git 상태 조회 | 난이도: ★★★ | 필요: opencode 1.19.5, git, Python 3.10+ (Node 는 단위 테스트에만) | 슬라이드: 플러그인 — 도구 실행 가로채기

## 무엇을 보여 주나

P2(`danger-guard`)는 **명령 문자열의 모양**만 봅니다. 같은 `git commit -m x` 라도 어느 브랜치에서 실행되느냐에 따라 괜찮을 수도, 안 될 수도 있는데 문자열만으로는 알 수 없습니다.

이 가드는 명령이 실행될 폴더에서 **git 에게 현재 브랜치를 직접 물어보고** 판단합니다.

- 현재 브랜치가 `main`/`master` 면 `git commit` 과 `git push` 를 막습니다. (push 는 목적지가 `main`/`master` 인 `git push origin HEAD:main` 도 막습니다.)
- 한 줄 안에서 브랜치가 바뀌는 경우도 따라갑니다. `git switch main && git commit` 은 feature 브랜치에서 시작했어도 막고, `git switch -c feat/y && git commit` 은 main 에서 시작했어도 통과시킵니다(차단 메시지가 권하는 절차를 한 줄로 쓴 형태). `bash -lc "…"`, `cmd /c "…"`, `powershell -Command "…"` 로 감싼 명령도 안쪽을 봅니다. 따라가지 못하는 경우는 아래 "주의할 점"에 있습니다.
- `gh pr create --draft`(`-d`) 와 `gh pr ready --undo` 를 막습니다. 이 규칙은 브랜치와 무관합니다. ("초안 PR 은 만들지 않는다"는 **팀 규칙의 예**일 뿐 일반적인 권장이 아닙니다. 읽는 사람이 자기 팀 규칙으로 바꿔 쓰라고 넣은 것입니다.)
- git 저장소가 아니거나, HEAD 가 detached 이거나, git 이 실패하거나 없으면 **허용하고 이유를 기록**합니다. 판단을 못 하는 상황에서 전부 막으면 에이전트가 멈추기 때문입니다.
- 차단 메시지는 모델에게 **대신 무엇을 하라**고 알려 줍니다(`git switch -c <type>/<name>`, 준비된 PR 열기). 모델은 막힌 채 멈추지 않고 안내대로 돌아섭니다.

## 실무에서는

- "main 에 직접 커밋하지 않는다"는 팀 규칙을 AGENTS.md 에 적는 것만으로는 부족합니다. AGENTS.md 는 모델이 읽는 **부탁**이고, 모델은 긴 작업 중에 잊거나, `--auto` 로 사람이 보지 않는 사이에 어길 수 있습니다. 게다가 AGENTS.md 는 정적이라 지금 어느 브랜치에 있는지 알 수 없어서 "main 일 때만 안 된다"는 조건을 표현할 수 없습니다. 이 가드는 **명령이 실행되기 직전의 실제 상태**를 보고 막습니다. (실제 모델이 얼마나 자주 규칙을 어기는지는 측정하지 않았습니다. 여기서 말하는 것은 "어길 수 있다"와 "코드는 어길 수 없다"의 차이입니다.)
- 둘은 함께 쓰는 것이 좋습니다. AGENTS.md 에는 "작업은 `feat/…` 브랜치에서 한다"고 적어 평소 행동을 이끌고, 가드는 실수했을 때의 마지막 안전장치로 둡니다.
- 같은 방식으로 "운영 브랜치에서 마이그레이션 금지", "작업 트리가 더러우면 배포 금지", "테스트 DB 가 아닌 곳에 연결돼 있으면 쓰기 금지"처럼 **상태에 따라 달라지는 규칙**을 만들 수 있습니다.

## 파일 구성

```
p10-branch-guard/
├── README.md
├── fake_llm.py                          # 검증용 가짜 LLM (표준 라이브러리만, 복사본)
├── check.py                             # 자동 검증 (단위 테스트 + 샌드박스 저장소에서 가짜 모델 실행 + --model 검사)
├── .opencode/plugins/branch-guard.js    # 플러그인 본체 (명령 분해기 + git 조회)
├── tests/guard.test.mjs                 # 임시 git 저장소를 쓰는 훅 단위 테스트 (250건, node + git)
└── logs/                                # 실행하면 생김: branch-guard.log (BLOCKED / ALLOW 이유)
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. (모델 설정이 없다면 무료 모델 `-m opencode/big-pickle` 을 붙이세요.) 실제 모델로는 이번에 돌리지 않아 **미검증**입니다.

1. 먼저 모델 없이 훅만 시험합니다. 임시 폴더에 git 저장소를 여러 개 만들고(main, feature, detached …) 명령 문자열을 훅에 넘겨 봅니다. 명령을 실행하지는 않습니다.

   PowerShell:
   ```powershell
   cd examples\03-plugins\p10-branch-guard
   node tests\guard.test.mjs
   ```
   Linux bash:
   ```bash
   cd examples/03-plugins/p10-branch-guard
   node tests/guard.test.mjs
   ```
   `branch-guard: 250 cases, 0 failed` 가 나오면 정상입니다.

2. **연습용 저장소를 따로 만듭니다.** 이 예제 폴더 자체를 git 저장소로 쓰지 말고 복사본에서 하세요. 가드 동작을 보려면 커밋을 시도해야 하기 때문입니다. 1번에서 들어간 이 예제 폴더에서 이어서 실행하는 명령입니다. (복사본이 이미 있으면 먼저 지웁니다.)

   PowerShell:
   ```powershell
   Remove-Item -Recurse -Force $env:TEMP\guard-demo -ErrorAction SilentlyContinue
   Copy-Item -Recurse . $env:TEMP\guard-demo
   cd $env:TEMP\guard-demo
   git init -b main; git config user.name demo; git config user.email demo.invalid
   git add .; git commit -m init
   ```
   Linux bash:
   ```bash
   rm -rf /tmp/guard-demo
   cp -r . /tmp/guard-demo && cd /tmp/guard-demo
   git init -b main && git config user.name demo && git config user.email demo.invalid
   git add . && git commit -m init
   ```
   (`demo.invalid` 는 이메일 형태가 아닌 자리 채움 값입니다. git 은 이 값으로도 커밋합니다.)
   (이 "init" 커밋은 가드가 로드되기 전이라 가능합니다. opencode 안에서 시키면 첫 커밋도 main 이라 막힙니다.)

3. opencode 를 실행합니다. 처음 실행하면 opencode 가 `.opencode/` 안에 `@opencode-ai/plugin` 을 npm 으로 설치하려고 합니다. 인터넷이 막혀 있고 패키지 미러도 없으면 첫 시작이 70초쯤 멈췄다가 계속 진행됩니다. 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 아주 처음, 새 환경에서의 첫 시작은 약 130초까지 걸렸습니다(패킷을 조용히 버리는 레지스트리면 200초를 넘을 수도 있습니다). 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다. (이 단계는 패키지 미러가 필요할 수 있습니다.)

   ```
   opencode
   ```

4. main 브랜치에서 커밋을 시킵니다.

   `hello.txt 에 hi 라고 쓰고 "add hello" 메시지로 커밋해 줘.` → 커밋이 막히고, 모델이 `git switch -c …` 로 브랜치를 만든 뒤 다시 커밋하면 통과합니다.

   `gh pr create --draft` 는 실제 PR 을 만들 수 있으니 시키지 마세요. 가드는 `gh` 가 없어도 먼저 막으므로 가짜 모델 검증(`python check.py`)으로 확인합니다.

5. 기록 확인:

   PowerShell: `Get-Content -Encoding UTF8 logs\branch-guard.log`
   Linux bash: `cat logs/branch-guard.log`

6. 자동 검증: 3~5번은 연습용 저장소(`guard-demo`)에서 했으므로, 1번과 같은 예제 폴더로 돌아가서 실행합니다. `python check.py` / `python check.py --model` (Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요).

## 기대 결과

아래 출력은 `check.py` 가 쓰는 **가짜 LLM**(`fake_llm.py`)으로 샌드박스의 임시 git 저장소(main 브랜치)에서 실제 `opencode 1.19.5`(Linux)를 실행해 얻은 것입니다. 실제 모델은 **미검증**입니다. 그대로 다시 얻으려면 예제 폴더에서 `CHECK_VERBOSE=1 python3 check.py` 를 실행하세요. `--- scripted run (compound) ---` 와 `--- scripted run (push/draft) ---` 아래에 아래 내용이 나옵니다. 커밋 해시(`8105574` 같은 값)는 실행할 때마다 다릅니다.

가짜 LLM 이 ① `echo hi > x.txt && git add x.txt && git commit -m 'add x'` ② `git switch -c feat/x` ③ ①을 다시, 순서로 실행하려 했을 때 (`check.py` 의 `[복합]` 검사, Linux 만):

```
✗ echo hi > x.txt && git add x.txt && git commit -m 'add x' failed
Error: [branch-guard:protected-branch] 현재 브랜치가 'main' 입니다. main/master 에는 직접 커밋하지 않습니다. 먼저 새 브랜치를 만드세요: git switch -c <type>/<name> (예: git switch -c feat/login-form). 변경한 파일은 그대로 따라옵니다. 그다음 같은 커밋 명령을 다시 실행하세요.

$ git switch -c feat/x
Switched to a new branch 'feat/x'

$ echo hi > x.txt && git add x.txt && git commit -m 'add x'
[feat/x 8105574] add x
 1 file changed, 1 insertion(+)
 create mode 100644 x.txt
```

`check.py` 가 이어서 확인하는 것: `main` 에는 `init` 한 개뿐이고(커밋 안 늘어남) `feat/x` 에 `add x` 가 있습니다. 차단된 명령은 **통째로** 실행되지 않습니다. 이것은 별도의 새 저장소에서 `echo hi > only.txt && git add only.txt && git commit …` 한 줄이 막힌 뒤 `only.txt` 가 없는 것으로 확인합니다(`[복합]` 세 번째 검사). Windows 에서는 PowerShell 5.1 이 `&&` 를 문법 오류로 받기 때문에 이 검사들을 건너뜁니다(`[SKIP]` 한 줄이 나옵니다). 그 대신 같은 일을 `write` 도구와 `git add`, `git commit` 별도 호출로 하는 검사(아래)는 두 OS 에서 모두 돕니다.

같은 일을 명령 하나씩 따로 호출했을 때(두 OS 공통 검사):

```
← Write x.txt
Wrote file successfully.

$ git add x.txt
(no output)

✗ git commit -m "add x" failed
Error: [branch-guard:protected-branch] 현재 브랜치가 'main' 입니다. main/master 에는 직접 커밋하지 않습니다. 먼저 새 브랜치를 만드세요: git switch -c <type>/<name> (예: git switch -c feat/login-form). 변경한 파일은 그대로 따라옵니다. 그다음 같은 커밋 명령을 다시 실행하세요.

$ git switch -c feat/x
Switched to a new branch 'feat/x'

$ git commit -m "add x"
[feat/x eddce22] add x
 1 file changed, 1 insertion(+)
 create mode 100644 x.txt
```

같은 줄에서 브랜치를 바꾸는 명령 (`[전환]` 검사, Linux 만). main 에서 `git switch -c feat/one && … git commit` 한 줄은 통과하고, 그다음 feat/one 에서 `git switch main && … git commit` 한 줄은 막힙니다. 막힌 줄은 `git switch main` 도 실행되지 않아 브랜치가 그대로 `feat/one` 입니다.

```
$ git switch -c feat/one && echo hi > one.txt && git add one.txt && git commit -m 'add one'
Switched to a new branch 'feat/one'
[feat/one 1dd10e3] add one
 1 file changed, 1 insertion(+)
 create mode 100644 one.txt

✗ git switch main && echo hi > two.txt && git add two.txt && git commit -m 'add two' failed
Error: [branch-guard:protected-branch] 이 명령은 먼저 'main' 로 전환한 뒤 커밋합니다. main/master 에는 직접 커밋하지 않습니다. 먼저 새 브랜치를 만드세요: git switch -c <type>/<name> (예: git switch -c feat/login-form). 변경한 파일은 그대로 따라옵니다. 그다음 같은 커밋 명령을 다시 실행하세요.
```

`main` 에서 `git push origin HEAD` 와 `gh pr create --draft --title x --body y`, 그리고 `git push --dry-run`:

```
✗ git push origin HEAD failed
Error: [branch-guard:push-to-protected] 현재 브랜치가 'main' 입니다. main/master 로는 직접 푸시하지 않습니다. 작업 브랜치를 만들어(git switch -c <type>/<name>) 커밋한 뒤 그 브랜치를 푸시하고(git push -u origin <브랜치>), PR 로 합치세요.
✗ gh pr create --draft --title x --body y failed
Error: [branch-guard:draft-pr] 초안(draft) PR 은 만들지 않는 규칙입니다. `--draft`(`-d`) 없이 바로 리뷰할 수 있는 PR 로 여세요: gh pr create --title "<제목>" --body "<설명>". 아직 덜 끝났다면 PR 을 열지 말고 브랜치에서 더 작업하세요.

$ git push --dry-run
fatal: No configured push destination.
Either specify the URL from the command-line or configure a remote repository using

    git remote add <name> <url>

and then push using the remote name

    git push <name>
```

`--dry-run` 은 가드를 통과해서 git 이 직접 답한 것입니다. git 저장소가 아닌 폴더에서 `git commit -m x` 는 가드가 허용하고 git 이 `fatal: not a git repository` 라고 답했습니다(`logs/branch-guard.log` 에 `ALLOW not-a-repo`).

```
$ node tests/guard.test.mjs
branch-guard: 250 cases, 0 failed
$ python3 check.py
== 23 checks, 0 failed, 0 warnings
```

지연: 브랜치를 묻는 git 한 번이 Linux 의 작은 저장소에서 중앙값 2.3ms (최대 7.4ms) 였습니다. git 이 들어 있지 않은 명령(`ls -la`)은 git 을 부르지 않아 0.0ms 입니다. (이 수치는 이번 보강 전에 잰 값이고 다시 재지 않았습니다.)

## 동작 원리

1. 훅은 `tool.execute.before` 에서 `input.tool === "bash"` 일 때 `output.args.command` 를 봅니다. 작업 폴더는 `output.args.workdir` 가 있으면 그것, 없으면 플러그인 입력의 `directory` 입니다.
2. **명령 분해.** 따옴표를 아는 작은 분해기(`tokenize`)가 문자열을 명령 단위로 자릅니다. `;` `&&` `||` `|` `&` 줄바꿈, 괄호, `$(…)`, 백틱이 경계입니다. 따옴표 안의 글자(`echo "git commit"`, `git commit -m "a; git push"`), `#` 주석, heredoc 본문(`cat <<'EOF' … EOF`)은 명령으로 보지 않습니다. 큰따옴표 안의 `$(…)` 는 실제로 실행되므로 안쪽을 따로 분석합니다(`git commit -m "$(cat <<'EOF' … EOF)"` 형태도 커밋으로 인식).
3. **명령 해석.** 각 명령에서 앞의 `NAME=값`, `sudo`, `env`, `time`, `if`/`then` 같은 껍데기를 벗기고, 실행 파일 이름(`git`, `git.exe`, `C:\…\git.exe` 모두)을 봅니다. `git` 이면 `-C <경로>`, `-c k=v`, `--no-pager` 같은 전역 옵션을 건너뛰어 하위 명령을 찾습니다. `cd`, `pushd`, PowerShell 의 `Set-Location`/`sl` 은 이후 명령의 작업 폴더를 바꿉니다(`cd main; cd ../feat; git commit` 은 `feat` 에서 실행되는 것으로 봅니다). `bash -c "…"`(`-lc`, `-ec` 처럼 합친 옵션도), `sh -c`, `zsh`/`fish -c`, `cmd /c "…"`(`/d /s /k` 포함), `powershell`/`pwsh` 의 `-Command`(`-c`, 줄임말)와 `-EncodedCommand`(base64 를 풀어서), `eval`, `Invoke-Expression` 의 인자는 다시 분석합니다.
   **브랜치 전환 추적.** `git switch`/`git checkout` 도 `cd` 처럼 같은 줄 안에서 순서대로 따라갑니다. 목적지가 보호된 브랜치면 뒤따르는 `commit`/`push` 를 막고, `-c`/`-C`/`-b`/`-B`/`--orphan` 으로 새 브랜치를 만들거나 `--detach` 하면 뒤따르는 명령은 그 브랜치 기준으로 판단합니다. 전환은 그 저장소 폴더에서만 유효합니다(`git -C other switch main` 은 `other` 에만 영향). `git checkout x` 는 `x` 가 브랜치인지 경로인지 문자열만으로는 모르므로, 보호된 브랜치 이름이거나 `git show-ref` 로 실제 로컬 브랜치임이 확인될 때만 전환으로 봅니다. 목적지를 알 수 없으면(`git switch -`, `@{-1}`, `HEAD~1`, `$VAR`, 경로) **전환이 없었던 것처럼 명령 시작 때의 브랜치로 판단**하고 `logs/branch-guard.log` 에 `NOTE switch-destination-unknown` 을 남깁니다.
   **`push` 의 `@`.** `git push origin @` 의 `@` 는 `HEAD` 와 같아서 현재 브랜치로 계산합니다.
   **`gh`.** `gh pr create` 와 별칭 `gh pr new` 의 `--draft`, `-d`, 합친 짧은 옵션(`-dt 제목`, `-fd`)을 봅니다. 값을 받는 짧은 옵션 뒤에 붙은 글자는 값으로 보므로 `-tdraft`(제목이 `draft`)는 막지 않습니다. `gh -R 소유자/저장소 pr …` 도 봅니다.
4. **브랜치 조회.** 해당 폴더에서 `git symbolic-ref -q --short HEAD` 를 **셸 없이 인자 배열**로 실행합니다(5초 제한). 성공하면 브랜치 이름, 종료 코드 1 이고 오류 출력이 없으면 detached HEAD, `not a git repository` 면 저장소 아님입니다. 폴더가 없거나 git 이 없거나 시간 초과여도 마찬가지로 허용하고 `logs/branch-guard.log` 에 `ALLOW <이유> :: <명령>` 을 남깁니다. 차단은 `BLOCKED rule=<id> :: <명령>` 입니다.
5. **무해한 형태는 통과.** `git commit --help/-h/--dry-run`, `git push --dry-run/-n/--help`, `git push --tags`(브랜치 없이 태그만), `git commit-graph`·`git commit-tree`(다른 하위 명령)는 막지 않습니다. `main` 에 있어도 `git push origin feat/x` 처럼 **다른 브랜치를 명시**해 올리는 push 는 허용합니다. 반대로 feature 브랜치에서도 `git push origin HEAD:main`, `git push origin :main`(삭제), `git push --all/--mirror` 는 막습니다.
6. 보호할 브랜치는 기본 `main,master` 이고 `BRANCH_GUARD_PROTECTED=main,release/1.0` 처럼 바꿀 수 있습니다.

## 직접 바꿔 보기

1. `BRANCH_GUARD_PROTECTED` 에 `develop` 을 추가하고 `tests/guard.test.mjs` 에 `develop` 브랜치 사례를 넣어 보세요.
2. `git merge`, `git cherry-pick`, `git revert`, `git am` 도 커밋을 만듭니다(아래 한계 참고). `scan()` 의 `if (g.sub === "commit" …)` 조건에 하위 명령 이름을 추가하고 테스트 사례를 넣어 보세요.
3. `deny("draft-pr", …)` 를 지우고 `gh pr create` 에 `--draft` 가 없으면 `--label` 이 있는지 보는 식으로 PR 규칙을 바꿔 보세요.
4. `currentBranch()` 가 반환하는 `skip` 사례(저장소 아님, detached …)를 허용 대신 차단으로 바꾸면 무슨 일이 생기는지 `tests/guard.test.mjs` 의 어떤 사례가 깨지는지로 확인해 보세요. "판단 못 하면 허용"이 왜 기본값인지 보입니다.

## 주의할 점 / 문제 해결

이 가드는 **실수 방지**이지 보안 경계가 아닙니다. 아래는 알고 있는 한계이고, 단위 테스트는 여기에 적은 막는 것/허용하는 것을 확인합니다.

- **다른 경로로 커밋을 만드는 명령은 보지 않습니다.** `git merge`, `git cherry-pick`, `git revert`, `git am`, `git rebase` 는 현재 브랜치에 커밋을 만들 수 있는데 막지 않습니다. `git commit-tree` + `git update-ref`, 스크립트 안의 git 호출(`make release`, `npm version`, `python -c "subprocess.run(['git','commit'…)"`), git 별칭(`git ci`)도 못 잡습니다.
- **같은 줄 안의 브랜치 전환은 위의 규칙으로만 따라갑니다.** 따라가지 못하는 것: `git switch -`·`@{-1}`·변수로 정한 목적지(시작 브랜치로 판단하고 `NOTE` 만 남김), 같은 줄에서 `git branch x && git checkout x` 처럼 방금 만든 브랜치로의 `git checkout`(git 이 아직 모르는 이름이라 경로로 보고 무시. `git switch x` 는 알 수 있음), `git checkout 커밋해시` 로 detached 가 되는 것, 앞선 명령이 실패해 전환이 일어나지 않은 경우(`git switch 없는브랜치 ; git commit`)와 `||` 로 이은 분기. `;` `&&` `||` 를 구분하지 않고 모두 "앞에서부터 차례로 성공한다"고 계산합니다.
- **껍데기 안의 명령은 문자열일 때만 풉니다.** `bash -lc`, `sh -c`, `cmd /c`, `powershell -Command`, `-EncodedCommand` 는 보지만 `bash script.sh`, `bash -s <<EOF`, `powershell -File x.ps1`, `cmd /c x.bat`, `wsl …`, `docker exec …`, `ssh host "…"`, `xargs`, `find -exec` 는 안쪽을 보지 못합니다. 별칭(`git ci`), 스크립트와 `make`, 파이썬·노드 안의 git 호출도 마찬가지입니다. 중첩은 4단계까지만 풉니다.
- **`git -C 다른/저장소` 는 처리합니다**(그 폴더의 브랜치를 묻습니다). 다만 `git --git-dir=… --work-tree=…` 는 폴더로 환산하지 않고 현재 폴더 기준으로 판단합니다.
- **셸 문법의 일부만 압니다.** `cd "$DIR"` 처럼 변수가 든 경로는 풀지 못해 폴더가 없다고 보고 허용합니다. `( cd x; … )` 서브셸의 폴더 변경이 바깥으로 새는 것으로 계산합니다. `pushd`/`popd` 스택은 따라가지 않습니다. `xargs`, `find -exec` 로 실행되는 git, `bash <<EOF` 로 넘기는 heredoc 스크립트는 분석하지 않습니다. PowerShell 의 백틱 이스케이프(`` `" ``)와 `""` 로 겹친 따옴표, `Start-Process git -ArgumentList commit` 도 다루지 못합니다.
- **push 의 목적지는 명령에 적힌 것만 봅니다.** `git push`(인자 없음)가 설정(`push.default`, 추적 브랜치)에 따라 `main` 으로 가더라도, 현재 브랜치가 `main` 이 아니면 허용합니다. 원격 쪽 브랜치 보호(GitHub 의 branch protection)는 그대로 필요합니다.
- **`gh` 는 `gh pr create` 와 `gh pr ready --undo` 만 봅니다.** `gh api … -f draft=true`, 웹 UI, 다른 도구로 만드는 초안 PR 은 못 막습니다. 가드 테스트는 `gh` 없이도 문자열만으로 판정하므로 `gh` 설치 여부와 무관합니다.
- **새 저장소(`git init` 직후)의 첫 커밋도 `main`/`master` 면 막힙니다**(커밋이 없어도 HEAD 는 `main` 을 가리키며, 테스트로 확인). 의도된 동작입니다. 해결: 먼저 `git switch -c <type>/<name>` 으로 브랜치를 만든 뒤 커밋하세요(변경한 파일은 그대로 따라옵니다). 사람이 터미널에서 직접 첫 커밋을 하는 것은 가드와 무관합니다.
- `git commit -m "--dry-run"` 처럼 옵션 이름과 같은 **메시지 값**은 `--dry-run` 플래그로 오해해 허용합니다(따옴표를 벗긴 뒤 단어로 비교하기 때문). 반대로 큰따옴표 안의 `$(git commit …)` 는 실제로 실행되므로 막습니다.
- 탐지 못 한 명령이 있어도 **에이전트를 멈추지는 않도록** 설계했습니다. 분해기가 예외를 내도 `ALLOW parse-error` 를 기록하고 허용합니다.
- 윈도의 bash 도구는 Git Bash 가 아니라 **Windows PowerShell 5.1** 입니다. 이 가드는 `git.exe`, `& git`, `Set-Location`, `;` 구분 형태의 테스트를 포함합니다. **Windows 에서의 확인**: 네이티브 Windows(Windows Python 3.12, Windows 용 opencode 1.19.5, bash 도구는 PowerShell 5.1)에서 `check.py` 16건(`&&` 복합 명령을 쓰는 `[복합]`·`[전환]`·`[껍데기]` 검사는 건너뜀)과 단위 테스트(250건)가 통과했습니다. 거기서 가짜 모델이 PowerShell 로 `git commit` 을 실행했을 때 main 에서는 막히고 feature 브랜치에서는 실제로 커밋됐습니다. PowerShell 5.1 은 `&&` 를 받지 않고 `echo hi > 파일` 이 UTF-16 으로 쓰기 때문에, `check.py` 는 명령을 한 줄에 하나씩 따로 호출하고 파일은 `write` 도구로 만듭니다. `&&` 로 이은 복합 명령은 Windows 에서는 셸을 거치지 않는 단위 테스트에서만 확인하고, Linux 에서는 `check.py` 가 실제 bash 로도 실행해 확인합니다. `cmd /c "…"` 형태의 실제 PowerShell 실행은 **미검증**입니다. 실제 모델과 PowerShell 7 은 **미검증**입니다.
- **export 는 플러그인 함수만 하세요.** 숫자·문자열·객체 같은 함수가 아닌 값(`export const X = 1`)을 export 하면 opencode 가 **파일 전체를 건너뜁니다.** 평소 실행에는 아무 출력도 없고 `opencode --print-logs` 에만 `Plugin export is not a function` 오류가 보입니다. 보조 함수를 export 하면 그 함수까지 플러그인으로 호출됩니다. 그래서 `tokenize`, `scan` 은 export 하지 않고, 테스트는 플러그인을 불러와 훅을 호출합니다. `.opencode/plugins/` 안의 모든 `.js` 가 플러그인으로 로드되므로 테스트 파일은 그 폴더 밖(`tests/`)에 둡니다.
- `node` 나 `git` 이 없으면 `check.py` 가 경고(WARN)를 내고 해당 검사를 건너뜁니다. opencode 실행에는 Node 가 필요 없습니다.
