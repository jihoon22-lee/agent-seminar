# C2 설정 변수: `{env:}` · `{file:}` 와 마스킹

> 구성: opencode.json + MCP 서버 1개 | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: 설정 (변수 치환)

## 무엇을 보여 주나

`opencode.json` 에 토큰을 직접 적지 않고 **환경변수**(`{env:NAME}`)나 **파일**(`{file:경로}`)에서 읽어 오는 방법을 보여 줍니다.
함께 세 가지 함정을 확인합니다. 셸 문법 `${NAME}` 은 치환되지 **않고**, 없는 환경변수는 오류가 아니라 **빈 문자열**이 되며, `opencode debug config` 의 `***` 마스킹은 **이름 기반**이라 모든 비밀이 가려지는 것도 아니고 "설정되었는지"를 알려 주지도 않는다는 점입니다.
작은 MCP 서버(`env_probe_server.py`)가 자기가 받은 환경변수를 기록해서, 마스킹 뒤에 가려진 **진짜 값이 프로세스에 도착했음**을 증명합니다.

## 실무에서는

- 저장소에 커밋하는 `opencode.json` 에는 `"Authorization": "Bearer {env:API_TOKEN}"` 만 적고, 실제 토큰은 각자의 셸이나 비밀 관리 도구에서 주입합니다.
- 토큰이 파일로 배포되는 환경(컨테이너 시크릿, 비밀 관리 도구가 만든 파일)에서는 `{file:/run/secrets/token}` 으로 읽습니다.
- 팀원이 "내 MCP 서버가 인증 실패"라고 할 때, 먼저 환경변수가 비어 있지는 않은지 서버 쪽에서 확인합니다. (설정 화면에서는 `***` 라서 구분이 안 됩니다.)
- 화면 공유나 버그 리포트에 `opencode debug config` 출력을 붙이기 전에, 가려진 것과 가려지지 않은 것을 알고 있어야 합니다.

## 파일 구성

```
c2-variables/
  README.md
  opencode.json           {env:} / {file:} / ${} 를 모두 쓰는 설정. MCP "env-probe" 와 꺼진 remote 항목
  prepare.py              secrets/token.txt 에 가짜 토큰 파일을 만든다 (gitignore 대상)
  env_probe_server.py     받은 환경변수를 out/received.json 에 기록하고 env_report 도구로 돌려주는 MCP 서버
  check.py                자동 검증
  secrets/  out/          prepare.py, MCP 서버가 만드는 폴더 (git 에 올라가지 않음)
```

## 따라 하기

1. 가짜 토큰 파일을 만듭니다. (다시 실행해도 안전합니다. 토큰은 데모용 가짜 문자열입니다.)

   PowerShell:
   ```powershell
   cd examples\00-config\c2-variables
   python prepare.py
   ```
   Linux bash:
   ```bash
   cd examples/00-config/c2-variables
   python3 prepare.py
   ```

2. **환경변수를 안 준 채로** 설정을 봅니다. (`DEMO_*` 가 비어 있는 상태)

   ```
   opencode debug config
   ```
   `mcp.env-probe.environment` 에서 `GREETING` 이 `", "` 이고 `UNSET_VALUE` 가 `""` 인지 확인하세요.

3. 환경변수를 주고 다시 봅니다.

   PowerShell:
   ```powershell
   $env:DEMO_API_TOKEN = "demo-env-token-123"; $env:DEMO_GREETING = "안녕"; $env:DEMO_NAME = "세미나"; $env:DEMO_USER = "alice"
   opencode debug config
   ```
   Linux bash:
   ```bash
   export DEMO_API_TOKEN=demo-env-token-123 DEMO_GREETING=안녕 DEMO_NAME=세미나 DEMO_USER=alice
   opencode debug config
   ```

4. MCP 서버를 띄워서 **서버가 받은 진짜 값**을 확인합니다. `mcp list` 가 서버를 시작하고, 서버는 `out/received.json` 에 받은 값을 씁니다.

   PowerShell:
   ```powershell
   opencode mcp list
   Get-Content out\received.json -Encoding UTF8
   ```
   Linux bash:
   ```bash
   opencode mcp list
   cat out/received.json
   ```
   Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`opencode.json` 의 `"command": ["python", ...]` 를 `python3` 로 수정)

5. (선택) 모델에게 서버가 받은 값을 말하게 합니다. 평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 `-m opencode/big-pickle` 을 붙이세요.

   ```
   opencode run --auto "env-probe_env_report 도구를 호출하고, 돌려받은 JSON 을 그대로 보여 주세요."
   ```
   또는 `opencode` 를 열고 같은 문장을 입력합니다.

6. 정리: `Remove-Item Env:DEMO_API_TOKEN, Env:DEMO_GREETING, Env:DEMO_NAME, Env:DEMO_USER` (PowerShell) / `unset DEMO_API_TOKEN DEMO_GREETING DEMO_NAME DEMO_USER` (bash).

## 기대 결과

3번의 `opencode debug config` (1.19.5, Linux, 환경변수를 준 상태)에서 `mcp` 부분입니다.

```json
"env-probe": {
  "type": "local",
  "command": ["python", "env_probe_server.py"],
  "environment": {
    "DEMO_API_TOKEN": "***",
    "FILE_TOKEN": "***",
    "GREETING": "안녕, 세미나",
    "SHELL_STYLE": "${DEMO_API_TOKEN}",
    "UNSET_VALUE": "",
    "PLAIN_NOTE": "just-a-literal"
  },
  "enabled": true
},
"remote-demo": {
  "type": "remote",
  "url": "http://127.0.0.1:9/mcp",
  "headers": { "Authorization": "***", "X-Demo-Label": "***" },
  "enabled": false
}
```

4번의 `out/received.json` (서버가 실제로 받은 값):

```json
{
  "DEMO_API_TOKEN": "demo-env-token-123",
  "FILE_TOKEN": "demo-file-token-456",
  "GREETING": "안녕, 세미나",
  "SHELL_STYLE": "${DEMO_API_TOKEN}",
  "UNSET_VALUE": "",
  "PLAIN_NOTE": "just-a-literal"
}
```

환경변수를 **주지 않았을 때**는 `debug config` 의 `DEMO_API_TOKEN` 이 똑같이 `"***"` 로 보이지만, `received.json` 에서는 `"DEMO_API_TOKEN": ""` 입니다. 화면의 `***` 만으로는 설정되었는지 알 수 없습니다.
`opencode mcp list` 는 `env-probe connected`, `remote-demo disabled` 로 표시됩니다.

5번의 모델 호출 결과(모델이 `env_report` 를 호출하는지)는 이 저장소를 만들 때 무료 모델 한도 문제로 확인하지 못했습니다. 모델 없이 확인한 위의 `received.json` 이 핵심 증거입니다.

## 동작 원리

**치환 규칙** (아래는 모두 직접 실행해서 확인한 동작입니다.)

| 표기 | 동작 |
|---|---|
| `{env:NAME}` | 문자열 안 어디서나 치환된다. `"Bearer {env:TOKEN}"`, `"{env:A}-{env:B}"` 처럼 조합 가능. `command` 배열, `environment`, `headers`, `username`, `instructions` 등 문자열이면 어디든 된다 |
| `{env:없는변수}` | 오류 없이 **빈 문자열**. `command` 의 인자가 `""` 로, `Bearer {env:X}` 는 `"Bearer "` 로 바뀐다. `username` 이 빈 문자열이면 OS 사용자 이름으로 대체된다 |
| `{file:경로}` | 파일 내용으로 치환. **끝의 줄바꿈은 제거**된다. 상대 경로는 **그 설정 파일이 있는 폴더** 기준이다 (`.opencode/opencode.json` 에서는 `.opencode/` 기준). `OPENCODE_CONFIG_CONTENT` 안에서는 실행 위치(cwd) 기준. 절대 경로와 `~/` 도 된다 |
| `{file:없는파일}` | 빈 문자열이 아니라 **설정 오류** (`bad file reference ... does not exist`). opencode 가 시작되지 않는다 |
| `${NAME}` | **치환되지 않는다.** 글자 그대로 MCP 서버에 전달된다 |

**마스킹** (`opencode debug config` 의 출력에서만 일어나며, 서버 프로세스가 받는 값에는 영향이 없습니다.)

- `headers` 의 값은 **전부** `***` 입니다. (`X-Demo-Label: plain-header` 처럼 비밀이 아니어도 가려집니다.)
- `environment` 의 값은 **키 이름**으로 판단합니다. 키 이름을 바꿔 가며 직접 실험했을 때 가려진 이름: `API_KEY`, `APIKEY`, `TOKEN`, `DEMO_TOKEN`, `BEARER_TOKEN`, `SECRET`, `MY_SECRET`, `PASSWORD`, `CREDENTIAL`, `PRIVATE_KEY`, `COOKIE`. (대소문자 구분 없음. `SECRETARY` 같은 이름도 가려짐)
- `TOKEN` 만은 **이름 끝에 올 때만** 가려집니다. `GITHUB_TOKEN`, `MYTOKEN` 은 `***` 이지만 `TOKEN_PATH`, `TOKEN_X`, `ACCESS_TOKEN_FILE` 은 그대로 보입니다. 반면 `SECRET_NAME`, `PASSWORD_FILE`, `API_KEY_PATH` 처럼 `SECRET`·`PASSWORD`·`API_KEY` 는 어디에 있어도 가려집니다. (opencode 1.19.5, 2026-11-17 재확인)
- 같은 실험에서 가려지지 **않은** 이름: `AUTH`, `BEARER`, `PASS`, `PWD`, `PASSWD`, `ACCESS_KEY`, `CRED`, `SIGNATURE`, `SESSION`, `DSN`, `DATABASE_URL`, `CONNECTION_STRING`, `OAUTH`, `CERT`, 그리고 `WSL_INTEROP`, `GREETING` 같은 일반 이름. 즉 `DATABASE_URL` 에 비밀번호가 들어 있어도 화면에 그대로 나옵니다.
- 값이 비어 있어도(`{env:미설정}`) 이름이 비밀스러우면 똑같이 `***` 로 보입니다.

**값이 서버까지 가는 길**

1. opencode 가 설정 파일을 읽으면서 `{env:}`, `{file:}` 를 치환합니다.
2. MCP 항목의 `environment` 를 자식 프로세스의 환경변수로 넘겨 `env_probe_server.py` 를 실행합니다. (`mcp list`, TUI, `run` 모두 같음)
3. 서버는 시작할 때 `os.environ` 에서 값을 읽어 `out/received.json` 에 씁니다. 마스킹은 출력 단계에서만 일어나므로 서버는 진짜 값을 받습니다.
4. 서버의 규칙: **stdout 에는 MCP 메시지만** 씁니다. 로그·진단문은 stderr 로 보냅니다. (stdout 에 다른 글자가 섞이면 연결이 깨집니다.)

## 직접 바꿔 보기

1. `opencode.json` 의 `SHELL_STYLE` 값을 `{env:DEMO_API_TOKEN}` 으로 고치고, 서버가 받은 값이 어떻게 달라지는지 `out/received.json` 에서 비교해 보세요.
2. `environment` 에 `DATABASE_URL: "postgres://user:{env:DB_PASS}@localhost/app"` 을 추가하고 `debug config` 를 보세요. 비밀번호가 그대로 보이나요? 키 이름을 `DATABASE_TOKEN` 으로 바꾸면 어떻게 되나요?
3. `{file:secrets/token.txt}` 를 `{file:secrets/없는파일.txt}` 로 바꿔 보세요. 어떤 오류 메시지가 나옵니까? 환경변수를 안 준 경우와 어떻게 다른가요?

## 주의할 점 / 문제 해결

- **`${NAME}` 은 안 됩니다.** 셸이나 docker-compose 처럼 쓰면 서버가 글자 그대로 `${NAME}` 을 받아 인증에 실패합니다. 반드시 `{env:NAME}` 입니다.
- **환경변수가 안 넘어간 것도 오류가 아닙니다.** `{env:TOKEN}` 의 `TOKEN` 이 비어 있으면 서버는 빈 토큰으로 시작합니다. 인증 오류가 나면 `received.json` 같은 방법으로 서버 쪽 값부터 확인하세요.
- 환경변수는 **opencode 를 실행한 셸**에서 읽습니다. 이미 떠 있는 opencode 에는 나중에 설정한 환경변수가 반영되지 않습니다. 설정 후 다시 시작하세요.
- 마스킹된 `***` 를 믿고 `debug config` 출력을 공유하지 마세요. 위 표의 "가려지지 않은 이름"이 그대로 노출됩니다.
- `secrets/` 와 `out/` 는 `.gitignore` 대상입니다. 진짜 토큰 파일을 만들었다면 저장소 밖에 두세요.
- Windows PowerShell 5.1 의 `Get-Content` 는 BOM 없는 UTF-8 파일을 한글 Windows 기본 인코딩으로 읽어 한글이 깨질 수 있어 `-Encoding UTF8` 를 붙였습니다.
- Windows 에서는 `$env:이름 = "값"` 으로 설정한 환경변수가 **그 PowerShell 창에서만** 유효합니다.
