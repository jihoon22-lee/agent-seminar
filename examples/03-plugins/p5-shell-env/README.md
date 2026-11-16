# P5 셸 환경변수 주입 (shell-env)

> 구성: 플러그인(JS) `shell.env` | 난이도: ★☆☆ | 필요: opencode 1.19.5, Python 3.10+ (Node 는 단위 테스트에만) | 슬라이드: 플러그인 — 환경 주입

## 무엇을 보여 주나

`shell.env` 훅은 에이전트가 셸 명령(`bash` 도구)을 실행하기 직전에 호출되어, 그 명령의 환경변수에 값을 덧붙일 수 있게 해 줍니다.
사용자의 터미널이나 시스템 설정은 건드리지 않고, **에이전트가 실행하는 명령에서만** `APP_ENV=dev`, 프록시 주소, 사설 CA 인증서 경로 같은 값이 보이게 됩니다.

## 실무에서는

- 사설 인증서를 쓰는 환경에서 `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE` 을 에이전트의 셸에만 지정해, 에이전트가 돌리는 `pip`·`curl`·테스트가 인증서 오류로 멈추는 것을 막습니다.
- 팀 공용 프록시나 패키지 미러 주소를 프로젝트마다 다르게 주입합니다. 사용자는 셸 프로필을 건드릴 필요가 없습니다.
- `APP_ENV=dev`, `DATABASE_URL=sqlite:///dev.db` 처럼 "에이전트는 항상 개발 환경에서만 일한다"는 전제를 코드로 고정합니다. (운영 DB 주소가 에이전트 셸에 섞여 들어가는 사고를 줄입니다.)

## 파일 구성

```
p5-shell-env/
├── README.md
├── fake_llm.py                       # 검증용 가짜 LLM (표준 라이브러리만, 복사본)
├── check.py                          # 자동 검증 (단위 테스트 + 플러그인 로드 + --model 모델 검사)
├── show_env.py                       # 환경변수 5개를 출력하는 확인용 스크립트
├── certs/demo-ca.pem                 # 자리표시용 가짜 파일 (진짜 인증서 아님)
├── .opencode/plugins/shell-env.js    # 플러그인 본체 (주입할 변수 표가 이 안에 있음)
├── tests/shell-env.test.mjs          # 훅을 직접 호출하는 시험 (node)
└── logs/                             # 실행하면 생김: plugin-load.log, shell-env.log
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. (모델 설정이 없다면 무료 모델 `-m opencode/big-pickle` 을 붙이세요.)

1. 먼저 내 터미널에서 확인합니다. 아직 아무것도 주입되지 않았으므로 전부 `None` 입니다.

   PowerShell:
   ```powershell
   cd examples\03-plugins\p5-shell-env
   python show_env.py
   ```
   Linux bash (`python` 명령이 없으면 `python3`로 바꾸세요):
   ```bash
   cd examples/03-plugins/p5-shell-env
   python3 show_env.py
   ```

2. 이 폴더에서 opencode 를 실행합니다. 처음 실행하면 opencode 가 `.opencode/` 안에 `@opencode-ai/plugin` 을 npm 으로 설치하려고 합니다. 인터넷이 막혀 있고 패키지 미러도 없으면 첫 시작이 70초쯤 멈췄다가 계속 진행됩니다. 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 아주 처음, 새 환경에서의 첫 시작은 약 130초까지 걸렸습니다(패킷을 조용히 버리는 레지스트리면 200초를 넘을 수도 있습니다). 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다.

   ```
   opencode
   ```

3. 프롬프트:

   - `bash 도구로 python 한 줄을 실행해서 환경변수 APP_ENV 의 값을 출력해 줘.`
   - `bash 도구로 python show_env.py 를 실행해서 결과를 그대로 보여줘.` (Linux 에서 `python` 이 없으면 `python3`)

4. 비대화식: `opencode run --auto "bash 도구로 python show_env.py 를 실행하고 결과를 그대로 보여줘"`

5. 자동 검증: `python check.py` / `python check.py --model`.

## 기대 결과

아래 출력은 `check.py` 가 쓰는 **가짜 LLM**(`fake_llm.py`: 정해진 도구 호출을 대신 수행하는 OpenAI 호환 서버, 표준 라이브러리만 사용)으로 실제 `opencode 1.19.5` 를 실행해 얻은 것입니다. 모델이 무엇을 시키든 플러그인이 어떻게 반응하는지를 매번 똑같이 재현할 수 있습니다. 실제 모델(무료 모델)로는 이번 확인 시점에 한도 초과/시간 초과로 결과를 얻지 못해 **미검증**입니다. 평소 쓰는 모델로 해 보면 모델의 말투와 시도 순서는 다르겠지만 차단/기록 동작은 같아야 합니다.

가짜 LLM 이 `python -c "import os; print('APP_ENV=' + ... + ' CA=' + ...)"` 를 bash 로 실행했을 때, 명령 출력(= 모델이 받은 결과):

Linux:
```
APP_ENV=dev CA=/home/…/examples/03-plugins/p5-shell-env/certs/demo-ca.pem
```
Windows (bash 도구 = Windows PowerShell 5.1, `python` 은 Windows 용):
```
APP_ENV=dev CA=C:\Users\…\examples\03-plugins\p5-shell-env\certs\demo-ca.pem
```

같은 값을 내 터미널에서 `python show_env.py` 로 보면:

```
APP_ENV=None
HTTP_PROXY=None
HTTPS_PROXY=None
NO_PROXY=None
REQUESTS_CA_BUNDLE=None
```

`logs/shell-env.log`:

```
2026-11-16T17:10:45.002Z injected APP_ENV,HTTP_PROXY,HTTPS_PROXY,NO_PROXY,REQUESTS_CA_BUNDLE cwd=/home/…/p5-shell-env
```

## 동작 원리

1. `shell.env(input, output)` 의 모양 (1.19.5 에서 관찰)
   - `input`: `{ cwd, sessionID, callID }`. `cwd` 는 명령이 실행될 폴더이고, 윈도에서는 `C:\...` 형식입니다.
   - `output.env`: **처음에는 빈 객체입니다.** 현재 환경 전체가 들어 있는 것이 아니라, 여기에 넣은 키만 기존 환경 위에 덮어씌워집니다. 그래서 `Object.assign(output.env, {...})` 로 넣을 값만 적으면 됩니다.
2. 이 훅은 `bash` 도구가 호출될 때마다 불립니다 (`read`/`edit` 에서는 불리지 않습니다). 호출 순서는 `tool.execute.before` → (권한 확인) → `shell.env` → 명령 실행 → `tool.execute.after` 입니다.
3. `REQUESTS_CA_BUNDLE` 은 `directory`(opencode 를 실행한 프로젝트 폴더)와 `path.join` 으로 **절대 경로**를 만듭니다. `./certs/demo-ca.pem` 같은 상대 경로는 명령이 실행되는 `cwd` 에 따라 달라지므로 쓰지 않았습니다.
4. 프록시 값(`HTTP_PROXY` 등)은 데모용입니다. 실제 프록시가 없는데 주소만 넣으면 에이전트가 하는 네트워크 명령이 모두 실패하므로 `NO_PROXY=*`(모든 주소는 프록시를 거치지 않는다)를 함께 넣어 영향이 없게 했습니다. 실제 프록시를 쓸 때는 이 세 줄을 실제 주소와 예외 목록으로 바꾸세요.
5. `certs/demo-ca.pem` 은 주석만 있는 가짜 파일입니다. 실제 인증서를 넣을 때도 비밀 키(개인 키)는 저장소에 넣지 마세요. CA 인증서(공개 인증서)만 해당됩니다.

### 윈도에서 bash 도구는 어떤 셸인가

이번 확인(Windows 11, Git for Windows 설치됨)에서 opencode 1.19.5 의 `bash` 도구는 **Git Bash 도 cmd 도 아닌 Windows PowerShell 5.1**(`powershell.exe`, `PSEdition=Desktop`)로 명령을 실행했습니다.

- `$BASH_VERSION`, `$SHELL`, `$APP_ENV` 같은 `$이름` 은 PowerShell 변수라서 환경변수가 있어도 **빈 값**으로 나옵니다. 환경변수는 `$env:APP_ENV` 로 읽어야 합니다. 그래서 이 예제는 셸에 상관없는 `python -c` 한 줄(또는 `show_env.py`)로 확인합니다.
- `uname` 같은 리눅스 명령은 "인식되지 않습니다" 오류가 납니다. 한국어 윈도의 PowerShell 오류 메시지는 cp949 라서 터미널에 따라 깨져 보일 수 있습니다.
- `OPENCODE_GIT_BASH_PATH=C:\Program Files\Git\bin\bash.exe` 를 지정해 봤지만 **한 번의 시험에서는** 셸이 바뀌지 않고 여전히 PowerShell 이었습니다. 지원하지 않는다고 단정하지는 않지만, 이 버전에서 Git Bash 로 바꾸는 방법은 확인하지 못했습니다.
- 출력 줄 끝은 `\r\n` 입니다. (훅의 `output.output` 에서 관찰)
- Linux 에서는 이번 확인에서 `/bin/bash` 로 실행됐습니다.

## 직접 바꿔 보기

1. `injected` 표에 `TZ: "Asia/Seoul"` 을 추가하고, 에이전트에게 `python -c "import os,time; print(os.environ.get('TZ'), time.strftime('%H:%M'))"` 를 실행시켜 보세요.
2. `NO_PROXY: "*"` 줄을 지운 뒤 `python -c "import urllib.request as u; print(u.getproxies())"` 를 실행시켜, 파이썬이 프록시 설정을 어떻게 읽는지 보세요.
3. `shell.env` 안에서 `input.cwd` 를 보고 폴더별로 다른 값을 주입해 보세요. (예: `cwd` 에 `services\api` 가 들어 있으면 `APP_ENV=api-dev`)

## 주의할 점 / 문제 해결

- 주입은 **에이전트가 실행한 셸 명령에만** 적용됩니다. 에이전트가 만든 스크립트를 나중에 내 터미널에서 실행하면 값이 없습니다 (그래서 1단계 `show_env.py` 가 전부 `None` 입니다).
- 환경변수 값은 모델이 `env`/`printenv` 로 읽을 수 있어서, **비밀(API 키 등)을 여기에 넣으면 모델 입력으로 전달될 수 있습니다.** 비밀이 필요한 도구는 따로 분리하세요.
- `REQUESTS_CA_BUNDLE` 이 가짜 인증서를 가리키므로, 이 폴더에서 에이전트가 `requests`·`pip` 로 HTTPS 요청을 하면 인증서 오류가 납니다. 데모용 설정이니 다른 프로젝트에 복사할 때는 값을 바꾸세요.
- **export 는 플러그인 함수만 하세요.** 숫자·문자열·객체 같은 함수가 아닌 값(`export const X = 1`)을 export 하면 opencode 가 **파일 전체를 건너뜁니다.** 평소 실행에는 아무 출력도 없고, `opencode --print-logs` 로 실행해야 `failed to load plugin ... Plugin export is not a function` 오류가 보입니다. 보조 함수를 export 하면 파일은 로드되지만 그 함수까지 플러그인으로 호출됩니다. 그러니 도우미는 export 하지 마세요. 문법 오류나 import 오류는 `--print-logs` 에도 아무것도 남기지 않으니, 플러그인이 로드됐는지는 플러그인이 직접 남기는 흔적(로드 로그 등)으로 확인하세요.
- `node` 가 없으면 `check.py` 가 경고(WARN)를 내고 단위 테스트를 건너뜁니다. opencode 실행에는 Node 가 필요 없습니다.
