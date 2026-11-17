# M12 server.py를 패키지로 만들어 배포하기 (python -m / uvx)

> 구성: M1 서버를 패키지로 옮긴 코드 + pyproject.toml | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ (uvx 경로는 uv 추가) | 슬라이드: MCP — 서버를 팀에 배포하기

## 무엇을 보여 주나

M1의 `server.py`는 파일 하나라서 레포를 clone해서 `python server.py`로 돌렸다. 서버를 쓰는 사람이 늘면 이 방식이 불편해진다. 이 예제는 **같은 서버를 설치 가능한 패키지로** 바꾸고, 두 가지 방법으로 실행한다.

1. `python -m team_glossary_mcp` + `PYTHONPATH=src` — 설치도 인터넷도 필요 없다 (기본 `opencode.json` 항목).
2. `uvx --from . team-glossary-mcp` — 패키지를 만들어 도구 환경에 설치해 실행한다 (`enabled: false` 항목). 팀 배포의 실제 모양과 같다.

바뀌는 것은 코드가 아니라 **서버를 가리키는 `command` 한 줄**과 데이터 파일을 찾는 방법이다.

## 실무에서는

- 서버를 쓰는 프로젝트가 여럿이면, 프로젝트마다 `server.py`를 복사하지 않고 **버전이 붙은 패키지 하나**를 가리키게 한다.
- 서버를 고치면 모두에게 알려야 한다. 패키지 버전을 올리고 `opencode.json`의 `==1.0.1`만 바꾸면 된다.
- 서버 코드를 보지 않을 팀원에게는 레포 clone 없이 `uvx team-glossary-mcp==1.0.0` 한 줄만 준다.
- 반대로 혼자 쓰거나 서버가 한 프로젝트에 붙어 있다면 패키지로 만들 필요가 없다 (아래 "언제 패키지가 필요한가").

## 파일 구성

```
m12-package-uvx/
  README.md
  pyproject.toml                       패키지 정보, 콘솔 명령(team-glossary-mcp), 빌드 백엔드
  opencode.json                        glossary-pkg(python -m, 켜짐) + glossary-uvx(uvx, 꺼짐)
  src/team_glossary_mcp/
    __init__.py                        __version__ = "1.0.0" (버전은 여기 한 곳)
    __main__.py                        python -m team_glossary_mcp 진입점
    server.py                          M1 server.py를 옮긴 것 (표준 라이브러리만)
    glossary.json                      패키지에 들어가는 데이터 파일
  check.py                             자동 검증 (tools/run_checks.py가 실행)
  fake_llm.py                          가짜 LLM 서버 (check.py 용)
  .gitignore                           dist/, build/, *.egg-info/, .venv/
```

`opencode.json`:

```json
{
  "mcp": {
    "glossary-pkg": {
      "type": "local",
      "command": ["python", "-m", "team_glossary_mcp"],
      "environment": { "PYTHONPATH": "src" },
      "enabled": true
    },
    "glossary-uvx": {
      "type": "local",
      "command": ["uvx", "--from", ".", "team-glossary-mcp"],
      "enabled": false,
      "timeout": 60000
    }
  }
}
```

## 따라 하기

모든 명령은 이 예제 폴더(`examples/02-mcp/m12-package-uvx`)에서 실행한다.
> Linux에서 `python` 명령이 없으면 `python3`로 바꾼다 (`opencode.json`의 `command` 첫 항목도 같이).

**1. 에이전트 없이 서버 직접 실행해 보기** (`PYTHONPATH=src`가 하는 일 확인)

```powershell
cd examples\02-mcp\m12-package-uvx
$env:PYTHONPATH = "src"
python -m team_glossary_mcp        # JSON 한 줄을 붙여 넣어 본다. 끝내려면 Ctrl+C
Remove-Item Env:PYTHONPATH
python -m team_glossary_mcp        # 이번에는 No module named team_glossary_mcp 로 실패한다
```

```bash
cd examples/02-mcp/m12-package-uvx
PYTHONPATH=src python3 -m team_glossary_mcp      # JSON 한 줄을 붙여 넣어 본다. 끝내려면 Ctrl+D
python3 -m team_glossary_mcp                      # 이번에는 No module named team_glossary_mcp 로 실패한다
```

```
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"lookup_term","arguments":{"term":"SLO"}}}
```

**2. opencode로 연결 확인** — 기본 항목은 설치 없이 바로 `connected`다.

```text
opencode mcp list
```

**3. opencode에서 질문하기** — 평소 쓰는 모델로 실행하면 된다.

```text
opencode run --auto "팀 용어집에서 롤백이 무슨 뜻인지 찾아줘"
```

**4. uvx 경로 써 보기** (uv가 필요하고, **처음 빌드할 때 패키지 인덱스(PyPI 또는 미러)가 필요하다**)

```text
uvx --from . team-glossary-mcp
```

`opencode.json`에서 `glossary-uvx`의 `enabled`를 `true`로, `glossary-pkg`는 `false`로 바꾸고 `opencode mcp list`를 다시 실행한다 (둘 다 켜면 같은 도구가 두 이름으로 나타난다).

**5. 팀에 나눠 줄 파일 만들어 보기**

```text
uv build
```

`dist/`에 `team_glossary_mcp-1.0.0-py3-none-any.whl`과 `.tar.gz`가 생긴다.

**6. 자동 검증**

```text
python check.py            # 모델 없이 (가짜 모델)
python check.py --model    # 실제 모델이 도구를 쓰는지까지 (soft)
```

## 기대 결과

`opencode mcp list` (기본 설정):

```text
●  ✓ glossary-pkg connected
│      python -m team_glossary_mcp
●  ○ glossary-uvx disabled
│      uvx --from . team-glossary-mcp
```

시작 시간 (Linux, uv 0.12.5, initialize 응답까지. `python check.py`가 출력하는 값):

| 실행 방식 | 첫 실행 | 두 번째 |
|-----------|---------|---------|
| `PYTHONPATH=src python -m team_glossary_mcp` | 0.04초 | 0.05초 |
| `uvx --from . team-glossary-mcp` (빈 uv 캐시, 빌드 백엔드 내려받기 포함) | 0.64~0.87초 | 0.06~0.07초 |
| `uvx --offline --from <wheel 파일> team-glossary-mcp` (빈 캐시) | 0.16~0.20초 | 0.07초 |

이 PC는 PyPI가 빨라서 첫 실행도 1초 미만이다. 느린 미러에서는 달라질 수 있지만, 그런 환경의 수치는 측정하지 못했다. opencode의 시작 제한은 30초(M9)이고 `uvx` 항목에는 `"timeout": 60000`을 넣어 두었다.

빈 uv 캐시에서 인터넷 없이(`--offline`) `uvx --from .`를 실행하면:

```text
  × Failed to build `team-glossary-mcp @ file:///.../m12-package-uvx`
  ├─▶ Failed to resolve requirements from `build-system.requires`
  ├─▶ No solution found when resolving: `hatchling>=1.27`
  ╰─▶ Because hatchling was not found in the cache and you require hatchling>=1.27, ...
hint: Packages were unavailable because the network was disabled. ...
```

빌드 백엔드(hatchling)를 인덱스에서 받아야 해서다. 서버 자체는 의존성이 없어도 **빌드 단계에서 인덱스가 필요하다.**

wheel 안의 파일 (`uv build --wheel` 후 `unzip -l`):

```text
team_glossary_mcp/__init__.py
team_glossary_mcp/__main__.py
team_glossary_mcp/glossary.json
team_glossary_mcp/server.py
team_glossary_mcp-1.0.0.dist-info/entry_points.txt   <- team-glossary-mcp 명령의 정체
```

## 동작 원리

### M1 server.py에서 달라진 점

| | M1 `server.py` | M12 패키지 |
|---|---|---|
| 데이터 파일 찾기 | `Path(__file__).parent / "glossary.json"` | `importlib.resources.files("team_glossary_mcp").joinpath("glossary.json")` |
| 실행 | `python server.py` (파일 위치 기준) | `python -m team_glossary_mcp` 또는 설치 후 `team-glossary-mcp` |
| 버전 | `"1.0.0"` 문자열 | `__init__.py`의 `__version__` 한 곳. `pyproject.toml`은 이 값을 읽는다 (`dynamic`) |
| UTF-8 설정 | 파일 맨 위 | `main()` 안 (import만 해도 부작용이 없도록) |
| 프로토콜 처리 | 그대로 | 그대로 |

`importlib.resources`를 쓰는 이유는 설치된 패키지는 소스 폴더와 다른 곳(예: wheel을 풀어 둔 도구 환경)에 있기 때문이다. 데이터 파일이 패키지 폴더 **안**에 있으면 hatchling이 wheel에 함께 넣는다 (위 목록에서 확인).

### `environment`와 상대 경로 `PYTHONPATH`

기본 항목은 `python -m team_glossary_mcp`에 `PYTHONPATH=src`를 준다. 패키지가 설치되어 있지 않으므로 파이썬이 `src`에서 찾게 하는 것이다.

- opencode는 `environment`를 서버 프로세스에 실제로 전달한다. 같은 명령에서 `environment`만 빼면 `opencode mcp list`가 `failed`가 되는 것을 `check.py`가 확인한다.
- `src`는 상대 경로이며 **서버 프로세스의 작업 폴더(= opencode를 실행한 프로젝트 폴더) 기준**으로 풀린다. 예제 폴더에서 opencode를 실행했을 때 Linux와 Windows 모두 `connected`였다.
- `command`는 M1과 같다: opencode를 이 폴더에서 실행하지 않으면 `src`를 못 찾아 `failed`다.

### uvx 경로가 하는 일

`uvx --from . team-glossary-mcp`는 ① 현재 폴더를 wheel로 빌드하고(`pyproject.toml`의 `build-system`) ② 격리된 도구 환경에 설치한 뒤 ③ 콘솔 명령 `team-glossary-mcp`(= `team_glossary_mcp.server:main`)를 실행한다. 결과물은 uv 캐시에 남아 두 번째부터 빠르다.

**함정: 소스만 고치면 반영되지 않는다.** `uvx --from .`는 캐시된 빌드를 다시 쓴다. `server.py`에 한 줄을 고치고 다시 실행해도 이전 내용이 나왔다 (uv 0.12.5에서 확인). `__init__.py`의 `__version__`을 올려도 똑같이 이전 버전(`1.0.0`)이 나왔다. 다시 빌드가 일어난 경우:

- `uvx --no-cache --from . team-glossary-mcp` — 캐시를 쓰지 않음
- `pyproject.toml` 수정 시각이 바뀜 (`touch`나 내용 수정)

`--refresh-package team-glossary-mcp`, `--reinstall-package team-glossary-mcp`는 이 경우 효과가 없었다. 개발 중에는 `python -m` 경로(기본 항목)를 쓰면 이 문제가 없다.

### 팀 배포 방법

| 방법 | 명령 | 이 예제에서 |
|------|------|-------------|
| 로컬 폴더 빌드 | `uvx --from . team-glossary-mcp` | **실행 확인** (위 표) |
| wheel 파일(공유 폴더 등) | `uvx --from /공유/폴더/team_glossary_mcp-1.0.0-py3-none-any.whl team-glossary-mcp` | **실행 확인** (Linux, 로컬 경로, 빈 캐시 + `--offline`) |
| 폴더를 인덱스처럼 | `uvx --no-index --find-links /공유/폴더 --from team-glossary-mcp==1.0.0 team-glossary-mcp` | **실행 확인** (Linux, 로컬 경로) |
| 패키지 인덱스/미러 | `uvx team-glossary-mcp==1.0.0` | **미실행** (게시하지 않았다) |
| git 주소 | `uvx --from git+https://<서버>/<저장소>.git@v1.0.0 team-glossary-mcp` | **미실행** |

wheel 파일 방식은 **인터넷도 인덱스도 필요 없다.** 빌드 백엔드가 필요한 것은 wheel을 만드는 사람뿐이고, 받는 사람은 의존성이 없는 이 패키지를 그대로 실행한다. 이 서버가 표준 라이브러리만 쓰기 때문에 가능하다. 의존성이 있는 서버는 그 의존성을 받을 인덱스가 필요하다.

공유 폴더 경로의 Windows 형태(`\\서버\공유\...`, 드라이브 문자)는 확인하지 못했다.

`opencode.json`에서 달라지는 부분은 `command` 한 줄이다.

```json
"command": ["uvx", "--from", "/공유/폴더/team_glossary_mcp-1.0.0-py3-none-any.whl", "team-glossary-mcp"]
```

```json
"command": ["uvx", "team-glossary-mcp==1.0.0"]
```

아래 줄은 인덱스에 게시한 뒤의 형태다 (미실행).

## 직접 바꿔 보기

1. 서버에 도구를 하나 추가하고 `uvx --from .`로 확인해 보자. 반영이 안 되는 것을 직접 보고 `--no-cache`로 해결해 본다.
2. `glossary.json`에 용어를 추가하고 `uv build --wheel`로 다시 빌드한 뒤 wheel 안에 들어갔는지 `unzip -l`로 본다.
3. `pyproject.toml`의 `[tool.hatch.build.targets.wheel]` 블록을 지우면 어떻게 되는지 `uv build`로 본다 (이 예제에서는 시험하지 않았다).
4. `__version__`을 `1.0.1`로 올리고 `uv build`를 하면 파일 이름이 `...-1.0.1-...`로 바뀐다. 기존 wheel과 같은 폴더에 두고 `--find-links` 방식으로 `==1.0.0`과 `==1.0.1`을 각각 요청해 보자 (이 조합은 시험하지 않았다).

## 주의할 점 / 문제 해결

### 언제 `server.py` 하나로 부족해지나

| 상황 | 파일 하나일 때의 문제 | 패키지로 바꾸면 |
|------|----------------------|----------------|
| 버전 관리 | "누가 어느 버전을 쓰는지" 모른다. 파일이 복사되며 갈라진다 | `==1.0.0`으로 고정, 올리면 `==1.0.1` |
| 여러 프로젝트 | 프로젝트마다 `server.py` 복사본 | 같은 패키지 한 줄 |
| 서버를 안 만든 팀원 | 레포를 clone하고 경로를 맞춰야 한다 | `command` 한 줄만 있으면 된다 |
| 의존성이 생길 때 | `requirements.txt`와 가상환경을 따로 안내 | `dependencies`에 적으면 uv가 알아서 설치 (M2의 `prepare.py` 불필요) |

### 비용

- **빌드와 배포 절차가 생긴다.** `pyproject.toml`, 버전 올리기, wheel 만들어 올리기. 서버가 자주 바뀌는 동안에는 번거롭다.
- **처음 빌드에는 인덱스가 필요하다.** 위 실험처럼 빈 캐시 + 오프라인이면 실패한다. 미러 환경이면 `UV_DEFAULT_INDEX` 등으로 지정해야 한다. wheel 파일 배포로 피할 수 있다 (의존성이 없을 때).
- **캐시가 개발을 헷갈리게 한다.** 위의 낡은 빌드 함정.
- 선택 기준: 팀원이 clone 없이 쓰거나, 프로젝트가 여럿이거나, 버전을 고정해야 하면 패키지. 그렇지 않으면 M1처럼 파일 하나가 더 단순하다.

### 그 밖에

- 서버를 고쳤는데 opencode에 반영이 안 되면 opencode를 다시 시작한다 (서버는 시작할 때 한 번 뜬다). uvx 경로는 위의 캐시 문제도 확인한다.
- `opencode mcp list`가 `failed`: ① opencode를 예제 폴더에서 실행했는지 ② Linux에서 `python`이 없다면 `python3` ③ uvx 항목이면 인덱스 접근 가능한지 순으로 본다. 서버 명령을 터미널에서 직접 실행해 보는 것이 가장 빠르다.
- Windows에서도 `check.py` 전체(`python -m` 항목과 `uvx --from .` 항목)가 통과했다. 시작 시간은 Linux에서 잰 값이다.
