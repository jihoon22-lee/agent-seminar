# P8 플러그인을 불러오는 방법들

> 구성: 플러그인(로드 방법 비교) | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: 플러그인 - 배포·로드 방법

## 무엇을 보여 주나

플러그인을 만드는 것과 **어떻게 불러오게 하느냐**는 별개입니다. 같은 아주 작은 플러그인(`hello.js`)을
네 가지 방법으로 불러 보고, 실제로 로드됐는지·몇 번 로드됐는지·`--pure` 에서는 어떻게 되는지를 `demo.py` 가 표로 보여 줍니다.
"팀원에게 플러그인을 어떻게 나눠 줄까?" 에 대한 선택지 비교표라고 생각하면 됩니다.

| | 방법 | 쓰는 때 |
|---|---|---|
| (a) | 프로젝트 `.opencode/plugins/` 에 파일을 둔다 (자동 탐색) | 이 저장소에서만 쓰는 플러그인. 저장소에 커밋해서 팀이 공유 |
| (b) | 전역 폴더 `~/.config/opencode/plugins/` 에 파일을 둔다 | 모든 프로젝트에서 쓰는 개인 플러그인 |
| (c) | `opencode.json` 의 `"plugin"` 에 경로를 쓴다 (`./상대경로`, `file:///절대경로`) | 파일 위치를 직접 정하고 싶을 때, 옵션을 넘기고 싶을 때 |
| (d) | npm 패키지 형태(`package.json` 이 있는 폴더 / npm 이름) | 여러 저장소에 배포·버전 관리 하고 싶을 때 |

## 실무에서는

- **팀 공용 가드/로깅 플러그인**을 저장소에 넣어 두는 건 (a). 클론하면 바로 적용됩니다.
- **개인 취향 플러그인**(알림, 단축 훅)은 (b). 프로젝트 파일은 건드리지 않습니다.
- **여러 저장소가 같은 플러그인**을 쓴다면 (d): 패키지로 만들어 자체 레지스트리/미러에 올리고 `"plugin": ["이름@1.2.0"]` 으로 버전을 고정합니다.
- 플러그인이 의심스러울 때는 `opencode --pure` 로 "플러그인 없이" 재현해서 원인이 플러그인인지 가려냅니다.

## 파일 구성

```
p8-load-methods/
├── README.md
├── demo.py                          # 시나리오별로 임시 폴더를 만들고 opencode 를 실행해 로드 결과를 표로 출력
├── check.py                         # demo.py 의 모든 시나리오를 검증 (모델 불필요)
├── mini_registry.py                 # npm 레지스트리 흉내 (표준 라이브러리). (d)의 npm 이름 형태를 오프라인으로 시험
├── plugins/
│   └── hello.js                     # 시험용 플러그인: 로드 마커 한 줄 기록 + shell.env 훅
└── packages/
    └── opencode-hello/              # (d) npm 패키지 형태: hello.js 와 같은 코드 + package.json(main/exports)
        ├── package.json
        └── index.js
```

`hello.js` 가 하는 일은 두 가지뿐입니다.

1. 로드될 때마다 마커 파일(`HELLO_MARKER` 환경 변수가 가리키는 파일, 없으면 `logs/hello-loaded.log`)에 JSON 한 줄을 남깁니다. 줄 수가 곧 **로드된 횟수**입니다.
2. `shell.env` 훅으로 bash 도구가 실행하는 명령의 환경 변수에 `HELLO_LOADED=yes` 를 넣습니다.

## 따라 하기

> 이 예제는 모델을 쓰지 않습니다. 평소 쓰는 모델·무료 모델 설정이 필요 없습니다.

### 1. 전부 실행해 보기

`demo.py` 는 시나리오마다 **새 임시 폴더와 임시 XDG 폴더**를 만들어 그 안에서만 opencode 를 실행합니다. 내 실제
`~/.config/opencode` 는 읽지도 쓰지도 않습니다. ((b)의 "전역 폴더"도 임시 XDG 폴더 안입니다.)

PowerShell:

```powershell
cd examples\03-plugins\p8-load-methods
python demo.py
```

Linux (bash) - `python` 명령이 없으면 `python3` 로 바꾸세요:

```bash
cd examples/03-plugins/p8-load-methods
python3 demo.py
```

골라서 실행하거나 목록을 볼 수도 있습니다.

```
python demo.py --list          # 시나리오 목록
python demo.py a d3 pure       # 골라서 실행
python demo.py a --keep        # 임시 폴더를 지우지 않고 남김 (안을 직접 열어 보고 싶을 때)
```

전체 실행에 1~2분 걸립니다(시나리오마다 opencode 를 새로 띄웁니다).

### 2. 직접 해 보기 - (a) 자동 탐색

```powershell
mkdir sandbox\.opencode\plugins
copy plugins\hello.js sandbox\.opencode\plugins\
cd sandbox
opencode debug config          # plugin 항목에 file:///.../sandbox/.opencode/plugins/hello.js 가 보인다
type logs\hello-loaded.log     # 마커가 한 줄 생겼다
```
```bash
mkdir -p sandbox/.opencode/plugins
cp plugins/hello.js sandbox/.opencode/plugins/
cd sandbox
opencode debug config          # plugin 항목에 file:///.../sandbox/.opencode/plugins/hello.js 가 보인다
cat logs/hello-loaded.log      # 마커가 한 줄 생겼다
```

`opencode debug config` 도 플러그인을 로드합니다. 그래서 모델 없이 로드 여부를 확인하는 가장 쉬운 방법입니다.
(`sandbox/` 는 `.gitignore` 대상입니다.)

## 기대 결과

실제 실행 결과입니다(Linux, opencode 1.19.5, 일부 줄임). 모델은 쓰지 않았습니다.

```
[OK] a     (a) 자동 탐색  (7.3s)
       방법    : .opencode/plugins/hello.js 에 파일만 두기
       로드 횟수: 1 (기대 1)
       - project/.opencode/plugins/hello.js
       shell.env 확인: HELLO_LOADED=yes

[OK] b     (b) 전역 폴더
       - xdg-config/opencode/plugins/hello.js

[OK] c1    (c) 상대 경로         - project/plugins/hello.js
[OK] c2    (c) file:/// 절대 경로 - project/plugins/hello.js
[OK] c3    (c) [경로, 옵션]       플러그인이 받은 옵션: {'greeting': '안녕'}
[OK] d1    (d) 패키지 폴더(상대 경로) - project/packages/opencode-hello/index.js
[OK] d2    (d) 패키지 폴더(file:///)  - project/packages/opencode-hello/index.js
[OK] d3    (d) npm 이름 + 패키지 미러
       - xdg-cache/opencode/packages/opencode-hello@1.0.0/node_modules/opencode-hello/index.js

[OK] e1    중복: 같은 경로 두 번                 로드 횟수: 1
[OK] e2    중복: 상대 경로 + 절대 경로            로드 횟수: 1
[OK] e3    중복: 자동 탐색 + 설정에서 같은 파일    로드 횟수: 1
[OK] e4    중복: 같은 내용, 다른 위치의 파일 2개   로드 횟수: 2
[OK] f1    자동 + 전역 + 설정 모두 켜기           로드 횟수: 3
[OK] pure  --pure  설정에는 플러그인 3개가 적혀 있지만 실행되지 않음   로드 횟수: 0
```

## 동작 원리

### (a) 자동 탐색
`.opencode/plugins/`(옛 이름 `.opencode/plugin/` 도 동작)의 `.js`/`.ts` 파일은 설정 없이 모두 로드됩니다.
`opencode debug config` 의 `plugin` 배열에는 이런 파일이 `file:///...` 주소로 **자동으로 추가되어** 나타납니다(확인).

### (b) 전역 폴더
`<설정 폴더>/plugins/` 입니다. 설정 폴더는 `opencode debug paths` 의 `config` 줄입니다.
Linux `~/.config/opencode`, Windows `%USERPROFILE%\.config\opencode`. `XDG_CONFIG_HOME` 을 바꾸면 그 아래 `opencode/` 로 옮겨 갑니다
(`demo.py` 가 이를 이용해 임시 폴더를 "전역"으로 씁니다).

### (c) `opencode.json` 의 `"plugin"`
```json
{ "$schema": "https://opencode.ai/config.json",
  "plugin": ["./plugins/hello.js", "file:///C:/work/tools/other.js", ["./plugins/hello.js", { "greeting": "안녕" }]] }
```
- 상대 경로는 프로젝트 폴더(`opencode.json` 이 있는 폴더)에서 실행했을 때 그 폴더 기준으로 풀렸습니다. (하위 폴더에서 실행했을 때의 기준은 확인하지 못했습니다.)
- `file:///절대경로` 도 됩니다. Windows 는 `file:///C:/work/...` 형태입니다.
- `[경로, 옵션객체]` 로 쓰면 플러그인 함수의 **두 번째 인자**로 옵션을 받습니다(확인: `c3`).

### (d) npm 패키지 형태
- **로컬 폴더**: `package.json` 이 있는 폴더를 가리키면 됩니다. `"./packages/opencode-hello"`, `"file:///.../packages/opencode-hello"` 둘 다 동작(확인).
  진입점은 **`main` 으로 정해집니다.** `main: "./dist/main.js"` 는 동작했고, `exports` 만 있고 `main` 이 없는 폴더, `main` 도 `index.js` 도 없는 폴더는 **조용히 로드되지 않았습니다.** (`main` 없이 `index.js` 만 있는 경우는 확인하지 못했습니다.)
  그러니 로컬 폴더용 패키지에는 `main` 을 꼭 쓰세요(이 예제는 `main` 과 `exports` 를 함께 둡니다).
- **npm 이름**: `"plugin": ["opencode-hello@1.0.0"]` 또는 이름만(`"opencode-hello"` = 최신). opencode 가 레지스트리에서 받아
  `<캐시 폴더>/opencode/packages/opencode-hello@1.0.0/node_modules/opencode-hello` 에 설치하고 로드합니다.
  **레지스트리가 필요**합니다. 인터넷이 막힌 환경이면 패키지 미러를 지정해야 합니다.
  - `demo.py` 의 `d3` 는 `mini_registry.py`(패키지 폴더를 tarball 로 내려 주는 50줄짜리 가짜 레지스트리)를 띄우고
    `npm_config_registry` 환경 변수로 그 주소를 지정해서, 이름 형태가 **레지스트리 주소만 바꾸면 그대로 동작함**을 오프라인으로 확인합니다.
  - 레지스트리를 지정하는 방법: 사용자 `~/.npmrc`(Windows `%USERPROFILE%\.npmrc`)의 `registry=...` 또는 환경 변수 `npm_config_registry`.
    **프로젝트 루트의 `.npmrc` 는 적용되지 않았습니다**(확인). 자세한 내용은 [P6](../p6-custom-tool/) 의 "주의할 점".
  - 로컬 폴더(`file:`) 방식은 레지스트리가 필요 없으므로 오프라인 환경에서 가장 현실적인 배포 방법입니다. 팀 공용 폴더나 저장소에 패키지 폴더를 두고 경로를 쓰세요.

### 중복해서 지정하면?
- **같은 파일**을 어떻게 가리키든(상대+절대, 같은 경로 두 번, 자동 탐색+설정에서 또 지정) **한 번만 로드**됩니다. `plugin` 배열에서도 하나로 합쳐집니다(`e1`~`e3`).
- 내용이 같아도 **파일 위치가 다르면 별개 플러그인**이라 각각 로드됩니다(`e4`: 2회). 전역 폴더와 프로젝트 폴더에 같은 플러그인을 두면 2회 로드됩니다(`f1`: 3회).
  → 같은 훅이 두 번 실행됩니다. 로그가 두 번 찍히거나, 가드가 두 번 돌 수 있으니 한 곳에만 두세요.
- 한 파일에서 여러 함수를 `export` 하면 **전부 플러그인으로 호출**됩니다. 도우미 함수는 내보내지 마세요.
  함수가 아닌 값(`export const NAME = "x"`)을 하나라도 내보내면 **그 파일의 플러그인이 모두 조용히 로드되지 않습니다**(확인).

### `--pure` (`OPENCODE_PURE=1` 도 동일)
외부 플러그인(자동 탐색·전역 폴더·`plugin` 설정·npm)을 **하나도 로드하지 않습니다.** `opencode debug config` 의 `plugin` 배열에는 여전히 적혀 있지만 실행되지 않습니다(`pure`: 0회).
같은 구성에서 스킬과 MCP 서버(`mcp list`)는 `--pure` 에서도 그대로 보입니다(확인: [X2](../../04-combined/x2-incident-analysis/) 폴더에서). 즉 **플러그인만 끄는 스위치**입니다.
또한 `.opencode/` 의 npm 자동 설치도 하지 않아 시작이 빨라집니다(1~2초).

### 플러그인이 받는 인자 (확인)
`async ({ client, project, directory, worktree, serverUrl, $, experimental_workspace }, options)`.
git 저장소가 아닌 곳에서는 `project.id` 가 `"global"`, `worktree` 가 `/` 로 나옵니다. 플러그인은 opencode 에 내장된 Bun 런타임에서 실행됩니다.

## 직접 바꿔 보기

1. `python demo.py a --keep` 으로 임시 폴더를 남기고 `project/opencode.json`(없음), `marker.log` 를 열어 보세요. 마커의 `loadedFrom` 이 실제로 로드된 파일입니다.
2. `plugins/hello.js` 에 `export const NOT_A_PLUGIN = 42` 를 추가하고 `python demo.py c1` 을 실행해 보세요. 로드 횟수가 0이 됩니다. 지우면 다시 1.
3. `packages/opencode-hello/` 에서 `index.js` 를 `dist/main.js` 로 옮기고 `main` 을 `./dist/main.js` 로 고친 뒤 `python demo.py d1` 을 실행해 보세요. 진입점이 `main` 으로 정해지는지 확인합니다. 확인 후 원래대로 되돌리세요. `check.py` 가 두 파일(`hello.js`, `index.js`)이 같은 내용이어야 통과하니 `hello.js` 를 고쳤다면 `index.js` 에도 같이 반영하세요.

## 주의할 점 / 문제 해결

- **로드 실패는 대부분 조용합니다.** `import` 오류, 문법 오류, 잘못된 진입점은 로그에도 안 남습니다. 플러그인 첫 줄에서 마커 파일에 쓰는 코드를 넣어 두면 "로드 자체가 안 된 건지, 훅이 안 불린 건지" 를 가를 수 있습니다.
  플러그인 함수가 **초기화 중 예외**를 던지면 `opencode --print-logs` 에서 `level=ERROR message="failed to load plugin"` 이 보입니다.
- 플러그인을 고친 뒤에는 **opencode 를 다시 시작**해야 합니다(실행 중에는 다시 읽지 않습니다).
- `.opencode/` 가 있는 폴더에서는 처음 시작할 때 `@opencode-ai/plugin` 을 npm 으로 설치합니다. 레지스트리에 닿지 않으면 약 70초 멈췄다가 계속됩니다. 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다.
  (이 예제의 `hello.js` 는 그 패키지를 import 하지 않아서 멈춘 뒤에도 정상 로드됩니다). 미러 지정은 [P6](../p6-custom-tool/) 참고.
- **Windows 에서 `shell.env` 확인**: Windows 의 bash 도구가 쓰는 셸이 PowerShell 일 수 있어(`$HELLO_LOADED` 가 안 풀림) `demo.py` 는 Windows 에서
  `python -c "import os; ..."` 로 환경 변수를 읽습니다. 실제 모델 세션에서 확인할 때도 셸 문법 차이를 기억하세요(PowerShell: `$env:HELLO_LOADED`).
- (d)의 npm 이름 시나리오(`d3`)는 Windows 에서 드물게 첫 시도에 0회로 끝난 적이 있어(원인 미확인, 이후 5/5 정상) `demo.py` 가 한 번 재시도합니다.
- `sandbox/`, `logs/` 는 `.gitignore` 대상입니다.
