# 1. opencode.json: 위치, 병합, 변수, 권한

이 문서는 세미나 3장 "설정"을 글로 옮긴 것입니다. 설정 파일을 어디에 두는지, 여러 파일이 어떻게 합쳐지는지, 비밀값을 어떻게 다루는지, 권한을 어떻게 선언하는지 다룹니다.
모든 내용은 **opencode 1.19.5** 기준입니다.

관련 예제: [C1 범위와 병합](../../examples/00-config/c1-scope-merge/) · [C2 변수와 마스킹](../../examples/00-config/c2-variables/) · [C3 실행할 때만 얹기](../../examples/00-config/c3-config-content-overlay/) · [C4 격리 실험](../../examples/00-config/c4-isolated-testing/) · [C5 권한](../../examples/00-config/c5-permissions/)

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
- `mcp` 항목 안의 오타나 잘못된 값(`"bash": "maybe"`)은 `Configuration is invalid`로 시작 자체를 막습니다.

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

## 이 장에서 기억할 것

- 우선순위: 전역 < `OPENCODE_CONFIG` < 프로젝트 `opencode.json` < `.opencode/opencode.json` < `OPENCODE_CONFIG_CONTENT`
- 배열은 이어 붙고, 객체는 키 단위로 합쳐지고, 객체를 문자열로 바꾸면 통째로 교체됩니다.
- 최상위 키 오타는 조용히 사라집니다. 항상 `opencode debug config`로 확인합니다.
- `{env:}` 미설정은 빈 문자열, `${}`는 치환 안 됨, `{file:}` 없는 파일은 시작 거부.
- 마스킹은 이름 기반입니다. `***`를 믿고 출력을 공유하지 마세요.
- permission은 마지막으로 맞는 규칙이 이깁니다.

막힐 때는 [5. 문제 해결](05-troubleshooting.md)의 표를 먼저 보세요.

다음: [2. 스킬](02-skills.md)
