# 1. opencode.json: 위치, 병합, 변수, 권한

이 문서는 세미나 3장 "설정"을 글로 옮긴 것입니다. 설정 파일을 어디에 두는지, 여러 파일이 어떻게 합쳐지는지, 비밀값을 어떻게 다루는지, 권한을 어떻게 선언하는지, 그리고 커스텀 명령, 모델 제공자 연결, 에이전트 정의를 다룹니다.
모든 내용은 **opencode 1.19.5** 기준입니다.

관련 예제: [C1 범위와 병합](../../examples/00-config/c1-scope-merge/) · [C2 변수와 마스킹](../../examples/00-config/c2-variables/) · [C3 실행할 때만 얹기](../../examples/00-config/c3-config-content-overlay/) · [C4 격리 실험](../../examples/00-config/c4-isolated-testing/) · [C5 권한](../../examples/00-config/c5-permissions/) · [C6 커스텀 명령](../../examples/00-config/c6-custom-commands/) · [C7 모델 제공자](../../examples/00-config/c7-provider-openai-compatible/) · [C8 에이전트](../../examples/00-config/c8-agents/)

## 설정 파일은 세 곳에 둘 수 있습니다

| 범위 | 위치 | 이럴 때 |
|---|---|---|
| 전역 | `~/.config/opencode/opencode.json` (Windows: `%USERPROFILE%\.config\opencode\opencode.json`) | 나만 쓰는 설정, 모든 프로젝트 공통 |
| 프로젝트 | `<프로젝트>/opencode.json` | 팀이 git으로 공유하는 설정 |
| 프로젝트 (폴더형) | `<프로젝트>/.opencode/opencode.json` | 스킬, 플러그인과 한 폴더에 모으고 싶을 때 |

스킬과 플러그인 폴더도 같은 범위를 따릅니다.

| 전역 | 프로젝트 |
|---|---|
| `~/.config/opencode/skills/` | `.opencode/skills/` |
| `~/.config/opencode/plugins/` | `.opencode/plugins/` |

원칙은 간단합니다. **팀이 같이 쓸 것은 프로젝트에, 개인 취향은 전역에** 둡니다. 토큰 같은 비밀값은 어디에도 직접 쓰지 않고 환경 변수로 넘깁니다. (아래 "변수 치환"에서 다룹니다.)

### 프로젝트 설정을 찾는 방법

opencode는 **실행한 폴더에서 위로 올라가며** 프로젝트 설정을 찾습니다. 그래서 프로젝트의 하위 폴더에서 실행해도 루트의 `opencode.json`이 적용됩니다.

- git 저장소 안에서는 **저장소 루트까지만** 올라갑니다. 저장소 바깥 폴더에 둔 `opencode.json`은 읽히지 않습니다.
- git 저장소가 **아닌** 곳에서는 계속 위로 올라갑니다. 압축을 푼 예제 폴더 위쪽에 우연히 다른 `opencode.json`이 있으면 같이 병합됩니다. 예상 밖의 값이 보이면 `git init`으로 경계를 만들거나 `OPENCODE_DISABLE_PROJECT_CONFIG=1`을 써 보세요.

설정 파일은 주석과 끝 쉼표를 허용하는 JSON입니다. 문법이 틀리면 `Config file at ... is not valid JSON(C)` 오류와 함께 문제의 줄을 알려 줍니다.

## 여러 파일은 덮어쓰지 않고 합쳐집니다

낮은 층에서 높은 층 순서입니다. 같은 키가 겹치면 위쪽(높은 층)이 이깁니다.

```
 1. 전역                  ~/.config/opencode/opencode.json
 2. OPENCODE_CONFIG       환경 변수가 가리키는 파일
 3. 프로젝트 루트          opencode.json
 4. 프로젝트 .opencode/    opencode.json
 5. OPENCODE_CONFIG_CONTENT  환경 변수 속 JSON 문자열 (파일이 아님)
```

헷갈리기 쉬운 점이 두 가지 있습니다.

- **`OPENCODE_CONFIG` 파일은 프로젝트 설정보다 약합니다.** 전역 위에 얹힐 뿐 전역을 없애지 못하고, 프로젝트 설정에는 집니다. 팀 공용 기본값을 파일 하나로 배포하는 용도로 알맞습니다.
- 위 층 외에 `OPENCODE_CONFIG_DIR=폴더`로 추가 설정 폴더를 지정할 수 있습니다. 이 폴더는 프로젝트 `.opencode/`보다 위, `OPENCODE_CONFIG_CONTENT`보다 아래에 쌓입니다.

이 순서는 1.19.5에서 같은 키를 다섯 군데에 넣고 하나씩 빼 보며 확인한 것입니다. [C1](../../examples/00-config/c1-scope-merge/)의 `demo.py`가 임시 폴더에서 다섯 단계를 차례로 쌓고, 각 값이 **어느 층에서 왔는지** 표로 보여 줍니다. 내 실제 전역 설정은 건드리지 않습니다.

PowerShell:
```powershell
cd examples\00-config\c1-scope-merge
python demo.py
```
Linux bash:
```bash
cd examples/00-config/c1-scope-merge
python3 demo.py
```

### 값의 종류마다 합쳐지는 방식이 다릅니다

| 값의 종류 | 예 | 규칙 |
|---|---|---|
| 단일 값 (문자열, 숫자) | `username`, `share` | 가장 높은 층의 값 하나만 남는다 |
| 배열 | `instructions` | 교체되지 않고 낮은 층부터 **이어 붙는다**. 같은 항목은 한 번만 남는다 |
| 객체 | `mcp`, `permission` | **키 단위**로 합쳐진다. 안쪽 객체도 같은 방식 |
| 객체 자리에 문자열 | `permission.bash`를 `"allow"`로 | 합쳐지지 않고 아래 층의 객체를 **통째로 교체** |

그래서 "프로젝트에 `instructions`를 적었더니 전역 규칙이 사라졌다"는 일은 생기지 않습니다. 반대로 전역의 `permission.bash` 객체를 프로젝트에서 `"allow"` 한 단어로 바꾸면 전역 규칙이 통째로 사라집니다. 객체를 문자열로 바꾸는 순간 병합이 멈추기 때문입니다.

## 적용된 결과는 debug config로 확인합니다

"설정했는데 안 된다"의 대부분은 이 세 명령으로 원인이 보입니다.

| 증상 | 명령 |
|---|---|
| 키 오타, 다른 파일이 덮어쓴 값 | `opencode debug config` |
| 스킬이 안 보인다 | `opencode debug skill` |
| MCP 서버가 안 붙는다 | `opencode mcp list` |

설정은 **시작할 때 한 번만** 읽습니다. 고친 뒤에는 opencode를 다시 실행하세요.

### 최상위 키 오타는 조용히 사라집니다

opencode 1.19.5의 검사는 반쪽만 엄격합니다.

- 알 수 없는 **최상위 키**는 오류 없이 버려집니다. `"plugins"`(복수형), `"permision"`, `"skills": {"path": ...}`는 에러 없이 사라지고 opencode는 그냥 뜹니다. "플러그인을 등록했는데 안 불린다"면 `plugins` 오타부터 의심하세요.
- `mcp` 항목 안의 오타, 잘못된 권한 값(`"permission": {"bash": "maybe"}`, 메시지 `Expected PermissionActionConfig`)은 `Configuration is invalid`로 시작 자체를 막습니다.

공식 문서에는 다음 버전 형식(`mcp.servers`, `plugins`)이 먼저 올라와 있습니다. 1.19.5에서 `plugins`는 조용히 무시되는 키입니다. 문서를 볼 때 버전을 꼭 확인하고, 적은 뒤에는 `debug config`에 실제로 남았는지 보세요. `$schema`를 넣으면 편집기가 미리 빨간 줄을 그어 줍니다.

```json
{
  "$schema": "https://opencode.ai/config.json"
}
```

### 이 문서에서 다루는 키

| 키 | 역할 |
|---|---|
| `$schema` | 편집기 자동 완성과 오류 표시 |
| `instructions` | 항상 읽히는 규칙 문서 |
| `skills.paths`, `skills.urls` | 기본 위치 밖의 스킬 ([2장](02-skills.md)) |
| `mcp` | 붙일 MCP 서버. 서버 이름이 도구 이름 앞에 붙는다 ([3장](03-mcp.md)) |
| `plugin` | 폴더 밖 플러그인. `.opencode/plugins/`는 적지 않아도 로드된다 ([4장](04-plugins.md)) |
| `permission` | 도구별 허용, 확인, 거부 |
| `command` | 커스텀 명령 정의 (아래 "커스텀 명령") |
| `provider`, `model` | 모델이 있는 주소와 기본 모델 (아래 "모델 제공자 연결") |
| `agent` | 역할별 프롬프트와 권한 (아래 "에이전트 정의") |

## 변수 치환: 비밀값은 설정 파일에 쓰지 않습니다

`opencode.json`은 git에 올리고, 토큰은 각자 환경 변수로 넣습니다. 팀원 모두 같은 파일을 씁니다.

```json
"environment": {
  "DEMO_API_TOKEN": "{env:DEMO_API_TOKEN}",
  "FILE_TOKEN": "{file:secrets/token.txt}",
  "GREETING": "{env:DEMO_GREETING}, {env:DEMO_NAME}",
  "SHELL_STYLE": "${DEMO_API_TOKEN}",
  "UNSET_VALUE": "{env:DEMO_NOT_SET}"
}
```

| 표기 | 동작 |
|---|---|
| `{env:NAME}` | 문자열 안 어디서나 치환된다. `"Bearer {env:TOKEN}"`, `"{env:A}-{env:B}"`처럼 조합할 수 있다. `command`, `environment`, `headers`, `url`, `username`, `instructions` 등 문자열이면 어디든 된다 |
| `{env:없는변수}` | 오류 없이 **빈 문자열**. `Bearer {env:X}`는 `"Bearer "`가 된다 |
| `{file:경로}` | 파일 내용으로 치환. 앞뒤 공백과 줄바꿈은 제거된다. 상대 경로는 **그 설정 파일이 있는 폴더** 기준(`.opencode/opencode.json`이면 `.opencode/` 기준). 절대 경로와 `~/`도 된다 |
| `{file:없는파일}` | 빈 문자열이 아니라 **설정 오류**(`bad file reference ... does not exist`). opencode가 시작되지 않는다. `enabled: false`인 항목이어도 마찬가지다 |
| `${NAME}` | **치환되지 않는다.** 글자 그대로 서버에 전달된다 |

가장 흔한 실수는 셸이나 docker-compose처럼 `${NAME}`을 쓰는 것입니다. 서버가 글자 그대로 `${NAME}`을 받아 인증에 실패합니다. 반드시 `{env:NAME}`입니다.

두 번째 함정은 **없는 변수가 오류가 아니라는 점**입니다. 오타를 내도 서버는 빈 토큰으로 시작합니다. 인증 오류가 나면 서버가 실제로 받은 값부터 확인하세요. [C2](../../examples/00-config/c2-variables/)의 `env_probe_server.py`가 받은 환경 변수를 `out/received.json`에 기록해서 이 확인을 보여 줍니다.

환경 변수는 **opencode를 실행한 셸**에서 읽습니다. 이미 떠 있는 opencode에는 나중에 설정한 변수가 반영되지 않습니다. PowerShell의 `$env:이름 = "값"`은 그 창에서만 유효합니다.

PowerShell:
```powershell
$env:DEMO_API_TOKEN = "demo-env-token-123"
opencode debug config
Remove-Item Env:DEMO_API_TOKEN
```
Linux bash:
```bash
export DEMO_API_TOKEN=demo-env-token-123
opencode debug config
unset DEMO_API_TOKEN
```

### debug config의 마스킹은 이름 기반입니다

`opencode debug config`는 비밀처럼 보이는 값을 `***`로 가립니다. 서버 프로세스가 받는 값에는 영향이 없고, 출력 단계에서만 일어납니다. 하지만 **모든 비밀이 가려지는 것은 아닙니다.**

| 대상 | 규칙 |
|---|---|
| 원격 MCP의 `headers` | 값이 **전부** `***` (비밀이 아닌 값도) |
| MCP `environment` 값 | **키 이름**으로 판단 |

`environment`에서 가려지는 이름과 보이는 이름은 다음과 같습니다 (대소문자 구분 없음).

| 가려진다 | 그대로 보인다 |
|---|---|
| 이름에 `SECRET`, `PASSWORD`, `API_KEY`, `APIKEY`, `PRIVATE_KEY`, `COOKIE`, `CREDENTIAL`, `AUTHORIZATION`이 **어디에든** 들어간 것 (`SECRET_NAME`, `PASSWORD_FILE`, `API_KEY_PATH`도 가려짐) | `AUTH`, `BEARER`, `PASS`, `PWD`, `PASSWD`, `ACCESS_KEY`, `CRED`, `SIGNATURE`, `SESSION`, `DSN`, `DATABASE_URL`, `CONNECTION_STRING`, `OAUTH`, `CERT` |
| 이름이 `TOKEN`으로 **끝나는** 것 (`API_TOKEN`, `GITHUB_TOKEN`) | `TOKEN_PATH`, `TOKEN_X`, `ACCESS_TOKEN_FILE` |

결론은 세 가지입니다.

1. `DATABASE_URL`에 비밀번호가 들어 있으면 화면에 그대로 나옵니다.
2. 값이 비어 있어도(`{env:미설정}`) 이름이 비밀스러우면 똑같이 `***`입니다. 화면의 `***`만으로는 **설정되었는지 알 수 없습니다.**
3. `debug config`는 전역 설정을 포함한 개인 설정을 전부 출력합니다. 화면 공유나 로그 첨부 전에 내용을 확인하세요.

비밀 값의 변수 이름은 `..._TOKEN`(끝), `..._SECRET`, `..._PASSWORD`, `..._API_KEY`로 짓는 것이 안전합니다. `..._KEY`라고만 지으면 (`ACCESS_KEY`처럼) 가려지지 않을 수 있습니다.

## OPENCODE_CONFIG_CONTENT: 이번 실행에만 설정 얹기

`OPENCODE_CONFIG_CONTENT`에 JSON 문자열을 넣고 opencode를 실행하면, 그 JSON이 **가장 높은 우선순위**로 병합됩니다. 설정 파일은 하나도 고치지 않습니다.

PowerShell:
```powershell
$env:OPENCODE_CONFIG_CONTENT = '{"instructions":["extra.md"]}'
opencode debug config
Remove-Item Env:OPENCODE_CONFIG_CONTENT
```
Linux bash:
```bash
OPENCODE_CONFIG_CONTENT='{"instructions":["extra.md"]}' opencode debug config
```

어떤 프로그램이 opencode를 **자식 프로세스로 띄울 때** 자기 도구를 붙이는 패턴으로 유용합니다. 공개 프로젝트 agent-browser가 이 방식을 씁니다. 브라우저 MCP 항목(`mcp.browser`)을 자기가 띄우는 opencode 프로세스에만 얹기 때문에, 사용자의 모델, 로그인, 다른 MCP 설정은 그대로 살아 있고 전역 설정 파일은 한 글자도 바뀌지 않습니다. 서버에 넘길 값은 같은 항목의 `environment`로 전달합니다. 이 패턴을 작게 줄인 것이 [C3](../../examples/00-config/c3-config-content-overlay/)의 `launch.py`입니다. 얹는 JSON은 대략 이 모양입니다.

```json
{
  "username": "overlay-user",
  "mcp": {
    "clock": {
      "type": "local",
      "command": ["/usr/bin/python3", ".../clock_server.py"],
      "enabled": true
    }
  }
}
```

`launch.py`로 실행한 opencode에서만 `clock` 서버가 붙고, 같은 폴더에서 그냥 `opencode mcp list`를 하면 없습니다. 파일에는 아무 흔적이 남지 않습니다.

쓸 때 알아야 할 점입니다.

- 덧씌우기는 **프로세스 단위**입니다. 이미 떠 있는 opencode에는 적용되지 않습니다.
- 파일 위치가 없는 JSON이라 `{file:...}`의 상대 경로가 **실행 위치(cwd)** 기준이 됩니다. 서버 경로는 절대 경로로 적으세요.
- 이 JSON 안의 `{env:...}`와 `{file:...}`도 치환됩니다. 토큰을 JSON에 직접 넣으면 같은 사용자의 다른 프로세스가 볼 수 있으니 `{env:NAME}`으로 참조하세요.
- 전역 설정보다 우선하므로, 사용자가 전역에 둔 MCP와 같은 이름을 쓰면 덮어씁니다. 서버 이름이 겹치지 않게 지으세요.
- 쉘 따옴표에 주의하세요. PowerShell에서는 바깥을 작은따옴표, 안쪽 JSON을 큰따옴표로 쓰는 것이 편합니다. JSON이 깨지면 시작할 때 설정 오류로 멈춥니다.

## 내 설정을 망치지 않고 실험하기

스킬, 플러그인, 설정을 실험할 때 내 평소 설정과 섞이면 "왜 되지?"와 "왜 안 되지?"를 구분할 수 없습니다. 격리가 개발의 기본입니다. 이 저장소의 모든 `check.py`도 이렇게 격리한 상태로 돌아갑니다.

`XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_STATE_HOME`을 임시 폴더로 바꾸면 전역 설정, 로그인 정보, 세션 기록, 캐시가 모두 임시 폴더로 갑니다. [C4](../../examples/00-config/c4-isolated-testing/)의 `isolated.py`가 이를 대신 해 줍니다.

PowerShell:
```powershell
cd examples\00-config\c4-isolated-testing
opencode debug paths                 # 평소: 내 실제 경로
python isolated.py debug paths       # 격리: 전부 임시 폴더
python isolated.py --global-config fake-global.json debug config
```
Linux bash:
```bash
cd examples/00-config/c4-isolated-testing
opencode debug paths
python3 isolated.py debug paths
python3 isolated.py --global-config fake-global.json debug config
```

격리 스위치마다 막는 것과 못 막는 것이 다릅니다. 모두 같은 실험 폴더에서 직접 확인한 결과입니다.

| 스위치 | 막는 것 | 막지 못하는 것 |
|---|---|---|
| `OPENCODE_DISABLE_PROJECT_CONFIG=1` | 프로젝트의 `opencode.json`, `.opencode/opencode.json`, `.opencode/skills/`, `.opencode/plugins/` 전부 | `OPENCODE_CONFIG`, `OPENCODE_CONFIG_CONTENT`, 전역 설정, 홈의 외부 스킬 |
| `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` | `~/.claude/skills`, `~/.agents/skills` | 프로젝트·전역 스킬, 내장 스킬 `customize-opencode` |
| `--pure` (`OPENCODE_PURE=1`) | 외부 **플러그인**만 | 설정 병합과 스킬은 그대로 |
| `OPENCODE_CONFIG=파일` | 아무것도 못 막는다 (전역 위, 프로젝트 아래에 끼어들 뿐) | 단독으로는 격리 수단이 아님 |

권장 조합은 다음과 같습니다.

1. 전역, 세션, 로그인까지 분리: `isolated.py`(XDG 샌드박스)
2. 프로젝트 파일의 영향까지 제거: `OPENCODE_DISABLE_PROJECT_CONFIG=1`
3. 그 위에 시험할 설정만 얹기: `OPENCODE_CONFIG=test-config.json` 또는 `OPENCODE_CONFIG_CONTENT`
4. 플러그인이 의심되면: `--pure`

격리하면 **모델 로그인도 사라집니다.** 모델이 필요하면 `-m opencode/big-pickle` 같은 무료 모델을 쓰거나 필요한 설정을 `--global-config`로 넘기세요. 또 `isolated.py`는 홈 폴더 자체는 바꾸지 않으므로, 다른 도구가 홈 아래에 쓰는 것은 막지 못합니다.

## permission: 가장 간단한 안전장치

`permission` 키로 에이전트가 무엇을 바로 하고(`allow`), 물어보고(`ask`), 못 하게(`deny`) 할지 코드 없이 선언합니다.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "edit": "ask",
    "bash": {
      "*": "ask",
      "git status*": "allow",
      "rm *": "deny"
    },
    "external_directory": "deny"
  }
}
```

| 키 | 값 | 의미 |
|---|---|---|
| `edit` | `"ask"` | 파일 수정 전에 사람에게 묻는다 |
| `bash` | `"*": "ask"` | 모든 명령은 기본적으로 묻는다 |
| | `"git status*": "allow"` | `git status`로 시작하는 명령은 묻지 않고 실행 |
| | `"rm *": "deny"` | `rm `으로 시작하는 명령은 거부 |
| `external_directory` | `"deny"` | 프로젝트 폴더 밖의 파일 접근 거부 |

### 규칙은 적은 순서대로 평가되고, 마지막으로 맞는 것이 이깁니다

그래서 **넓은 규칙(`*`)을 먼저, 구체적인 예외를 뒤에** 적습니다. 순서를 뒤집어 `{"git status*": "allow", "*": "ask"}`로 쓰면 `*`가 마지막이라 `git status`도 ask가 됩니다.

층이 여러 개일 때의 순서도 알아 두세요. 낮은 층의 키가 먼저, 높은 층에서 새로 나온 키가 뒤에 옵니다. 같은 키를 높은 층에서 다시 적으면 값은 바뀌지만 **위치는 처음 나온 자리에 남습니다.** `permission`을 아무것도 적지 않으면 `bash`와 `edit`은 기본 allow입니다.

모델 없이 규칙을 확인하는 명령이 있습니다. `opencode debug agent build`가 에이전트가 쓰는 최종 규칙을 순서대로 보여 줍니다. `--tool`과 `--params`를 더하면 모델을 거치지 않고 그 에이전트의 권한 규칙으로 도구를 직접 실행합니다. 이 방식에서는 `ask`가 자동 승인되어 allow와 ask를 구분하지 못하지만, deny와 평가 순서는 정확히 확인됩니다.

```
opencode debug agent build --tool bash --params "{ command: 'rm victim.txt', description: 'x' }"
```

예제의 `sandbox/` 폴더에서 실행하세요. 단계별 따라 하기는 [C5](../../examples/00-config/c5-permissions/)에 있습니다.

### 알아 둘 규칙들

| 상황 | 동작 |
|---|---|
| 모든 사용이 deny (`edit: "deny"`, 또는 마지막 `*`가 deny) | 오류가 아니라 도구가 **아예 꺼져서** 모델 목록에서 사라진다 (`Tool bash is disabled for agent build`) |
| `opencode run`에서 `ask` | `--auto`가 없으면 `auto-rejecting`으로 **자동 거절** |
| `opencode run --auto` | `ask`는 자동 승인. **`deny`는 그대로 막힌다** |
| `a && b` 복합 명령 | 부분별로 따로 판정. 한 부분이라도 deny면 거부 |
| `"rm *": "deny"` | `rm`으로 시작하는 문자열만 잡는다. **`git rm -f 파일`은 못 잡는다** (실험에서 파일이 실제로 지워졌음) |
| 프로젝트 안의 `.env` 읽기 | 기본 규칙이 ask |

`--auto`를 쓸수록 `deny`가 안전장치입니다. 위험한 동작은 허용 목록 방식(`"*": "deny"`로 시작해 필요한 것만 allow)이 더 안전합니다.

### plan 에이전트의 부작용

읽기 전용 `plan` 에이전트의 기본 규칙은 `edit * deny`입니다. 그런데 전역에 `"edit": "ask"`를 쓰면 그 뒤에 쌓여서 마지막 `edit *` 규칙이 `ask`가 됩니다. plan 에이전트도 수정을 시도할 수 있게 되어 기본 읽기 전용 성격이 사라집니다. `edit`을 전역으로 바꿀 때는 `opencode debug agent plan`도 확인하세요.

### 스킬과 MCP 도구도 permission으로 제어합니다

`permission`의 키는 도구 이름입니다. 스킬과 MCP 도구도 같은 방식으로 다룹니다.

```json
{
  "permission": {
    "skill": { "*": "allow", "deploy-*": "deny" },
    "ops_noisy_*": "deny",
    "ops_restart": "ask"
  }
}
```

- `permission.skill`의 deny는 스킬을 모델의 목록에서 지웁니다. ([2장](02-skills.md))
- MCP 도구는 `<서버>_<도구>` 이름에 패턴이 걸립니다. deny한 도구는 모델에게 가는 도구 목록에서 빠져 컨텍스트도 아낍니다. ([3장](03-mcp.md))

### 선언형 권한과 플러그인 가드

| | `permission` | 플러그인 (`tool.execute.before`) |
|---|---|---|
| 만드는 법 | `opencode.json` 몇 줄 | JS 코드 |
| 표현력 | 명령 문자열 **패턴**과 allow/ask/deny | 코드로 무엇이든 판단: 옵션 순서, 경로 검사, 기록 |
| 막았을 때 | 사람에게 묻거나 거부 (`ask`가 있음) | 예외를 던져 막고 메시지를 직접 정함. 묻는 동작은 없음 |
| 적합한 때 | 팀 공통 기본 안전선, 사람이 승인하는 흐름 | 패턴으로 표현 못 하는 조건, 감사 기록 |

기본 안전선은 선언형으로 두고, 패턴으로 표현할 수 없는 조건만 플러그인으로 보강합니다. 둘은 함께 쓸 수 있습니다. ([4장](04-plugins.md)의 "permission과 플러그인")

## 커스텀 명령: 내가 부르는 지시문

"계획대로 끝까지 진행해 줘. PR 단위로, 검사 통과 후 병합, ..." 같은 문단을 매번 붙여 넣는 대신 `/finish` 한 단어로 부르게 저장해 두는 기능입니다. [C6](../../examples/00-config/c6-custom-commands/)가 같은 지시문을 명령(`/finish`)과 스킬(`finish-plan`)로 한 프로젝트에 두고, 가짜 모델이 받은 요청을 글자 수까지 비교합니다.

### 정의하는 두 가지 방법

결과는 같습니다.

- `.opencode/command/이름.md`: frontmatter(`description` 등) + 본문. **본문이 `template`** 이 됩니다. `.opencode/commands/`(복수형) 폴더도 읽힙니다.
- `opencode.json`의 `command` 키

```json
{
  "command": {
    "status": {
      "description": "지금 저장소 상태를 세 줄로 요약",
      "agent": "plan",
      "template": "git status 와 git log -5 --oneline 을 읽고, 지금 어떤 상태인지 세 줄로 요약해 줘. 파일은 고치지 않는다."
    }
  }
}
```

- 같은 이름을 `.md`와 `command` 키에 모두 정의하면 **`.md`가 이깁니다.**
- 모델 없이 읽혔는지 확인: `opencode debug config`의 `command` 항목.
- 실행: `opencode run --command finish`, `opencode run --command review "src/app.py"`. TUI에서 `/finish`로 부르는 것은 이 예제에서 확인하지 못했습니다(미검증).

### 인자: `$ARGUMENTS`와 `$1`, `$2`

본문이 `ALL=[$ARGUMENTS] ONE=[$1] TWO=[$2] THREE=[$3]`일 때 모델이 받은 사용자 메시지입니다.

| 넘긴 인자 | 모델이 받은 메시지 |
|---|---|
| `x` | `ALL=[x] ONE=[x] TWO=[] THREE=[]` |
| `"a b"` `c` (두 인자) | `ALL=["a b" c] ONE=[a b] TWO=[c] THREE=[]` |
| `a` `b` `c` `d` | `ALL=[a b c d] ONE=[a] TWO=[b] THREE=[c d]` |

- 공백이 있는 인자는 `$ARGUMENTS`에 **따옴표가 붙어** 들어가고, `$1`은 따옴표를 뗀 값입니다.
- 없는 위치는 빈 문자열입니다.
- 인자가 자리표시자보다 많으면 **가장 큰 번호의 자리표시자가 나머지를 모두** 받습니다.
- 인자 안의 큰따옴표는 모양이 깨집니다. 따옴표가 필요한 값은 파일 경로로 넘기고 본문에서 읽게 하세요.
- 본문에 `$ARGUMENTS`가 **없는데** 인자를 주면 본문 뒤에 빈 줄을 두고 인자가 덧붙습니다.

### 확인한 frontmatter 키

| 키 | 확인한 동작 |
|---|---|
| `description` | `debug config`에 보인다. 모델 요청에는 들어가지 않는다. TUI의 `/` 목록에 보이는지는 미검증 |
| `agent` | `agent: plan`이면 실행 헤더가 `> plan · ...`이 되고 사용자 메시지 끝에 plan 모드 안내가 붙는다 |
| `model` | `-m`으로 준 모델보다 우선한다. 가리키는 모델이 설정에 없으면 모델 호출 없이 실패(종료 코드 비0) |
| `subtask` | `subtask: true`면 하위 에이전트 작업으로 실행된다 |

이 네 개 밖의 키는 시험하지 않았습니다.

### 없는 명령 이름은 원인을 말해 주지 않습니다

`opencode run --command nosuch hi`는 종료 코드 1, 모델 호출 없이 `UnknownError ... Unexpected server error. Check server logs for details.`만 나옵니다. 이름이 틀렸다는 말이 없고 `--print-logs --log-level ERROR`로 봐도 이름은 안 나옵니다. 오타가 의심되면 `opencode debug config`로 이름을 확인하세요.

### 명령은 글일 뿐입니다

명령은 모델에게 보내는 **글**이라 모델이 어길 수 있습니다. 반드시 지켜야 하는 제약은 `permission`이나 에이전트 권한으로 거세요.

## 모델 제공자 연결: OpenAI 호환 주소

처음 opencode를 쓸 때 가장 먼저 하는 일은 모델이 있는 주소를 알려 주는 것입니다. [C7](../../examples/00-config/c7-provider-openai-compatible/)이 모의 서버(`model_server.py`, 진짜 모델이 아닙니다)로 연결과 실패 증상을 재현합니다.

```json
{
  "provider": {
    "demo-endpoint": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "데모 엔드포인트",
      "options": {
        "baseURL": "{env:LLM_BASE_URL}",
        "apiKey": "{env:LLM_API_KEY}"
      },
      "models": {
        "demo-chat": { "name": "Demo Chat", "limit": { "context": 32768, "output": 4096 } }
      }
    }
  },
  "model": "demo-endpoint/demo-chat"
}
```

| 키 | 의미 |
|---|---|
| `provider.<이름>` | 모델은 `이름/모델id`로 부른다 |
| `npm` | OpenAI 호환 API를 말하는 어댑터 |
| `options.baseURL` | `/chat/completions` 바로 앞까지의 주소 (보통 `.../v1`) |
| `options.apiKey` | `Authorization: Bearer <값>`으로 보내진다 |
| `models.<id>` | `id`가 서버로 가는 `model` 값. `limit`을 따른 동작은 시험하지 않았다(미검증) |
| `model` | `-m`이 없을 때 쓰는 기본 모델 |

저장소에 커밋하는 파일에는 `{env:...}`만 적고 주소와 키는 각자의 셸 환경에서 줍니다. 키를 `opencode.json`에 직접 적지 마세요.

**어댑터는 내려받지 않습니다.** `@ai-sdk/openai-compatible`은 opencode 1.19.5에 들어 있습니다. 레지스트리 주소를 닫은 환경과 네트워크 없는 네임스페이스에서도 첫 `run`이 성공했고 실행 뒤 `@ai-sdk` 패키지가 생기지 않았습니다. 다른 어댑터는 확인하지 않았습니다(미검증).

### 주소나 키가 틀렸을 때

| 상황 | 사용자 화면 | 서버 쪽 |
|---|---|---|
| 키가 틀림 | `Error: Incorrect API key provided` (서버가 준 메시지) | 키 불일치 |
| `LLM_API_KEY` 없음 | 위와 **똑같은** 메시지 | `Authorization` 헤더 자체가 없음 |
| `LLM_BASE_URL` 없음 | `Error: Invalid URL`. 서버에는 요청이 오지 않음 | 없음 |
| 서버가 꺼져 있음 | `Error: Cannot connect to API: ECONNREFUSED: ...` | 없음 |
| `baseURL`에서 `/v1`을 뺌 | 모의 서버는 받아 주지만 | 경로가 `/chat/completions` |

- `{env:}`가 미설정이면 오류 없이 빈 문자열이고, 키가 비면 `Authorization` 헤더를 아예 보내지 않습니다. 화면만으로는 "키 없음"과 "키 틀림"이 구분되지 않아 서버 로그가 필요합니다.
- 서버가 꺼져 있으면 오류가 나오기까지 **약 68초**가 걸렸습니다(원인은 확인하지 않았습니다). 멈춘 것처럼 보여도 기다리면 메시지가 나옵니다.
- `opencode models`는 설정에 적힌 모델을 보여 줄 뿐 서버에 접속하지 않습니다. 환경 변수가 없어도 목록에 나오므로 **연결은 실제로 한 번 질문해 봐야 압니다.**
- `opencode debug config`에서 `baseURL`은 가려지지 않아 환경 변수가 없으면 `""`로 보입니다. `apiKey`는 값이 있든 없든 `***`라서 키가 설정됐는지는 알 수 없습니다.

### `--print-logs`로 원인 찾기

연결이 안 될 때 순서입니다. ① `opencode debug config`에서 `baseURL`이 비어 있지 않은지, ② `opencode run --print-logs --log-level ERROR "안녕"`으로 어느 단계에서 났는지, ③ 서버 쪽 기록에 요청이 왔는지와 `Authorization`이 있는지.

```
level=ERROR ... message="stream error" providerID=demo-endpoint modelID=demo-chat ... error.error="TypeError: Invalid URL"
```

②에서는 어느 provider와 모델에서 났는지까지 나옵니다. 키가 틀린 경우에는 `error.error="AI_APICallError: Incorrect API key provided"`입니다.

## 에이전트 정의: 역할마다 다른 권한

에이전트는 **프롬프트 + 권한 + (선택) 모델**을 한 묶음으로 이름 붙인 것입니다. `opencode run --agent reviewer`처럼 고르면 그 역할로 시작합니다. [C8](../../examples/00-config/c8-agents/)이 세 에이전트(읽기 전용 `reviewer`, `docs/**`만 고치는 `docs`, 조사원 `researcher`)를 가짜 모델로 확인합니다.

정의하는 방법은 두 가지이고 결과는 같습니다.

- `.opencode/agent/이름.md`: frontmatter(`description`, `mode`, `permission`) + **본문이 시스템 프롬프트**
- `opencode.json`의 `agent` 키: `{"이름": {"description", "mode", "prompt", "permission"}}`

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
```

모델 없이 해석 결과를 보는 명령은 `opencode debug agent 이름`입니다.

### 막은 도구는 모델의 도구 목록에서 사라집니다

`permission`에서 통째로 deny한 도구는 모델에게 보내는 도구 목록에서 아예 빠집니다. 모델은 거절당하는 것이 아니라 그런 도구가 있는지도 모릅니다. 모델이 받은 도구 목록입니다.

| 에이전트 | 도구 목록 |
|---|---|
| 기본 `build` | bash, edit, glob, grep, read, skill, task, todowrite, webfetch, write |
| `reviewer` | glob, grep, read, skill, todowrite, webfetch |
| `docs` | edit, glob, grep, read, skill, todowrite, webfetch, write |

- 그래도 모델이 목록에 없는 도구를 부르면 도구는 실행되지 않고 `Model tried to call unavailable tool 'edit'. Available tools: ...`가 도구 결과로 돌아갑니다. 종료 코드는 0이고 대화는 이어집니다.
- `bash`를 `"*": deny` 뒤에 `"git diff*": allow` 같은 패턴 규칙으로 두면 마지막 규칙이 deny가 아니라서 목록에 **남습니다.** `docs`의 `edit`도 `* deny` 다음에 `docs/** allow`가 와서 목록에 남고, 경로는 실행 직전에 검사합니다.

### 경로별 edit 규칙은 git 루트 기준입니다

`docs`가 `docs/**`만 고칠 수 있게 하는 규칙은 **git 저장소 루트를 기준으로 한 상대 경로**와 비교됩니다.

| 시도 | 결과 |
|---|---|
| `docs/guide.md` 수정, `docs/sub/x.md` 쓰기 | 실행됨 (묻지 않음) |
| `src/calc.py` 수정 | 거부 |
| 같은 폴더인데 `.git`이 없음 | `docs/guide.md` 수정도 **거부** |

루트 아래 하위 폴더의 `sub/docs/g.md`도 `docs/**`에 걸리지 않아 거부됩니다. 그래서 예제는 `prepare.py`로 자체 git 저장소인 `sandbox/`를 만듭니다. 이 저장소의 예제 폴더에서 바로 실행하면 같은 이유로 맞지 않을 것입니다(추정, 직접 시험하지 않음).

### `mode`: primary와 subagent

| | `mode: primary` | `mode: subagent` |
|---|---|---|
| `--agent 이름`으로 시작 | 됨 | 안 됨. 경고 후 `build`로 실행 |
| 다른 에이전트의 `task` 도구 설명 | 나오지 않음 | 나옴 (내장 `explore`, `general`과 함께) |
| 쓰는 방식 | 사용자가 고른 대화의 주인공 | 주인공이 `task`로 넘기는 하위 작업. 자기 프롬프트와 권한으로 돈다 |

`--agent`에 subagent나 없는 이름을 주면 `agent "nosuch" not found. Falling back to default agent` 같은 경고 한 줄과 함께 `build`로 실행합니다. **종료 코드가 0이라 오타가 조용히 넘어갑니다.** 권한을 믿고 돌리기 전에 실행 헤더(`> reviewer`)를 확인하세요.

### 함정: `task`가 열려 있으면 읽기 전용이 우회됩니다

`task: deny`만 지운 사본으로 확인했습니다. `edit`이 목록에 없는 `reviewer`가 `task`로 내장 `general` 하위 에이전트를 부르자, `general`은 **자기 권한으로** `src/calc.py`를 실제로 고쳤습니다. 하위 작업은 부른 쪽의 제한을 물려받지 않습니다. 읽기 전용 에이전트를 만들 때는 `edit`, `bash`만큼 `task`도 막으세요. 실제 모델의 응답은 확인하지 못했습니다(미검증, 위 결과는 가짜 모델).

## 셋의 차이: 스킬, 명령, 에이전트

모델에게 글이나 권한을 주는 세 가지가 헷갈리기 쉽습니다. 모두 C6, C8에서 모델이 받은 요청을 읽어 확인한 값입니다.

| | 스킬 ([2장](02-skills.md)) | 명령 ([C6](../../examples/00-config/c6-custom-commands/)) | 에이전트 ([C8](../../examples/00-config/c8-agents/)) |
|---|---|---|---|
| 정의하는 것 | 절차와 지식 | 지시문 한 덩어리 | 역할: 프롬프트 + 권한 (+ 모델) |
| 누가 시작하나 | 모델 (description을 보고) | 사용자 (`/이름`, `--command`) | 사용자(`--agent`) 또는 모델(`task`) |
| 부르기 전 모델 요청에 있는 것 | 이름 + description (예제에서 103자. 스킬 파일 경로도 함께 실리므로 설치 위치에 따라 300자 안팎) | **아무것도 없음** | 고른 에이전트 외에는 거의 없음. 단 subagent의 description은 모든 요청의 `task` 도구 설명에 들어간다 |
| 본문이 들어오는 때와 곳 | 모델이 `skill` 도구를 부를 때, **도구 결과**로 | 사용자가 부를 때, **사용자 메시지**로 | 고르면 시스템 프롬프트와 도구 목록이 바뀜 |
| 인자 | 없음 (대화에서 읽음) | `$ARGUMENTS`, `$1` `$2` | 없음 |
| 권한을 바꾸나 | 아니오 | `agent:` 키로 에이전트를 고르면 간접적으로 | **예** (도구가 목록에서 빠짐) |

같은 280자 지시문을 명령과 스킬로 두었을 때 스킬의 목록 항목(103자)이 본문과 같은 자릿수였습니다. 이렇게 짧은 글은 스킬로 둬도 이득이 크지 않습니다. 스킬은 본문이 길고 **가끔만** 필요할 때, 명령은 **내가 정확히 그 순간에 부르고 싶을 때** 맞습니다. 비교를 위해 두 개를 같이 둔 것은 예제뿐이고, 실제 프로젝트에서는 둘 중 하나만 두세요. 둘 다 있으면 모델이 스킬을 불러 같은 지시를 두 번 받을 수 있습니다.

## 이 장에서 기억할 것

- 우선순위: 전역 < `OPENCODE_CONFIG` < 프로젝트 `opencode.json` < `.opencode/opencode.json` < `OPENCODE_CONFIG_CONTENT`
- 배열은 이어 붙고, 객체는 키 단위로 합쳐지고, 객체를 문자열로 바꾸면 통째로 교체됩니다.
- 최상위 키 오타는 조용히 사라집니다. 항상 `opencode debug config`로 확인합니다.
- `{env:}` 미설정은 빈 문자열, `${}`는 치환 안 됨, `{file:}` 없는 파일은 시작 거부.
- 마스킹은 이름 기반입니다. `***`를 믿고 출력을 공유하지 마세요.
- permission은 마지막으로 맞는 규칙이 이깁니다.
- 명령은 사용자가 부를 때만 글이 들어가고, 스킬은 이름과 description이 항상 들어갑니다. 없는 명령 이름은 이유 없이 `Unexpected server error`입니다.
- 모델 연결 문제는 `debug config`의 `baseURL`, `--print-logs`, 서버 기록 순으로 가릅니다. 키 없음과 키 틀림은 화면이 같습니다.
- 에이전트의 deny는 도구를 목록에서 지웁니다. 읽기 전용이라면 `task`도 막고, `--agent` 오타는 조용히 `build`로 넘어갑니다.

막힐 때는 [5. 문제 해결](05-troubleshooting.md)의 표를 먼저 보세요.

다음: [2. 스킬](02-skills.md)
