# M13 이미 있는 CLI를 읽기 전용 도구로 감싸기 (git)

> 구성: Python 서버 1개 + 연습용 git 저장소 생성기 | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, git | 슬라이드: MCP — 기존 도구 연결

## 무엇을 보여 주나

지금까지의 MCP 예제는 서버가 데이터를 직접 들고 있었다. 실무에서는 반대인 경우가 더 많다. **이미 있는 명령줄 도구를 에이전트가 쓰게 하고 싶다.**
이 예제는 `git` 을 감싸서 `git_log`, `git_blame`, `git_diff_stat` 세 가지 읽기 전용 도구로 내놓는다.

기능은 `subprocess.run` 몇 줄이면 끝난다. 이 예제의 요점은 **모델이 보낸 문자열을 명령줄에 넣는 순간 생기는 문제를 어떻게 막느냐**다. 아래 일곱 가지를 각각 `check.py` 가 확인한다.

| # | 막으려는 것 | 이 서버의 방법 |
|---|---|---|
| 1 | 입력이 셸 명령으로 해석됨 | 인자 리스트로 실행, 셸을 쓰지 않는다 |
| 2 | 옵션 주입 (`--output=파일`) | `-`로 시작하는 값 거부, 경로 앞에 `--` |
| 3 | 저장소 밖 파일 읽기 | 경로를 `resolve()`로 풀어서(`..`, 심볼릭 링크 포함) 저장소 안인지 확인, 절대 경로 거부 |
| 4 | 끝없이 긴 출력 | 40줄에서 자르고 `…(N줄 생략)` 표시 |
| 5 | 멈춘 프로세스 | 10초 제한 |
| 6 | 실패를 성공처럼 전달 | 0이 아닌 종료 코드 → `isError: true` + stderr 문장 |
| 7 | 환경마다 달라지는 출력 | `--no-color`, `--format` 직접 지정, `-c core.quotepath=false`, UTF-8로 읽기 |

## 실무에서는

- **팀이나 조직 안에서만 쓰는 CLI를 에이전트에게 열어 줄 때의 기본 모양**이다. 빌드 시스템(`상태/로그 조회`), 테스트 러너(`실패한 테스트 목록`), 정적 분석기(`경고 요약`)처럼 이미 명령줄이 있는 도구는 `git` 자리에 그 CLI를 넣고 같은 방어를 하면 된다. 서버가 하는 일은 "CLI가 할 수 있는 것 중 읽기 전용 일부만, 검증된 인자로, 크기를 제한해서" 내놓는 것이다.
- **MCP 대신 스킬이 더 싼 경우도 많다.** "이 CLI를 이렇게 실행하라"고 `SKILL.md` 에 적어 두고 모델이 `bash` 로 직접 실행하게 하면, 서버 코드를 짤 필요가 없고 항상 컨텍스트에 올라가는 것도 이름과 설명 한 줄뿐이다(X1 비교 참고). 이 방식의 약점은 모델이 명령줄을 **자기 마음대로 조립한다**는 것이다. `bash` 를 열면 `git push` 나 `--output=` 같은 인자를 인자 단위로 검증할 방법이 없고, 막으려면 권한 패턴(C5)에 기대야 한다.
- 그래서 MCP 래퍼가 값을 하는 때는 정해져 있다: **(1) 입력 검증이 필요할 때** (이 예제의 2~3번), **(2) 열어 주는 범위를 좁히고 싶을 때** (읽기 전용 세 동작만, `bash` 권한은 끄고), **(3) 여러 에이전트나 사람이 같은 도구를 공유할 때**. 셋 다 해당하지 않는다면 스킬이 더 싸다. 반대로 도구가 많아지면 MCP는 도구마다 스키마가 매 요청에 붙는 비용이 있다.

## 파일 구성

```
m13-wrap-cli/
  README.md        이 문서
  server.py        MCP 서버: git_log, git_blame, git_diff_stat (작업 폴더의 저장소가 대상)
  prepare.py       sandbox/ 에 연습용 git 저장소를 만든다 (커밋 7개, 작성자 dev-alpha / dev-beta)
  opencode.json    mcp.repo: ["python", "server.py"]
  check.py         자동 검증
  fake_llm.py      가짜 LLM 서버 (check.py 가 모델 없이 도구 호출을 재현하는 데 씀)
  sandbox/         (prepare.py 가 생성, .gitignore 대상) 연습용 저장소 + server.py/opencode.json 복사본
```

### 왜 sandbox/ 안에서 실행하나

서버는 **자기가 실행된 폴더의 저장소**를 대상으로 한다(저장소 경로를 인자로 받는 방법도 있지만 검증할 값이 하나 늘어난다). 그래서 `prepare.py` 가 `sandbox/` 를 독립된 git 저장소로 만들고, `server.py` 와 `opencode.json` 을 거기에 복사한다(이력에는 넣지 않는다). opencode 를 `sandbox/` 에서 실행하면 `python server.py` 가 그 저장소를 본다. 이렇게 하면 이 레포의 진짜 이력이 예제에 섞이지 않는다. 실무에서 쓸 때는 `server.py` 를 한 곳에 두고, 저장소 안에서 opencode 를 실행하면서 `command` 에 서버의 절대 경로를 적는다.

## 따라 하기

> Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`opencode.json` 의 `command` 도 `["python3", "server.py"]` 로. 수정한 뒤에는 `prepare.py` 를 다시 실행해 `sandbox/` 로 복사한다.)

**1. 연습용 저장소 만들기**

```powershell
cd examples\02-mcp\m13-wrap-cli
python prepare.py
cd sandbox
```

```bash
cd examples/02-mcp/m13-wrap-cli
python3 prepare.py
cd sandbox
```

**2. 에이전트 없이 서버에 JSON 줄 넣어 보기** (`sandbox/` 안에서)

```powershell
python server.py
```

```bash
python3 server.py
```

붙여 넣을 줄:

```
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"git_blame","arguments":{"file":"src/pricing.py","start_line":14,"end_line":16}}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"git_diff_stat","arguments":{"from":"--output=x","to":"HEAD"}}}
```

**3. opencode 로 연결 확인과 질문** (`sandbox/` 안에서)

```powershell
opencode mcp list
opencode run -m opencode/big-pickle --auto "src/pricing.py 의 tax 함수를 반올림으로 고친 사람이 누구고 언제인지 알려줘"
```

```bash
opencode mcp list
opencode run -m opencode/big-pickle --auto "src/pricing.py 의 tax 함수를 반올림으로 고친 사람이 누구고 언제인지 알려줘"
```

이 단계는 평소 쓰는 모델이나 무료 모델이 필요하다. 인터넷이나 패키지 미러는 필요 없다.

## 기대 결과

`python prepare.py` (해시는 고정 날짜·작성자 덕에 항상 같다):

```
4bf37a5 dev-alpha 2026-03-16 README에 설계 메모 안내 추가
668e1e6 dev-beta 2026-03-13 할인 함수 설명 문구 정리
0abe8c3 dev-alpha 2026-03-12 정액 쿠폰과 상한 추가
7e2e1a3 dev-beta 2026-03-09 설계 메모 추가
96c2730 dev-alpha 2026-03-06 세금 계산을 반올림으로 수정
288ebe8 dev-beta 2026-03-04 수량 할인과 최종 금액 계산 추가
3b1b74c dev-alpha 2026-03-02 가격 계산 모듈 초기 버전
```

도구 호출 결과(Linux, git 2.53.0, `sandbox/` 에서):

```
git_log {path: "src/pricing.py", max_count: 3}
668e1e6  2026-03-13  dev-beta  할인 함수 설명 문구 정리
0abe8c3  2026-03-12  dev-alpha  정액 쿠폰과 상한 추가
96c2730  2026-03-06  dev-alpha  세금 계산을 반올림으로 수정

git_diff_stat {from: "HEAD~4", to: "HEAD"}
 README.md      |  2 ++
 docs/설계.md   |  5 +++++
 src/pricing.py | 16 +++++++++++++++-
 3 files changed, 22 insertions(+), 1 deletion(-)

git_blame {file: "src/pricing.py", start_line: 1, end_line: 60}   (53줄짜리 파일)
^3b1b74c (dev-alpha 2026-03-02  1) """주문 금액 계산 모듈 (연습용)."""
...(40번 줄까지)
…(13줄 생략)

git_diff_stat {from: "--output=x", to: "HEAD"}                     -> isError: true
'from' 값은 '-'로 시작할 수 없습니다 (옵션 주입 방지): '--output=x'

git_diff_stat {from: "nope", to: "HEAD"}                           -> isError: true
git이 종료 코드 128로 실패했습니다: fatal: bad revision 'nope'
```

`opencode mcp list` (sandbox/ 에서):

```
●  ✓ repo connected
│      python server.py
```

가짜 모델이 `repo_git_log` → `repo_git_blame` 을 부르게 한 `opencode run` 의 화면(`check.py` 가 하는 것):

```
⚙ repo_git_log {"path":"src/pricing.py","max_count":5}
⚙ repo_git_blame {"file":"src/pricing.py","start_line":14,"end_line":16}
```

도구 이름이 `repo`(서버 이름) + `_` + `git_log` 라서 `repo_git_log` 가 된다.

## 동작 원리

JSON-RPC 부분은 M1 과 같다. 달라진 것은 `tools/call` 의 안쪽이다. 모델의 인자가 도구까지 가는 길:

```
모델 인자 → check_value(빈 값, '-' 시작, 제어 문자) → check_path(절대 경로, resolve 후 저장소 안?)
          → run_git(인자 리스트, 고정 옵션, 10초) → 종료 코드 확인 → clip(40줄) → 모델
```

- **1. 셸을 거치지 않는다.** `subprocess.run(["git", "diff", old, new, "--"])` 처럼 인자 리스트를 주면 각 원소가 git 의 인자 하나다. `old` 에 `; rm -rf ~` 가 들어 있어도 그냥 이상한 리비전 이름일 뿐이다. 서버 소스에 `shell=True` 가 없는지도 `check.py` 가 본다.
- **2. 옵션 주입은 셸이 없어도 일어난다.** 셸을 안 써도, 값이 `-` 로 시작하면 git 이 옵션으로 읽는다. 읽기 전용 명령 `git diff --stat` 에 `--output=pwned.txt` 를 넘기면 **실제로 파일이 써진다**(`check.py` 가 이 대조 실험을 한다). 그래서 `-` 로 시작하는 값은 거부하고, 경로는 `--` 뒤에만 둔다. 리비전 자리에는 `--` 를 둘 수 없어서 이 서버는 거부로 막는다.
- **3. 경로 검사는 문자열 비교가 아니라 `resolve()` 다.** `src/../../server.py` 는 `..` 가 중간에 있어서 `startswith("..")` 로는 못 잡는다. `(저장소 / 경로).resolve()` 로 실제 위치를 구한 뒤 `relative_to(저장소)` 가 되는지 본다. 심볼릭 링크가 저장소 밖을 가리켜도 `resolve()` 가 따라가므로 걸러진다.
- **4. 줄 수 제한은 알려야 한다.** 조용히 자르면 모델은 40줄이 전부인 줄 안다. `…(13줄 생략)` 을 붙이고, `git_blame` 의 도구 설명에도 "한 번에 최대 40줄, `start_line/end_line` 으로 나눠서" 라고 적어서 모델이 다음 행동을 알게 한다.
- **5. 시간 제한.** `subprocess.run(..., timeout=10)`. 시간이 넘으면 자식 프로세스를 죽이고 `isError` 로 알린다. (opencode 의 도구 호출 제한 60초보다 먼저 끝나야 모델이 이유를 읽는다.)
- **6. 실패는 프로토콜 오류가 아니라 도구 오류다.** 없는 리비전은 `isError: true` 와 `fatal: bad revision 'nope'` 문장으로 돌려준다. M1 에서 본 것처럼 모델이 읽고 스스로 고친다.
- **7. 출력 모양을 고정한다.** 사람이 쓰는 git 출력은 설정에 따라 색, 페이저, 한글 이스케이프가 달라진다. 이 서버는 `-c core.quotepath=false`(한글 파일명이 `"docs/\354\204\244..."` 로 나오는 것을 막음. `check.py` 가 대조 실험을 한다), `-c color.ui=never`, `-c core.pager=cat`, `--format=...`, `LC_ALL=C`(오류 문구를 영어로 고정)를 항상 붙이고 출력은 UTF-8 로 읽는다. 읽기 전용이므로 `GIT_OPTIONAL_LOCKS=0` 도 준다.

`git_diff_stat` 에는 `--no-ext-diff --no-textconv` 도 붙는다. 저장소 설정에 외부 diff 프로그램이 적혀 있어도 실행되지 않게 하려는 것이다. (이 부분은 설정 항목으로만 확인했고, 실제로 외부 프로그램을 실행시켜 보는 시험은 하지 않았다.)

## 직접 바꿔 보기

1. **방어 하나 빼 보기** — `check_value` 에서 `startswith("-")` 검사를 지우고 `git_diff_stat` 에 `{"from":"--output=pwned.txt","to":"HEAD"}` 를 보낸다. 읽기 전용 도구가 `sandbox/pwned.txt` 를 만든다. (확인 후 파일과 수정을 되돌린다.)
2. **줄 수 제한 바꾸기** — `MAX_LINES = 10` 으로 줄이고 `git_log` 를 `max_count: 20` 으로 불러 본다.
3. **도구 하나 더** — `git_show`(커밋 하나의 변경 내용)를 추가해 본다. 어떤 값을 검증해야 하고, 출력이 크면 어떻게 줄일지 먼저 정한다.
4. **다른 CLI 로 바꾸기** — `run_git` 의 `GIT_CMD` 자리에 팀의 CLI 를 넣고, 그 CLI 가 `-` 로 시작하는 값을 어떻게 받는지(`--` 를 지원하는지) 먼저 확인한다. 지원하지 않으면 거부가 유일한 방어가 된다.
5. **스킬과 비교** — `bash` 권한이 열린 상태에서 "git 으로 `--output=x` 를 붙여 diff 를 떠 줘"라고 시키면 어떻게 되는지, MCP 서버만 열고 `bash` 를 막은 상태(M8, C5 참고)와 비교한다.

## 주의할 점 / 문제 해결

- **opencode 를 `sandbox/` 안에서 실행해야 한다.** 예제 폴더에서 실행하면 `opencode.json` 은 찾아지지만, 서버는 그 폴더가 속한 저장소(이 레포 전체)를 대상으로 한다. `sandbox/` 는 자기 `.git` 을 갖고 있어 이 레포와 분리된다.
- **`prepare.py` 는 `sandbox/` 를 지우고 다시 만든다.** `sandbox/` 안에서 고친 것은 사라진다. `server.py` 를 고쳤다면 `prepare.py` 를 다시 실행해야 복사본에 반영된다.
- **`git` 이 PATH 에 없으면** 도구가 "git 실행 파일을 찾을 수 없습니다" 라는 `isError` 를 돌려주고, `check.py` 는 이 예제를 건너뛴다(경고).
- **이 서버는 읽기 전용 "동작"만 노출한 것이지, 읽기 전용 "권한"이 아니다.** 같은 사용자 권한으로 돌기 때문에 서버 코드의 검증이 뚫리면 그 사용자가 할 수 있는 일은 다 할 수 있다. 중요한 저장소라면 읽기 전용 계정이나 컨테이너에서 서버를 돌리는 것이 따로 필요하다.
- **검증 목록은 완전하지 않다.** 리비전 이름은 `-` 시작과 제어 문자만 거른다. git 이 리비전으로 해석하는 값(`HEAD~3`, `a..b`, `HEAD:파일` 등)은 모두 통과한다. 허용할 모양을 더 좁히고 싶다면 정규식 화이트리스트를 추가한다.
- 빠른 점검: 서버가 이상하면 `sandbox/` 안에서 JSON 줄을 직접 넣어 본다(따라 하기 2번).
