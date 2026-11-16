# C1 설정 범위와 병합 규칙

> 구성: 설정 파일 4개 + 환경변수 2개 | 난이도: ★☆☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: 설정 (opencode.json)

## 무엇을 보여 주나

opencode 설정은 한 파일이 다른 파일을 **교체**하지 않고 **병합**됩니다. 전역 설정, 팀 공용 설정, 프로젝트 설정, 한 번만 쓰는 설정이 층층이 쌓이고, 같은 키가 겹치면 위쪽 층이 이깁니다.
이 예제는 다섯 단계로 층을 하나씩 쌓으면서 `opencode debug config` 의 결과가 어떻게 달라지는지, 그리고 **어느 층 때문에** 그 값이 되었는지 표로 보여 줍니다.
특히 "배열은 이어 붙고, 객체는 키 단위로 합쳐지고, 단일 값만 덮어쓴다"는 규칙을 직접 확인할 수 있습니다.

## 실무에서는

- 팀 공용 기본값(예: 위험한 명령은 `ask`)을 한 파일로 배포하고, 개인은 `OPENCODE_CONFIG=팀파일.json` 으로 가져다 씁니다. 개인 전역 설정은 그대로 두고 그 위에 팀 규칙이 얹힙니다.
- 저장소마다 `opencode.json` 을 두어 그 프로젝트에서만 쓰는 MCP 서버와 지침(`instructions`)을 정합니다. 저장소를 clone 한 동료도 같은 설정을 받습니다.
- 내 PC에서만 필요한 설정은 커밋하지 않는 `.opencode/opencode.json` 에 두거나, 실행할 때만 `OPENCODE_CONFIG_CONTENT` 로 얹습니다. (C3 참고)
- "왜 이 MCP가 켜져 있지?", "왜 이 명령이 허용되지?" 같은 질문은 `opencode debug config` 로 병합 결과를 보면 바로 답이 나옵니다.

## 파일 구성

```
c1-scope-merge/
  README.md
  demo.py                       다섯 시나리오를 실행해 표로 보여 주는 데모 (표준 라이브러리만)
  check.py                      자동 검증 (모델 호출 없음)
  global-config/opencode.json   "전역 설정" 대역. 실제 ~/.config/opencode 는 건드리지 않는다
  team-defaults.json            OPENCODE_CONFIG 로 가리킬 팀 공용 설정
  opencode.json                 프로젝트 루트 설정
  .opencode/opencode.json       프로젝트 .opencode 폴더 설정
```

모든 파일은 `username`, `share`, `instructions`, `"enabled": false` 인 MCP 항목, `permission` 같은 **무해한 키**만 씁니다. 모델 설정(`model`)은 없습니다. `instructions` 에 적힌 `*-rules.md` 파일은 실제로 존재하지 않아도 오류가 나지 않습니다.

## 우선순위 (낮음 → 높음)

```
 1. 전역          ~/.config/opencode/opencode.json     (이 예제에서는 임시 XDG_CONFIG_HOME 으로 대체)
        │  덮어씀
 2. OPENCODE_CONFIG=파일경로                            (team-defaults.json)
        │  덮어씀
 3. 프로젝트 루트  opencode.json                         (작업 폴더에서 위로 올라가며 찾음)
        │  덮어씀
 4. 프로젝트       .opencode/opencode.json
        │  덮어씀
 5. OPENCODE_CONFIG_CONTENT=JSON 문자열                  (환경변수, 파일이 아님)
```

병합 규칙은 값의 종류마다 다릅니다.

| 값의 종류 | 예 | 규칙 |
|---|---|---|
| 단일 값 | `username`, `share` | 가장 높은 층의 값 하나만 남는다 |
| 배열 | `instructions` | **교체되지 않고** 낮은 층부터 차례로 이어 붙는다. 같은 항목은 한 번만 남는다 |
| 객체 | `mcp`, `permission` | 키 단위로 합쳐진다. 같은 키는 높은 층이 이기고, 안쪽 객체도 같은 방식으로 합쳐진다 |
| 객체를 문자열로 | `permission.bash` 를 `"allow"` 로 | 합쳐지지 않고 **통째로 교체**된다 |

## 따라 하기

1. 병합 데모를 실행합니다. 임시 폴더만 쓰므로 안전합니다.

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

2. 직접 한 단계씩 확인해 봅니다. (실제 내 전역 설정도 함께 병합되어 보입니다. 읽기만 하므로 안전합니다.)

   PowerShell:
   ```powershell
   opencode debug config                                   # 프로젝트 + 내 전역
   $env:OPENCODE_CONFIG = "$PWD\team-defaults.json"
   opencode debug config                                   # + 팀 파일
   $env:OPENCODE_CONFIG_CONTENT = '{"username":"me-today"}'
   opencode debug config                                   # + 이번 실행에만 얹은 JSON
   Remove-Item Env:OPENCODE_CONFIG, Env:OPENCODE_CONFIG_CONTENT
   ```
   Linux bash:
   ```bash
   opencode debug config
   OPENCODE_CONFIG="$PWD/team-defaults.json" opencode debug config
   OPENCODE_CONFIG_CONTENT='{"username":"me-today"}' opencode debug config
   ```

3. 하위 폴더에서도 같은 결과인지 확인합니다: `mkdir src; cd src; opencode debug config` 를 실행하면 위쪽 폴더의 `opencode.json` 이 그대로 적용됩니다.

(이 예제는 모델을 쓰지 않습니다. 모델 선택은 평소 쓰는 설정 그대로이고, 설정 파일에는 `model` 키를 넣지 않았습니다.)

## 기대 결과

`python demo.py` 의 마지막 시나리오입니다. (opencode 1.19.5, Linux에서 실제 실행한 출력)

```
=== 5. + OPENCODE_CONFIG_CONTENT
    활성 레이어: global < OPENCODE_CONFIG < project < .opencode < CONFIG_CONTENT
    키                            결과 값                                         이긴 레이어
    ---------------------------  -------------------------------------------  -----------
    username                     content-user                                 CONFIG_CONTENT
    share                        manual                                       OPENCODE_CONFIG
    instructions[]               global-rules.md                              global
    instructions[]               shared-rules.md                              global
    instructions[]               team-rules.md                                OPENCODE_CONFIG
    instructions[]               project-rules.md                             project
    instructions[]               content-rules.md                             CONFIG_CONTENT
    mcp.layer-global             local python global.py (enabled=false)       global
    mcp.layer-team               local python team.py (enabled=false)         OPENCODE_CONFIG
    mcp.layer-project            local python project.py (enabled=false)      project
    mcp.layer-dotopencode        local python dotopencode.py (enabled=false)  .opencode
    mcp.layer-content            local python content.py (enabled=false)      CONFIG_CONTENT
    permission.bash.*            ask                                          global
    permission.bash.git status*  deny                                         CONFIG_CONTENT
    permission.bash.rm *         deny                                         project
    permission.edit              deny                                         .opencode

보너스: 프로젝트의 하위 폴더(src/deep)에서 실행해도 5번과 같은 결과인가? -> 예
```

시나리오마다 `username` 만 따로 보면 층이 하나씩 쌓일 때 이긴 값이 바뀝니다.

| 시나리오 | username | share |
|---|---|---|
| 1. 전역만 | `global-user` | `disabled` |
| 2. + `OPENCODE_CONFIG` | `team-user` | `manual` |
| 3. + 프로젝트 루트 | `project-user` | `manual` |
| 4. + `.opencode/` | `dotopencode-user` | `manual` |
| 5. + `OPENCODE_CONFIG_CONTENT` | `content-user` | `manual` |

`share` 는 프로젝트 쪽 파일들이 정하지 않았으므로 2번에서 정해진 값이 끝까지 남습니다.

## 동작 원리

1. `demo.py` 는 `global-config/opencode.json` 을 **임시** `XDG_CONFIG_HOME/opencode/` 로 복사합니다. opencode 는 `XDG_CONFIG_HOME` 아래를 "전역 설정 폴더"로 읽으므로, 내 실제 전역 설정은 읽히지도 바뀌지도 않습니다.
2. 시나리오 1·2는 프로젝트 설정이 없는 빈 임시 폴더에서 실행합니다. 3·4·5는 이 예제 파일을 임시 프로젝트로 복사해 실행합니다. (3번에서는 `.opencode/` 를 빼고 복사해서 층이 하나씩만 쌓이도록 했습니다.)
3. 시나리오마다 `opencode debug config` 가 병합 결과를 JSON 으로 출력합니다.
4. `demo.py` 는 각 층의 원본 파일을 직접 읽어서, 결과의 각 값이 **어느 층에서 왔는지** 표시합니다. 원본 파일에서 찾지 못하면 `?` 로 표시되므로, 표의 "이긴 레이어"는 추측이 아니라 실제 결과와 대조한 값입니다.
5. 프로젝트 설정은 작업 폴더에서 위쪽 폴더로 올라가며 찾습니다. 가까운 폴더의 `opencode.json` 이 더 높은 우선순위로 얹히며, 하위 폴더에서 실행해도 상위 폴더의 설정이 적용됩니다. git 저장소 안에서는 **저장소 루트까지만** 올라갑니다. (저장소 바깥 폴더에 둔 `opencode.json` 은 읽히지 않는 것을 확인했습니다.) git 저장소가 아닌 폴더에서는 위쪽 폴더의 `opencode.json` 도 읽힙니다.
6. `permission.bash` 안의 규칙은 **키가 처음 나온 순서**로 배열에 쌓입니다. 위 표에서 `*` 가 맨 앞에 있는 것은 전역 설정이 먼저 정의했기 때문입니다. 규칙은 "마지막으로 맞는 것이 이긴다"로 평가되므로 이 순서가 중요합니다. (C5 참고)

참고: 위 층 외에 `OPENCODE_CONFIG_DIR=폴더` 환경변수로 추가 설정 폴더(`opencode.json` 포함)를 지정할 수 있습니다. 이 폴더는 프로젝트 `.opencode/` 보다 위, `OPENCODE_CONFIG_CONTENT` 보다 아래에 쌓입니다.

## 직접 바꿔 보기

1. `.opencode/opencode.json` 의 `username` 줄을 지우고 `python demo.py` 를 다시 실행해 보세요. 4번에서 `username` 이 `project-user` 로 돌아갑니다. 이긴 레이어가 바뀌는 것을 표에서 확인하세요.
2. `opencode.json` 의 `instructions` 에 `team-rules.md` 를 추가해 보세요. 이미 팀 파일에 있는 항목이라 결과에는 **한 번만** 나옵니다.
3. `opencode.json` 의 `"permission"` 을 `{ "bash": "allow" }` 로 바꿔 보세요. 전역·팀 파일의 `bash` 규칙(`*`, `git status*`)이 합쳐지지 않고 `"allow"` 하나로 **교체**됩니다. 객체를 문자열로 바꾸는 순간 병합이 멈춘다는 점이 핵심입니다.

## 주의할 점 / 문제 해결

- **`.opencode/` 가 있으면 opencode 가 `@opencode-ai/plugin` 을 npm 에서 자동 설치하려 합니다.** (`package.json`, `node_modules`, 자체 `.gitignore` 생성) 인터넷이 막혀 있고 패키지 미러도 없으면 첫 실행이 약 70초 멈췄다가 계속됩니다. 이 예제의 `debug config` 는 설치를 일으키지 않았지만, `opencode`(TUI), `mcp list`, `debug skill` 등은 일으킬 수 있습니다.
- `OPENCODE_CONFIG` 로 지정해도 **전역 설정은 사라지지 않습니다.** 전역 위에 얹힐 뿐이며, 프로젝트 설정보다 낮은 우선순위입니다. 전역을 완전히 빼고 실험하려면 C4(`isolated.py`)를 쓰세요.
- git 저장소가 아닌 폴더(예: 압축을 푼 예제 폴더)에서 실행하면 **상위 폴더에 우연히 있는 `opencode.json`** 까지 병합됩니다. 예상 밖의 값이 보이면 `git init` 으로 경계를 만들거나 `OPENCODE_DISABLE_PROJECT_CONFIG=1` 을 써 보세요. (C4 참고)
- 설정 파일이 올바른 JSON(주석 허용, 끝 쉼표 허용)이 아니면 `Config file at ... is not valid JSON(C)` 오류가 나며 어느 줄이 문제인지 알려 줍니다.
- Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`demo.py` 안의 MCP 항목은 `enabled: false` 라서 실제로 실행되지 않습니다.)
- `opencode debug config` 는 개인 설정(전역 설정 포함)을 전부 출력합니다. 화면 공유나 로그 첨부 전에 내용을 확인하세요. 키 값 일부는 `***` 로 가려지지만 전부는 아닙니다. (C2 참고)
