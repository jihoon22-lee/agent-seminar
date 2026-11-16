# M3 환경 변수로 설정과 토큰 넘기기

> 구성: 서버 1개(M1과 같은 용어집) + 환경 변수 3개 + 가짜 토큰 파일 | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: MCP — 설정과 비밀 값

## 무엇을 보여 주나

MCP 서버에는 대개 **코드에 쓰면 안 되는 값**(API 토큰, 접속 주소, 로그 수준)이 필요하다. 이 예제는 그 값을 `opencode.json`의
`environment`로 서버 프로세스에 넘기는 방법을 보여 준다. 값은 `{env:이름}`(내 셸의 환경 변수) 또는 `{file:경로}`(파일 내용)로 채운다.
그래서 `opencode.json`을 저장소에 커밋해도 토큰은 들어 있지 않다. 토큰이 없으면 서버가 도구 호출을 **분명한 메시지로 거절**하는 것까지 확인한다.

## 실무에서는

- 팀 저장소에 `opencode.json`을 커밋해 모두가 같은 MCP 서버를 쓰되, **토큰은 각자의 환경 변수나 개인 파일**에서 읽게 한다.
- 개발/운영처럼 접속 대상이 다를 때 `GLOSSARY_PATH`·`API_URL` 같은 값만 환경 변수로 바꿔 같은 서버 코드를 재사용한다.
- 실제 사례: [agent-browser](https://github.com/jihoon22-lee/agent-browser)는 opencode 프로세스를 관리하면서, 브라우저 MCP 서버 항목을 `OPENCODE_CONFIG_CONTENT`로 덧씌워 사용자의 전역 설정을 건드리지 않는다. 그 항목의 `environment`에 실행 홈·포트 같은 값을 넘기고, WSL 환경에서는 `WSL_INTEROP`(WSL에서 Windows 실행 파일을 부르는 데 쓰는 소켓 경로)도 서버 프로세스에 전달한다. 서버 프로세스는 부모(opencode)와 환경이 다르다는 점이 핵심이다. (코드: `bridge/src/runtime/interop.rs`의 `environment` 설정 부분)

## 파일 구성

```
m3-env-config/
  README.md        이 문서
  server.py        환경 변수(GLOSSARY_PATH, API_TOKEN, LOG_LEVEL)를 읽는 MCP 서버
  glossary.json    용어집 (M1과 같은 14개)
  prepare.py       secrets/token.txt(가짜 토큰 파일)를 만든다
  opencode.json    mcp.glossary-env({env:} 사용) / mcp.glossary-file({file:} 사용, 기본 꺼짐)
  secrets/         (prepare.py가 생성, .gitignore 대상)
  check.py         자동 검증
```

`server.py`는 도구 3개를 제공한다: `lookup_term`, `list_terms`(둘 다 `API_TOKEN` 필요), `server_info`(토큰 없이도 동작, 토큰 값은 절대 출력하지 않고 설정됨/없음만 보여 줌).

## 따라 하기

> Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`opencode.json`의 `command`도 `["python3", "server.py"]`로)
> **반드시 이 예제 폴더에서** 실행한다. (`command`의 `server.py`는 opencode를 실행한 폴더 기준)

**1. 준비 — 가짜 토큰 파일 만들기**

```powershell
cd examples\02-mcp\m3-env-config
python prepare.py
```

```bash
cd examples/02-mcp/m3-env-config
python3 prepare.py
```

> 이 단계를 건너뛰면 opencode가 이 폴더에서 아예 시작하지 않는다. `{file:./secrets/token.txt}`가 가리키는 파일이 없으면 설정 오류이기 때문이다. (아래 "주의할 점")

**2. 환경 변수가 없을 때 — 도구가 거절한다**

```powershell
Remove-Item Env:DEMO_API_TOKEN -ErrorAction SilentlyContinue
opencode mcp list
opencode run --auto "glossary-env 도구로 SLO가 무슨 뜻인지 찾아줘"
```

```bash
unset DEMO_API_TOKEN
opencode mcp list
opencode run --auto "glossary-env 도구로 SLO가 무슨 뜻인지 찾아줘"
```

평소 쓰는 모델로 실행하면 됩니다. (`opencode`를 켜서 같은 문장을 입력해도 같다.) 모델 설정이 없다면 `opencode run` 뒤에 `-m opencode/big-pickle`을 붙이세요.

**3. 환경 변수를 정하고 다시 — 도구가 동작한다**

```powershell
$env:DEMO_API_TOKEN = "demo-token-123"
opencode run --auto "glossary-env 도구로 SLO가 무슨 뜻인지 찾아줘"
```

```bash
export DEMO_API_TOKEN=demo-token-123
opencode run --auto "glossary-env 도구로 SLO가 무슨 뜻인지 찾아줘"
```

**4. 토큰이 설정에서 어떻게 보이는지 — `debug config`**

```powershell
opencode debug config
```

```bash
opencode debug config
```

**5. `{file:}` 방식으로 바꿔 보기** — 파일을 고치지 않고 환경 변수 `OPENCODE_CONFIG_CONTENT`로 덮어쓴다.

```powershell
$env:OPENCODE_CONFIG_CONTENT = '{"mcp":{"glossary-env":{"enabled":false},"glossary-file":{"enabled":true}}}'
opencode mcp list
opencode run --auto "glossary-file 도구로 server_info를 보여줘"
Remove-Item Env:OPENCODE_CONFIG_CONTENT
```

```bash
export OPENCODE_CONFIG_CONTENT='{"mcp":{"glossary-env":{"enabled":false},"glossary-file":{"enabled":true}}}'
opencode mcp list
opencode run --auto "glossary-file 도구로 server_info를 보여줘"
unset OPENCODE_CONFIG_CONTENT
```

이때는 `DEMO_API_TOKEN`을 정하지 않아도 `secrets/token.txt`의 값으로 동작한다.

## 기대 결과

`opencode debug config` (발췌 — 토큰 값이 `***`로 가려진다. `LOG_LEVEL`처럼 비밀이 아닌 값은 그대로 보인다):

```json
"glossary-env": {
  "type": "local",
  "command": ["python", "server.py"],
  "environment": {
    "GLOSSARY_PATH": "glossary.json",
    "API_TOKEN": "***",
    "LOG_LEVEL": "INFO"
  },
  "enabled": true
},
```

`opencode mcp list`:

```
●  ✓ glossary-env connected
●  ○ glossary-file disabled
```

토큰이 **없을 때** (모델 `opencode/big-pickle`로 실행한 실제 출력 발췌):

```
✗ glossary-env_lookup_term {"term":"SLO"} failed
Error: API_TOKEN 환경 변수가 설정되지 않아 용어집을 조회할 수 없습니다. opencode.json의 mcp.glossary-env.environment.API_TOKEN 값을 확인하세요. ({env:DEMO_API_TOKEN}을 쓰는 경우 opencode를 실행하는 셸에서 DEMO_API_TOKEN을 먼저 설정해야 합니다.)
```

토큰이 **있을 때**:

```
⚙ glossary-env_lookup_term {"term":"SLO"}
SLO: 서비스가 지키기로 한 내부 목표 수치. 예: 한 달 동안 요청의 99.9%가 500ms 안에 성공. (별칭: Service Level Objective, 서비스 수준 목표)
```

`isError: true` 결과는 `✗ ... failed`와 `Error: <서버가 쓴 메시지>`로 표시된다.

## 동작 원리

### `environment`와 치환 규칙 (opencode 1.19.5에서 확인한 것)

```json
"environment": {
  "GLOSSARY_PATH": "glossary.json",
  "API_TOKEN": "{env:DEMO_API_TOKEN}",
  "LOG_LEVEL": "INFO"
}
```

opencode는 설정 파일을 읽을 때 `{...}` 자리표시자를 먼저 값으로 바꾼 뒤, MCP 서버 프로세스를 띄울 때 `environment`의 값을 **그 프로세스의 환경 변수**로 넣는다.

| 표기 | 의미 | 확인한 동작 |
|------|------|-----------|
| `{env:이름}` | opencode를 실행한 셸의 환경 변수 | 정의되지 않았으면 **빈 문자열**이 된다. 오류가 아니다. |
| `{file:경로}` | 파일 내용 | **설정 파일이 있는 폴더 기준** 상대 경로다 (opencode를 하위 폴더에서 실행하거나, `OPENCODE_CONFIG`로 다른 위치의 설정 파일을 쓸 때도 설정 파일 쪽 기준). 앞뒤 공백과 줄바꿈은 제거된다. |
| `{file:...}`의 파일이 없을 때 | | `Configuration is invalid ... bad file reference ... does not exist`로 **opencode 전체가 시작하지 않는다.** `enabled: false`인 항목이어도 마찬가지다. |

`command`와 원격 `headers`(M4)에서도 `{env:}`를 쓸 수 있다. 서버 프로세스는 opencode의 환경을 이어받고(`PATH` 등) `environment`에 적은 값이 그 위에 더해진다.

### 서버 쪽 규칙 (`server.py`)

- `os.environ.get("API_TOKEN") or ""` — 변수가 아예 없을 때와 **빈 문자열**일 때를 둘 다 "없음"으로 취급한다. `{env:DEMO_API_TOKEN}`이 정의되지 않으면 빈 문자열이 오기 때문에 이 처리가 꼭 필요하다.
- 토큰이 없으면 `lookup_term`/`list_terms`는 `isError: true` 결과로 거절한다. 메시지에 **어떤 설정을 확인해야 하는지** 적어 두면 모델이 사용자에게 그대로 안내할 수 있다.
- `server_info`는 토큰이 있는지 없는지만 알려 주고 값·앞 글자·길이를 노출하지 않는다. 로그(stderr)에도 토큰 값을 쓰지 않는다.
- `LOG_LEVEL`은 파이썬 `logging`의 수준이다. 로그는 stderr로만 나간다.

### `debug config`의 마스킹

`opencode debug config`는 `environment` 값 중 **키 이름이 비밀처럼 보이는 것**(`TOKEN`, `API_KEY`, `SECRET`, `PASSWORD`, `CREDENTIALS`, `AUTHORIZATION`, `COOKIE` 등)을 `***`로 가린다. 몇 가지 확인된 사실:

- 값이 **비어 있어도** `***`로 나온다. 즉 `debug config`만으로는 "환경 변수가 없어서 빈 값"인지 "값이 있는지"를 구분할 수 없다. 이럴 땐 `server_info` 도구처럼 서버가 상태를 알려 주게 하면 된다.
- 원격 서버의 `headers` 값은 전부 `***`로 가려진다 (M4).
- 마스킹은 **이름 패턴** 기준이다. `API_TOKEN_FILE`, `ACCESS_KEY_ID`, `PASSWD`, `DB_URL` 같은 이름은 가려지지 않고 값이 그대로 출력된다. 화면 공유나 로그에 `debug config` 결과가 남을 수 있으니, 비밀 값의 변수 이름은 `..._TOKEN`, `..._KEY`, `..._SECRET`, `..._PASSWORD`로 짓는 것이 안전하다.

## 직접 바꿔 보기

1. **로그 수준** — `opencode.json`의 `LOG_LEVEL`을 `DEBUG`로 바꾸고 `python server.py`를 직접 실행해 stderr에 나오는 로그를 본다. (`opencode run`의 출력에는 서버의 stderr 로그가 나오지 않는다.)
2. **다른 용어집** — `GLOSSARY_PATH`를 다른 JSON 파일로 바꾼다. 상대 경로가 서버 프로세스의 현재 폴더(= opencode를 실행한 폴더) 기준임을 확인한다.
3. **공백 확인** — `secrets/token.txt`의 앞뒤에 공백과 빈 줄을 넣어 보자. `{file:}`은 앞뒤 공백·줄바꿈을 잘라 주므로 서버가 받는 값은 그대로다. (서버는 토큰 값을 출력하지 않으니, 확인하려면 `server.py`의 `main()`에 임시로 `log.info(len(API_TOKEN))`을 넣어 길이만 본다.)
4. **이름 바꿔 보기** — 환경 변수 이름 `API_TOKEN`을 `API_TOKEN_FILE`로 바꾸고(서버 코드의 `os.environ.get`도 함께) `opencode debug config` 결과가 어떻게 달라지는지 본다.

## 주의할 점 / 문제 해결

- **`Configuration is invalid ... bad file reference`** — `python prepare.py`를 먼저 실행하지 않았다는 뜻이다. `opencode.json`이 `{file:./secrets/token.txt}`를 가리키는 한 이 파일이 있어야 한다.
- **토큰을 설정했는데 "API_TOKEN이 설정되지 않았다"고 나온다** — `{env:DEMO_API_TOKEN}`은 **opencode를 실행한 셸**의 변수다. 다른 터미널에서 설정했거나, 설정한 뒤 opencode를 재시작하지 않았다면 반영되지 않는다. PowerShell의 `$env:DEMO_API_TOKEN = "..."`은 그 PowerShell 창에서만 유효하다.
- **도구가 거절해도 에이전트는 다른 길을 찾는다** — 이 예제를 무료 모델 `big-pickle`로 실행했더니 모델이 도구의 거절 메시지를 본 뒤 `bash`로 `glossary.json`을 직접 읽어 답을 만들었다 (`secrets/` 폴더를 `ls`로 열어 보기도 했다). 서버의 토큰 검사는 **그 서버의 도구만** 막을 뿐 에이전트의 다른 도구(bash, read)는 막지 못한다. 파일을 읽지 못하게 하려면 권한 설정(`permission`, M8)이 필요하다.
- **`{env:...}`가 정의되지 않아도 오류가 나지 않는다** — 오타를 내도 조용히 빈 문자열이 되므로, 서버가 "값이 비었다"를 분명히 알리게 만드는 것이 이 예제의 `API_TOKEN` 처리다.
- **실제 토큰을 `opencode.json`에 직접 쓰지 말 것.** 이 예제의 `demo-token-123` 같은 값은 연습용 가짜 값이다. 진짜 토큰은 환경 변수나 커밋하지 않는 파일(`secrets/`는 `.gitignore`에 있다)로만 다룬다.
- **Windows PowerShell에서 `$env:이름 = ...`** — 따옴표 안의 값만 쓴다. 영구 설정이 아니라 현재 창에만 적용된다.
