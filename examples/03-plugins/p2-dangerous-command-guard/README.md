# P2 위험한 명령 차단 플러그인 (dangerous-command-guard)

> 구성: 플러그인(JS) `tool.execute.before` + 규칙 표 | 난이도: ★★☆ | 필요: opencode 1.19.5, Node(단위 테스트용, 선택) | 슬라이드: 플러그인 — 도구 실행 가로채기

## 무엇을 보여 주나

에이전트가 `bash` 도구로 실행하려는 명령 문자열을 실행 직전에 검사해서 `rm -rf /`, `git push --force`, `git reset --hard`, `DROP TABLE` 같은 되돌릴 수 없는 명령을 막는 플러그인입니다.
핵심은 **규칙 표(`RULES`)** 입니다. 규칙은 `{ id, pattern, message }` 한 덩어리이고, 한 줄만 추가하면 새 위험 명령을 막을 수 있습니다.
그리고 이 정규식들은 모델을 부르지 않고도 `node` 로 수십 개 사례를 한 번에 시험할 수 있습니다.

## 실무에서는

- 에이전트에게 `--auto`(권한 자동 승인)를 주고 오래 일을 시킬 때, 사람이 일일이 보지 못하는 동안의 마지막 안전장치로 씁니다.
- "force push 는 절대 안 된다", "운영 DB 로는 DROP 을 못 한다" 같은 팀 규칙을 문서 대신 코드로 강제합니다.
- 차단 메시지에 "대신 `git restore <경로>` 를 쓰세요"처럼 안전한 대안을 적어 두면, 모델이 막힌 채 멈추지 않고 안전한 방법으로 돌아갑니다.

## 파일 구성

```
p2-dangerous-command-guard/
├── README.md
├── fake_llm.py                       # 검증용 가짜 LLM (표준 라이브러리만, 복사본)
├── check.py                              # 자동 검증 (단위 테스트 + 플러그인 로드 + --model 모델 검사)
├── .opencode/plugins/danger-guard.js     # 플러그인 본체 (RULES 표가 이 안에 있음)
├── tests/matcher.test.mjs                # 규칙 표를 실제 훅으로 시험 (차단 47건 + 허용 36건, node)
└── logs/                                 # 실행하면 생김: plugin-load.log, danger-guard.log
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. (모델 설정이 없다면 무료 모델 `-m opencode/big-pickle` 을 붙이세요.)

1. 먼저 모델 없이 규칙 표만 시험해 봅니다. 명령을 실행하는 것이 아니라 훅에 문자열을 넘겨 보기만 합니다.

   PowerShell:
   ```powershell
   cd examples\03-plugins\p2-dangerous-command-guard
   node tests\matcher.test.mjs
   ```
   Linux bash:
   ```bash
   cd examples/03-plugins/p2-dangerous-command-guard
   node tests/matcher.test.mjs
   ```
   `danger-guard: 47 deny cases, 36 allow cases, 0 failed` 가 나오면 정상입니다.

2. opencode 를 실행합니다. 처음 실행하면 opencode 가 `.opencode/` 안에 `@opencode-ai/plugin` 을 npm 으로 설치하려고 합니다. 인터넷이 막혀 있고 패키지 미러도 없으면 첫 시작이 70초쯤 멈췄다가 계속 진행됩니다. 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다.

   ```
   opencode
   ```

3. **안전하게** 차단을 확인하려면, 실행돼도 아무 일 없는 명령으로 시험하세요. `echo` 는 SQL 문장을 출력만 합니다.

   - `bash 도구로 정확히 이 명령을 실행해 줘: echo DROP TABLE users;` → 차단
   - `bash 도구로 정확히 이 명령을 실행해 줘: echo hello-guard` → 통과

   (진짜 `rm -rf /` 를 시켜 보지 마세요. 플러그인이 로드되지 않은 상태라면 실제로 실행될 수 있습니다.)

4. 차단 기록 확인:

   PowerShell: `Get-Content logs\danger-guard.log`
   Linux bash: `cat logs/danger-guard.log`

5. 자동 검증: `python check.py` / `python check.py --model` (Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요).

## 기대 결과

아래 출력은 `check.py` 가 쓰는 **가짜 LLM**(`fake_llm.py`: 정해진 도구 호출을 대신 수행하는 OpenAI 호환 서버, 표준 라이브러리만 사용)으로 실제 `opencode 1.19.5` 를 실행해 얻은 것입니다. 모델이 무엇을 시키든 플러그인이 어떻게 반응하는지를 매번 똑같이 재현할 수 있습니다. 실제 모델(무료 모델)로는 이번 확인 시점에 한도 초과/시간 초과로 결과를 얻지 못해 **미검증**입니다. 평소 쓰는 모델로 해 보면 모델의 말투와 시도 순서는 다르겠지만 차단/기록 동작은 같아야 합니다.

가짜 LLM 이 `echo DROP TABLE users;` 와 `echo guard-ok-123` 을 차례로 실행하려 했을 때(Linux, Windows 동일):

```
> build · echo

✗ echo DROP TABLE users; failed
Error: [danger-guard:sql-drop] DROP TABLE/DATABASE/SCHEMA 는 데이터를 영구 삭제합니다. 이 에이전트에서는 실행할 수 없으니, 필요한 SQL 을 파일로 작성해 사용자가 직접 검토 후 실행하도록 안내하세요.

$ echo guard-ok-123
guard-ok-123
```

`logs/danger-guard.log`:

```
2026-11-16T17:10:11.480Z BLOCKED rule=sql-drop :: echo DROP TABLE users;
```

단위 테스트:

```
$ node tests/matcher.test.mjs
danger-guard: 47 deny cases, 36 allow cases, 0 failed
```

## 동작 원리

1. 플러그인은 `async ({ directory }) => 훅 객체` 를 export 하고, `tool.execute.before(input, output)` 에서 `input.tool === "bash"` 일 때 `output.args.command` 를 검사합니다. (`bash` 도구의 인자 키는 `command`, `description` 입니다.)
2. `RULES` 를 순서대로 훑어 `pattern` 에 걸리고 `unless` 에는 걸리지 않는 첫 규칙을 찾습니다. 찾으면 `logs/danger-guard.log` 에 기록한 뒤 `throw new Error("[danger-guard:<id>] <메시지>")` 합니다. 도구는 실행되지 않고 모델은 그 메시지를 오류로 받습니다.
3. 정규식에는 몇 가지 약속이 있습니다.
   - `[^;&|\n]*` 로 한 명령 안에서만 옵션을 찾습니다. `echo hi; rm -rf /` 처럼 `;`·`&&`·`|` 뒤에 붙은 명령도 잡지만, 앞 명령의 옵션이 뒤 명령으로 넘어가지는 않습니다.
   - 옵션 순서와 묶음에 상관없이 잡습니다: `rm -rf`, `rm -fr`, `rm -r -f`, `rm --recursive`, `git push -fu`, `git clean -xdf`.
   - 지울 대상은 `/`, `/*`, `~`, `~/*`, `$HOME`, `*`, `./*`, `.` 같은 "너무 큰 경로"만 봅니다. 그래서 `rm -rf build`, `rm -rf *.pyc`, `rm -rf /tmp/demo-build` 는 통과합니다.
   - `git push --force-with-lease` 와 `git clean -n`(미리보기)처럼 안전한 변형은 허용합니다.
   - PowerShell: `Remove-Item -Recurse -Force C:\`, `ri`, `$env:USERPROFILE`, `rd /s /q C:\` 도 봅니다. 윈도에서 bash 도구는 Windows PowerShell 5.1 이기 때문입니다.
4. **규칙 추가하는 법**: `RULES` 배열에 한 항목을 넣으면 됩니다.

   ```js
   {
     id: "docker-prune-all",
     pattern: /\bdocker\s+system\s+prune\b[^;&|\n]*\s-a\b/i,
     message: "docker system prune -a 는 쓰지 않는 이미지를 모두 지웁니다. docker image ls 로 확인 후 지울 이미지를 지정하세요.",
   },
   ```
   그리고 `tests/matcher.test.mjs` 의 `deny`/`allow` 표에 사례를 추가해 `node tests/matcher.test.mjs` 로 확인합니다. "막아야 하는 것"과 "막으면 안 되는 것"을 함께 적는 것이 중요합니다. (`truncate -s 0 app.log` 는 리눅스 명령이므로 SQL `TRUNCATE` 규칙이 걸리지 않게 테이블 이름이 따라올 때만 봅니다.)

### config 만으로 하는 방법과 비교: `permission.bash` vs 플러그인

`opencode.json` 의 `permission.bash` 로도 명령별 허용/거부를 정할 수 있습니다. 이 저장소의 `examples/00-config/c5-permissions` 가 그 예제입니다.

```json
{ "permission": { "bash": { "*": "ask", "git status*": "allow", "rm *": "deny" } } }
```

| | `permission.bash` (설정) | 이 플러그인 (코드) |
|---|---|---|
| 작성 | JSON 몇 줄, 코드 필요 없음 | JS 와 정규식, 테스트 필요 |
| 판정 | 명령 문자열을 `*` 와일드카드 패턴과 비교 | 임의의 코드: 옵션 순서·묶음 옵션·`;` 뒤 명령·예외(`unless`) |
| 결과 | `allow` / `ask`(사람에게 물음) / `deny` | 차단(throw) 또는 통과. 사람에게 묻는 동작은 없음 |
| 메시지 | opencode 기본 거부 메시지 | 이유와 대안을 담은 한국어 안내를 모델에게 직접 전달 |
| 기록 | 없음 | 마음대로 (이 예제는 `danger-guard.log`) |
| 시험 | opencode 를 실행해야 확인 | 모델 없이 `node` 로 수십 사례를 한 번에 |
| 배포 | `opencode.json` 한 파일 | `.opencode/plugins/` 아래 파일 (프로젝트에 복사) |

고르는 기준:

- **설정으로 충분하면 설정을 쓰세요.** "`git push` 는 물어봐라", "`rm` 은 거부", "`git status` 는 허용"처럼 명령 앞부분으로 구분되는 규칙은 `permission.bash` 가 가장 단순하고, `ask` 로 사람에게 확인받을 수 있다는 장점이 있습니다.
- **플러그인은 패턴 하나로 표현이 안 될 때** 씁니다. `git push` 는 허용하되 `-f`/`--force` 는 막고 `--force-with-lease` 는 허용하기, `rm` 의 옵션 순서가 바뀌어도 막기, 명령 안의 `DROP TABLE` 을 대소문자 구분 없이 막기, 차단된 시도를 기록으로 남기기, 팀 규칙을 단위 테스트로 고정하기가 그런 경우입니다.
- 둘은 함께 쓸 수 있습니다. 설정으로 큰 틀(기본 `ask`)을 잡고, 플러그인으로 정말 위험한 몇 가지를 코드로 못 박는 구성이 현실적입니다. 이 예제의 `tool.execute.before` 는 권한 확인보다 **먼저** 실행되는 것을 관찰했습니다 (같은 명령에서 `tool.execute.before` → `permission.asked` 순서).

## 직접 바꿔 보기

1. 위의 `docker-prune-all` 규칙을 `RULES` 에 추가하고 `deny`/`allow` 사례를 넣어 `node tests/matcher.test.mjs` 를 통과시켜 보세요.
2. `git-push-force` 규칙에서 `--force-with-lease` 도 막고 싶다면 정규식을 어떻게 바꿔야 할지, 그리고 `allow` 표의 어느 사례가 깨지는지 확인해 보세요.
3. `git-clean-force` 규칙의 `unless` 줄을 지우고 테스트를 돌려, 미리보기 사례(`git clean -nfd`, `git clean --dry-run -fd`)가 왜 깨지는지 확인해 보세요. `unless` 가 하는 일이 눈에 보입니다.

## 주의할 점 / 문제 해결

- **명령 문자열만 봅니다.** `psql -f cleanup.sql` 처럼 파일 안에 있는 `DROP TABLE` 이나, `python -c "shutil.rmtree('/')"` 같은 우회는 막지 못합니다. 따옴표 안의 글자도 구분하지 않아서 `git commit -m "rm -rf / 금지"` 같은 명령도 막힐 수 있습니다. 정규식 필터는 실수 방지용이지 보안 경계가 아닙니다.
- **export 는 플러그인 함수만 하세요.** 상수나 보조 함수를 export 하면 opencode 가 그것도 플러그인으로 호출하다가 오류 메시지 없이 파일 전체를 건너뜁니다. 그래서 `RULES` 는 export 하지 않고, 테스트는 플러그인을 불러와 훅을 호출합니다. `.opencode/plugins/` 안의 모든 `.js` 가 플러그인으로 로드되므로 테스트 파일도 그 폴더 밖(`tests/`)에 둡니다.
- 윈도의 bash 도구는 Git Bash 가 아니라 **Windows PowerShell 5.1** 입니다. 모델이 쓰는 명령도 `Remove-Item`, `Get-Content` 같은 PowerShell 문법이 됩니다.
- `node` 가 없으면 `check.py` 가 경고(WARN)를 내고 단위 테스트를 건너뜁니다. opencode 실행에는 Node 가 필요 없습니다.
- 차단 시험을 `rm -rf /` 같은 진짜 명령으로 하지 마세요. 플러그인이 로드되지 않았다면 실제로 실행됩니다. `echo` 로 문장만 출력하는 방식이 안전합니다.
