# M11 남이 만든 서버 가져다 쓰기 (npx / uvx)

> 구성: 설정 파일 + 연습용 폴더 만드는 스크립트 + 도구 살펴보기 스크립트 (서버 코드는 없다) | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, Node.js(npx), uv(uvx) | 슬라이드: MCP — 남이 만든 서버 쓰기

## 무엇을 보여 주나

M1~M9는 서버를 직접 만들었다. 실무에서는 **이미 있는 서버를 가져다 쓰는 일이 더 많다.** 이 예제는 `opencode.json`에 두 줄을 적어 공개 서버 두 개를 붙인다.

- `files` — 공식 파일 서버 `@modelcontextprotocol/server-filesystem@2.3.0` (Node, `npx`로 실행)
- `clock` — 시간 서버 `mcp-server-time==2026.11.11` (Python, `uvx`로 실행)

핵심은 붙이는 방법이 아니라 순서다. **켜기 전에 살펴보고(`show_tools.py`), 켠 뒤에는 필요한 만큼만 남긴다(`permission` deny).**
파일 서버는 도구가 16개이고 그중 6개가 파일을 쓰거나 지우는 도구다. 그대로 켜면 모델이 sandbox 안의 파일을 마음대로 고칠 수 있다.

## 실무에서는

- "깃 서버, DB 서버, 파일 서버가 이미 있다더라"를 들었을 때, 코드를 짜기 전에 먼저 붙여 보고 도구 목록을 보는 것이 출발점이다.
- 팀에서 검증된 서버 이름과 **버전**을 `opencode.json`에 적어 레포에 넣어 두면, 새로 온 사람도 같은 서버를 같은 버전으로 쓴다.
- 읽기만 필요한 작업이면 쓰기 도구는 처음부터 빼 둔다. 나중에 필요해지면 그때 한 개씩 연다.
- 서버를 붙이기 전에 "이게 정말 서버여야 하나"를 먼저 따진다 (아래 "서버를 붙이지 않는 편이 나을 때").

## 파일 구성

```
m11-use-existing-server/
  README.md        이 문서
  opencode.json    mcp.files(npx) + mcp.clock(uvx) + permission(쓰기 도구 6개 deny)
  prepare.py       연습용 폴더 sandbox/ 를 만든다 (인터넷 불필요)
  show_tools.py    서버가 내놓는 도구와 모델이 받는 도구를 이름·글자 수로 출력
  check.py         자동 검증 (tools/run_checks.py가 실행)
  fake_llm.py      가짜 LLM 서버 (opencode가 모델에게 보내는 요청을 기록하는 데 씀)
  .gitignore       sandbox/ 제외
  sandbox/         (생성됨) 서버가 접근할 수 있는 유일한 폴더
```

`opencode.json`의 핵심:

```json
{
  "mcp": {
    "files": {
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem@2.3.0", "--confine-roots", "sandbox"],
      "timeout": 60000
    },
    "clock": { "type": "local", "command": ["uvx", "mcp-server-time==2026.11.11"], "timeout": 60000 }
  },
  "permission": {
    "files_write_file": "deny", "files_edit_file": "deny", "files_append_file": "deny",
    "files_create_directory": "deny", "files_move_file": "deny", "files_copy_file": "deny"
  }
}
```

## 따라 하기

> **이 단계는 패키지 미러가 필요하다.** `npx`는 npm 레지스트리에서, `uvx`는 PyPI(또는 팀이 쓰는 미러)에서 서버를 처음 한 번 내려받는다. 인터넷이 막혀 있으면 먼저 미러를 설정한다 (`npm config set registry <미러 주소>`, uv는 환경 변수 `UV_DEFAULT_INDEX` 또는 `uv.toml`).
> Linux에서 `python` 명령이 없으면 `python3`로 바꾼다.

**1. 연습용 폴더 만들기**

```powershell
cd examples\02-mcp\m11-use-existing-server
python prepare.py
```

```bash
cd examples/02-mcp/m11-use-existing-server
python3 prepare.py
```

**2. 켜기 전에 살펴보기** — 서버를 띄워 도구 이름, 설명 길이, 스키마 길이, 읽기 전용 표시를 본다. 이어서 opencode가 모델에게 실제로 넘기는 도구도 본다(가짜 모델을 쓰므로 계정이 필요 없고, opencode는 임시 폴더로 격리해서 실행한다).

```powershell
python show_tools.py              # 막은 상태 (opencode.json 그대로)
python show_tools.py --no-limit   # permission 규칙을 뺀 상태와 비교
python show_tools.py --raw        # 서버가 내놓는 도구만 (opencode 실행 없음)
```

```bash
python3 show_tools.py
python3 show_tools.py --no-limit
python3 show_tools.py --raw
```

**3. 연결 확인**

```text
opencode mcp list
```

**4. opencode에서 써 보기** — 평소 쓰는 모델로 실행하면 된다.

```text
opencode run --auto "files 서버로 notes/todo.txt 를 읽어서 할 일이 몇 개인지 알려줘"
opencode run --auto "지금 서울 시간이 몇 시야? clock 도구를 써서 알려줘"
opencode run --auto "files 서버로 notes/new.txt 라는 파일을 만들어 줘"
```

세 번째는 쓰기 도구가 막혀 있어서 `files_*` 쓰기 도구를 쓸 수 없다. 다만 opencode **내장** `write`/`edit` 도구는 이 설정과 상관없이 따로 있다 (아래 "주의할 점").

**5. 자동 검증**

```text
python check.py            # 모델 없이 (가짜 모델)
python check.py --model    # 실제 모델이 files_ 도구를 쓰는지까지 (soft)
```

## 기대 결과

`python show_tools.py` (Linux, 2026-11-17 실행. `npx`/`uvx`가 서버를 받아 오므로 처음에는 몇 초 걸린다):

```text
== 1. 서버가 내놓는 도구 (tools/list)

[files] npx -y @modelcontextprotocol/server-filesystem@2.3.0 --confine-roots sandbox
  도구                              설명    스키마  읽기전용표시  막힘
  read_file                       85    573  예           
  read_text_file                 457    573  예           
  read_media_file                234    306  예           
  read_multiple_files            324    315  예           
  write_file                     228    461  아니오         deny
  append_file                    316    493  아니오         deny
  edit_file                      693    813  아니오         deny
  create_directory               310    344  아니오         deny
  list_directory                 344    279  예           
  list_directory_with_sizes      364    401  예           
  directory_tree                 474    977  예           
  move_file                      325    527  아니오         deny
  copy_file                      318    304  아니오         deny
  search_files                   473    915  예           
  get_file_info                  312    291  예           
  list_allowed_directories       248     95  예           
  -> 읽기 전용이 아닌 도구 6개: write_file, append_file, edit_file, create_directory, move_file, copy_file

[clock] uvx mcp-server-time==2026.11.11
  get_current_time                39    311  예           
  convert_time                    30    717  예           
  get_time_ago                    90    816  예           

서버 합계: 도구 19개, 이름+설명+스키마 약 16331자 (≈ 4082 토큰)

== 2. 모델이 실제로 받는 도구 (가짜 LLM 이 받은 요청)
  files  10개  files_directory_tree, files_get_file_info, files_list_allowed_directories, files_list_directory, ...
  clock   3개  clock_convert_time, clock_get_current_time, clock_get_time_ago
모델에게 가는 MCP 도구: 13개, 정의 JSON 11334자 (≈ 2833 토큰) — 매 요청마다 반복해서 전송
```

`--no-limit`로 보면 `files`가 16개, MCP 도구 합계가 19개 / 17034자(≈ 4258 토큰)가 된다. 글자 수를 4로 나눈 어림값이고, 한글은 토큰이 더 많을 수 있다.

`opencode mcp list`:

```text
●  ✓ files connected
│      npx -y @modelcontextprotocol/server-filesystem@2.3.0 --confine-roots sandbox
●  ✓ clock connected
│      uvx mcp-server-time==2026.11.11
```

가짜 모델로 확인한 호출 결과 (`python check.py`가 하는 일):

```text
files_read_text_file {"path":"notes/todo.txt"}     -> 1. 용어집에 SLO 예시 추가 ... (읽힘)
files_read_text_file {"path":"<예제 폴더>/prepare.py"} -> Access denied - path outside allowed directories: ... not in <예제 폴더>/sandbox
files_write_file {...}                             -> Model tried to call unavailable tool 'files_write_file'. Available tools: ...
clock_get_current_time {"timezone":"Asia/Seoul"}   -> {"timezone": "Asia/Seoul", "datetime": "2026-11-17T16:34:51+09:00", ...}
```

시작 시간 (이 PC, initialize 응답까지. 캐시를 비운 첫 실행 / 이후):

| 서버 | 첫 실행 | 이후 |
|------|---------|------|
| `npx -y …server-filesystem@2.3.0` | 2.8초 | 1.1~1.7초 |
| `uvx mcp-server-time==2026.11.11` | 2.5초 | 0.8초 |

opencode의 서버 시작 제한은 30초다(M9). 이 PC는 레지스트리가 빨라서 여유롭지만, 느린 미러에서는 첫 실행이 길어질 수 있어 서버 항목에 `"timeout": 60000`을 넣어 두었다 (미러 환경에서의 시간은 미검증).

## 동작 원리

### 1. 서버의 README를 읽는 법

공개 서버를 쓰기 전에 npm/PyPI 페이지나 저장소의 README에서 이것만 찾으면 된다.

1. **실행 명령** — `npx -y <패키지>` 또는 `uvx <패키지>`. 그대로 `command` 배열이 된다. 공백으로 나뉜 조각마다 배열 원소 하나다.
2. **인자** — 이 서버는 허용 폴더를 명령줄 인자로 받는다. 서버마다 다르니 README의 "Usage"를 본다. `--help`로도 확인된다.
3. **환경 변수** — 토큰 같은 값이 필요하면 `environment`에 쓴다 (M3 참고).
4. **도구 목록** — README의 표와 실제 `tools/list`가 다를 수 있다. 실제 것은 `show_tools.py`로 본다.

### 2. 버전을 왜 고정하나

`npx -y @modelcontextprotocol/server-filesystem`처럼 버전을 빼면 **실행할 때마다 최신 버전을 받을 수 있다.** 어제 되던 설정이 오늘 다르게 동작한다. `@2.3.0`, `==2026.11.11`처럼 고정하면 팀원 모두가 같은 코드를 쓴다.

다만 고정이 완전하지는 않다. `uvx mcp-server-time==2025.9.25`(이전 버전)를 실행해 보니 2026-11-17에 아래 오류로 죽었다. 이 버전이 의존하는 `mcp` 패키지의 버전이 고정되어 있지 않아 새 `mcp` 2.x가 설치되었고, 코드가 옛 이름(`McpError`)을 찾지 못한 것이다.

```text
ImportError: cannot import name 'McpError' from 'mcp.shared.exceptions' (...). Did you mean: 'MCPError'?
```

그래서 이 예제는 의존성이 호환되는 최신 `2026.11.11`을 쓴다. 최상위 패키지만 고정해도 **그 아래 의존성은 흘러갈 수 있다**는 뜻이다. 엄격하게 하려면 `uvx --exclude-newer <날짜>`나 잠금 파일(M10/M12의 `package-lock.json`, `uv.lock`)을 쓴다 (이 예제에서는 시험하지 않았다).

### 3. "허용 폴더(allowed directories)"가 뜻하는 것

파일 서버는 **허용 폴더 안의 파일만** 읽고 쓴다. 폴더 밖 경로는 서버가 거절한다.

```text
Access denied - path outside allowed directories: .../prepare.py not in .../sandbox
```

`../` 로 빠져나가는 경로도 거절된다. 이 확인은 서버가 하는 일이라 모델이 어떻게 요청해도 같다.

확인한 사실 세 가지:

- `sandbox`처럼 **상대 경로로 준 인자는 서버의 작업 폴더 기준**이다. opencode가 서버를 프로젝트 폴더에서 띄우므로 `<예제 폴더>/sandbox`가 된다 (`list_allowed_directories`로 확인).
- `read_text_file`의 상대 경로(`notes/todo.txt`)는 **허용 폴더 기준**이다. `sandbox/notes/todo.txt`로 쓰면 `sandbox/sandbox/notes`를 찾다가 실패한다.
- **opencode는 연결할 때 `roots` 기능을 선언하고, 서버가 묻으면 "내 프로젝트 폴더"를 roots로 알려 준다.** 이 서버는 `--confine-roots` 없이 roots를 받으면 **명령줄 허용 폴더를 버리고 roots로 바꾼다.** 직접 시험했다: `--confine-roots`를 뺀 설정에서 `list_allowed_directories`가 `sandbox`가 아니라 **프로젝트 폴더 전체**를 돌려줬다. 그래서 이 예제는 `--confine-roots`를 붙였고, 그때 허용 폴더는 `sandbox`로 유지된다. 서버 README의 설명과 같은 동작이다.

> 인자 한 줄이 접근 범위를 통째로 바꾼다. 남의 서버를 쓸 때 "허용 범위가 내 생각과 같은가"는 `list_allowed_directories` 같은 도구로 직접 확인한다.

### 4. 켜기 전에 살펴보기, 그다음 제한하기

`show_tools.py`는 두 가지를 보여 준다.

- **서버가 내놓는 것**: 도구 16개 중 `readOnlyHint`가 `false`인 6개가 쓰기·변경 도구다. 서버가 스스로 붙인 표시이므로 참고용이다. 서버가 거짓으로 적어도 알 수 없으니, **이름과 설명을 눈으로도 읽는다.**
- **모델이 받는 것**: opencode가 모델에게 보낸 요청의 `tools`. M8과 같은 방법(가짜 LLM)이다.

제한은 M8에서 확인한 방법을 그대로 쓴다. `permission`에 `<서버이름>_<도구이름>: "deny"`를 적으면 그 도구는 **모델에게 보내는 목록에서 빠진다.** 빠진 도구를 모델이 억지로 부르면 `unavailable tool` 오류가 돌아오고 파일은 생기지 않는다(직접 확인).

서버 쪽에서 막는 방법도 있다. 이 서버는 `--read-only` 옵션이 있어 쓰기 도구를 아예 등록하지 않는다. `--read-only`를 붙여 `tools/list`를 보니 도구가 10개(읽기 전용)뿐이었고, `write_file`을 직접 호출하면 `Tool write_file not found`(-32602)가 나왔다. 두 방법의 차이:

| | `permission` deny (opencode) | `--read-only` (서버 옵션) |
|---|---|---|
| 어디서 막나 | 모델에게 가는 목록에서 | 서버가 도구를 등록하지 않음 |
| 어느 서버에나 되나 | 예 | 서버가 지원할 때만 (서버마다 다름) |
| 이 예제 | 기본 | 보강으로 `check.py`에서만 시험 |

### 5. 컨텍스트 비용

도구 정의는 **매 요청마다** 모델에게 전송된다. `show_tools.py`로 잰 값 (글자 수 / 4 ≈ 토큰):

| | 도구 수 | 정의 JSON | ≈ 토큰 |
|---|---|---|---|
| 모델이 받음: 서버 둘 다, 제한 없음 | 19 | 17,034자 | 4,258 |
| 모델이 받음: 쓰기 도구 6개 deny | 13 | 11,334자 | 2,833 |
| 서버가 내놓음(`tools/list`): 파일 서버 | 16 | 14,147자 | 3,536 |
| 서버가 내놓음(`tools/list`): 시간 서버 | 3 | 2,184자 | 546 |

위 두 줄은 opencode가 보낸 `tools` 배열 기준(래퍼 포함), 아래 두 줄은 서버가 준 이름+설명+스키마만 센 값이라 서로 바로 비교하면 안 된다.

쓰기 도구 6개를 빼면 약 1,400 토큰이 줄었다. 시간 서버는 질문 한 번에 시각 하나를 알려 주는 일에 약 550 토큰을 쓴다. 쓰지 않는 서버는 `enabled: false`로 꺼 둔다(M8).

### 6. 서버를 붙이지 않는 편이 나을 때

- **내장 도구로 되는 일**: opencode에는 이미 `read`, `grep`, `bash`가 있다. 현재 프로젝트 파일만 읽는다면 파일 서버는 필요 없고, 도구 3,500 토큰만 더 든다. 이 예제의 파일 서버가 의미 있는 경우는 **프로젝트 밖의 특정 폴더를 범위를 정해 열어 줄 때**다.
- **한 줄짜리 명령으로 되는 일**: 시간 서버의 `get_current_time`은 `date` 명령이면 충분하다. 도구 하나 때문에 서버 하나를 붙이면 그 서버의 모든 도구가 따라온다.
- **출처를 모르는 서버**: 서버는 내 PC에서 내 권한으로 실행되는 프로그램이다. 이름이 비슷한 패키지(오타 공격), 설치 때 스크립트가 도는 패키지를 조심한다. 게시자, 배포 횟수, 소스 저장소를 보고, 이름은 철자까지 복사해서 쓴다.
- **고칠 수 없는 서버에 의존하는 일**: 서버가 사라지거나 버전이 깨지면 팀 전체가 멈춘다. 버전 고정과 미러 보관을 같이 생각한다.

## 직접 바꿔 보기

1. `opencode.json`에서 `permission` 블록을 지우고 `python show_tools.py`를 다시 실행한다. `files`가 16개가 되고 MCP 도구 크기가 커진다.
2. `--confine-roots`를 지우고 `opencode run`으로 "files 서버의 `list_allowed_directories`를 불러줘"를 시켜 보자. 허용 폴더가 `sandbox`에서 프로젝트 폴더로 바뀐다.
3. 허용 목록 방식으로 바꾸기: `permission`을 `{"files_*": "deny", "files_read_text_file": "allow", "files_list_directory": "allow"}`처럼 쓴다. 규칙은 마지막 일치가 이기므로(M8) 이 순서여야 한다. 모르는 새 도구가 생겨도 기본이 deny다. (이 방식은 M8에서 같은 규칙으로 확인했고, 이 예제의 서버로는 시험하지 않았다.)
4. 명령에 `--read-only`를 추가해 `python show_tools.py --raw`로 도구 수가 10개가 되는지 본다.
5. 다른 서버를 같은 방법으로 살펴본다: `["uvx", "mcp-server-time==2026.11.11", "--local-timezone", "Asia/Seoul"]`처럼 인자를 추가하는 식이다 (`--help`에 `--local-timezone` 옵션이 있는 것만 확인했고 opencode로는 시험하지 않았다).

## 주의할 점 / 문제 해결

- **막은 것은 MCP 도구뿐이다.** `files_write_file`을 deny해도 opencode 내장 `write`, `edit`, `bash`는 그대로 있어서 모델이 프로젝트 파일을 고칠 수 있다. 쓰기를 정말 막으려면 내장 도구도 같은 방식으로 deny한다(M8의 reviewer 에이전트 참고).
- **`failed`가 나오면**: ① 미러 설정 ② `npx`/`uvx`가 PATH에 있는지 ③ 처음 받는 시간이 제한(`timeout`)을 넘었는지 순서로 본다. 서버 명령을 터미널에서 직접 실행해 보는 것이 가장 빠르다.
- **파일 서버가 `sandbox`를 못 찾는다** — `python prepare.py`를 먼저 실행했는지, opencode를 예제 폴더에서 실행했는지 확인한다 (이 경우의 실제 오류 메시지는 확인하지 않았다).
- **버전을 올릴 때**는 `show_tools.py`를 다시 돌려 도구 목록이 바뀌지 않았는지 본다. 도구가 늘면 `permission`의 deny 목록도 손봐야 한다.
- **Windows**: 이 예제의 `check.py` 전체를 Windows(PowerShell 5.1, opencode 1.19.5)에서도 실행해 통과했다. `npx`와 `uvx` 서버 연결, `--confine-roots`와 상대 인자 `sandbox`, 쓰기 도구 차단이 Linux와 같게 동작했다. 직접 스크립트로 서버를 띄울 때는 `npx`가 `npx.cmd`라서 이름만으로는 실행되지 않는다. `shutil.which("npx")`로 전체 경로를 찾아 넘겨야 한다(`check.py`, `show_tools.py`가 그렇게 한다). opencode는 `["npx", …]` 그대로 실행한다.
