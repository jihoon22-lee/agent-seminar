# C4 안전하게 설정 실험하기 (격리 실행)

> 구성: isolated.py + 비교 데모 + 실험용 프로젝트 파일 | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: 설정 (테스트와 격리)

## 무엇을 보여 주나

설정, 스킬, 플러그인을 실험하다 보면 내 실제 `~/.config/opencode` 설정과 세션 기록을 건드리거나, 반대로 내 전역 설정 때문에 실험 결과가 오염되기 쉽습니다.
`isolated.py` 는 어떤 opencode 명령이든 **일회용 XDG 샌드박스** 안에서 실행합니다. 설정·로그인 정보·세션·캐시가 전부 임시 폴더로 가고, 끝나면 지워집니다.
또 `OPENCODE_DISABLE_PROJECT_CONFIG`, `OPENCODE_DISABLE_EXTERNAL_SKILLS`, `--pure`, `OPENCODE_CONFIG` 가 각각 **무엇을 막고 무엇은 못 막는지**를 비교표로 확인합니다.

## 실무에서는

- 새 `opencode.json` 이나 MCP 설정을 팀에 배포하기 전에, 내 전역 설정이 섞이지 않은 깨끗한 상태에서 동작하는지 확인합니다. ("내 PC에서만 되는" 문제를 줄입니다.)
- 설정 병합이나 권한 규칙처럼 헷갈리는 동작을 `debug config` 로 실험할 때, 실수로 실제 설정을 고칠 걱정 없이 마음껏 바꿔 봅니다.
- 자동화 테스트(CI)에서 opencode 를 호출할 때, 실행하는 사람의 세션·로그인·스킬이 결과에 영향을 주지 않게 합니다. 이 저장소의 모든 `check.py` 도 같은 방식으로 돌아갑니다.
- 플러그인이 문제를 일으키는 것 같을 때 `--pure` 로 "플러그인 없이도 재현되는지" 가려냅니다.

## 파일 구성

```
c4-isolated-testing/
  README.md
  isolated.py            어떤 opencode 명령이든 일회용 샌드박스에서 실행 (표준 라이브러리만)
  flags_demo.py          격리 스위치별로 무엇이 숨겨지는지 비교표를 출력
  check.py               자동 검증 (모델 호출 없음)
  opencode.json          실험용 프로젝트 설정 (username = c4-project-user)
  fake-global.json       --global-config 에 쓸 "전역 설정" 대역 (username = fake-global-user)
  test-config.json       OPENCODE_CONFIG 에 쓸 테스트 설정 (username = c4-test-user)
  .opencode/skills/c4-local-skill/SKILL.md   프로젝트 스킬 (스위치가 숨기는지 확인용)
  .opencode/plugins/c4-marker.js             C4_MARKER_FILE 에 한 줄을 쓰는 플러그인 (로드 여부 확인용)
```

## 따라 하기

1. **평소 경로와 격리 경로를 비교합니다.** `debug paths` 는 읽기만 하는 명령입니다.

   PowerShell:
   ```powershell
   cd examples\00-config\c4-isolated-testing
   opencode debug paths                 # 평소: 내 실제 경로
   python isolated.py debug paths       # 격리: 전부 임시 폴더
   ```
   Linux bash:
   ```bash
   cd examples/00-config/c4-isolated-testing
   opencode debug paths
   python3 isolated.py debug paths
   ```

2. **격리된 상태로 아무 opencode 명령이나** 실행합니다. 옵션은 opencode 인자보다 앞에 둡니다.

   ```
   python isolated.py debug config
   python isolated.py --global-config fake-global.json debug config
   python isolated.py --env OPENCODE_DISABLE_PROJECT_CONFIG=1 debug config
   python isolated.py --keep debug skill        # 끝난 뒤에도 임시 폴더를 남기고 경로를 알려 줌
   python isolated.py -- --pure debug config    # opencode 옵션으로 시작하는 인자는 앞에 -- 를 붙임
   ```
   `isolated.py` 는 인자 없이 실행하면 **격리된 TUI** 를 엽니다. 이때는 로그인 정보가 없으므로 모델을 직접 지정하세요. (예: `python isolated.py run -m opencode/big-pickle --auto "안녕"`) 평소 쓰는 모델의 로그인은 샌드박스에 없습니다.

3. **스위치 비교표**를 봅니다. (모델 호출 없음)

   ```
   python flags_demo.py
   ```

4. (선택) 테스트 설정만 남기는 "완전 통제" 조합을 직접 실행해 봅니다.

   PowerShell:
   ```powershell
   python isolated.py --env OPENCODE_DISABLE_PROJECT_CONFIG=1 --env "OPENCODE_CONFIG=$PWD\test-config.json" debug config
   ```
   Linux bash:
   ```bash
   python3 isolated.py --env OPENCODE_DISABLE_PROJECT_CONFIG=1 --env "OPENCODE_CONFIG=$PWD/test-config.json" debug config
   ```
   `username` 이 `c4-test-user` 로 나오면 프로젝트 설정도, 내 전역 설정도 섞이지 않은 것입니다.

## 기대 결과

1번의 격리 실행 (opencode 1.19.5, Linux, `<임시폴더>` 는 실행마다 달라지는 임시 경로):

```
[isolated] 샌드박스: <임시폴더>  (cwd: ...)
home       /home/<사용자>
data       <임시폴더>/data/opencode
bin        <임시폴더>/cache/opencode/bin
log        <임시폴더>/data/opencode/log
repos      <임시폴더>/data/opencode/repos
cache      <임시폴더>/cache/opencode
config     <임시폴더>/config/opencode
state      <임시폴더>/state/opencode
tmp        <임시폴더>/tmp/opencode
```

평소에는 `data` 가 `~/.local/share/opencode`, `config` 가 `~/.config/opencode`, `state` 가 `~/.local/state/opencode`, `cache` 가 `~/.cache/opencode` 입니다. (Windows 도 같은 XDG 환경변수를 존중하므로 같은 방식으로 격리됩니다.) 단 `home` 줄은 그대로입니다. 홈 폴더 자체는 바꾸지 않습니다. 그래서 `~/.claude/skills` 같은 외부 스킬은 별도 스위치로 숨깁니다.

3번의 비교표 (`flags_demo.py`, 같은 실험용 폴더에서 스위치를 하나씩 추가):

```
setting                             username          project-skill  external-skill  plugin
----------------------------------  ----------------  -------------  --------------  ----------
(none) sandbox only                 c4-project-user   visible        visible         loaded
OPENCODE_DISABLE_EXTERNAL_SKILLS=1  c4-project-user   visible        hidden          loaded
OPENCODE_DISABLE_PROJECT_CONFIG=1   fake-global-user  hidden         visible         not loaded
--pure                              c4-project-user   visible        visible         not loaded
OPENCODE_CONFIG=test-config.json    c4-project-user   visible        visible         loaded
DISABLE_PROJECT_CONFIG + CONFIG     c4-test-user      hidden         visible         not loaded
```

읽는 법: `username` 은 어느 설정이 이겼는지(`c4-project-user` = 이 폴더의 `opencode.json`, `fake-global-user` = 샌드박스의 전역 설정, `c4-test-user` = `test-config.json`), `external-skill` 은 가짜 홈의 `~/.claude/skills`, `~/.agents/skills` 가 보이는지입니다.

## 동작 원리

**isolated.py 가 하는 일**

1. `tempfile.mkdtemp()` 로 임시 폴더를 만들고, 그 아래에 `config/ data/ cache/ state/ tmp/` 를 둡니다.
2. 환경변수 `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_STATE_HOME`, `TMPDIR`/`TEMP`/`TMP` 를 그 폴더들로 바꿉니다. opencode 는 전역 설정(`opencode.json`), 로그인 정보(`auth.json`), 세션 DB, 로그, 캐시를 이 경로 아래에만 둡니다.
3. 샌드박스의 전역 설정은 `{"autoupdate": false}` 한 줄입니다. `--global-config 파일` 을 주면 그 파일을 복사해서 씁니다. (원본은 읽기만 합니다.)
4. `OPENCODE_DISABLE_EXTERNAL_SKILLS=1`, `OPENCODE_DISABLE_AUTOUPDATE=1` 을 설정하고, 상속받은 `OPENCODE_CONFIG`, `OPENCODE_CONFIG_CONTENT`, `OPENCODE_CONFIG_DIR` 는 지웁니다. (내 셸에 남아 있던 값이 실험에 새어 들어오지 않게)
5. opencode 를 실행하고 종료 코드를 그대로 돌려준 뒤 임시 폴더를 지웁니다. `--keep` 이면 지우지 않고 경로를 출력합니다.

**각 스위치의 실제 동작 (모두 이 예제에서 직접 확인)**

| 스위치 | 막는 것 | 막지 못하는 것 |
|---|---|---|
| `OPENCODE_DISABLE_PROJECT_CONFIG=1` | 프로젝트의 `opencode.json`, `.opencode/opencode.json`, `.opencode/skills/`, `.opencode/plugins/` 전부 | `OPENCODE_CONFIG`, `OPENCODE_CONFIG_CONTENT` (그대로 적용됨), 전역 설정, 홈의 외부 스킬 |
| `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` (`true` 도 됨. `0` 은 끄지 못함) | `~/.claude/skills`, `~/.agents/skills` | 프로젝트·전역 스킬, 내장 스킬(`customize-opencode`) |
| `--pure` (또는 `OPENCODE_PURE=1`) | 외부 **플러그인**: `.opencode/plugins/*.js` 와 설정의 `plugin` 항목에 적은 파일 | 설정 병합과 스킬은 그대로. `debug config` 에는 `plugin` 항목이 여전히 보이지만 로드되지 않음 |
| `OPENCODE_CONFIG=파일` | 아무것도 막지 못함. 전역 **위에** 얹히고 프로젝트 설정보다는 **아래** | 전역과 프로젝트 설정이 그대로 남음 → 단독으로는 격리 수단이 아님 |

그래서 테스트 격리의 권장 조합은 다음과 같습니다.

- 전역·세션·로그인까지 분리: `isolated.py` (XDG 샌드박스)
- 프로젝트 파일 영향까지 제거: `OPENCODE_DISABLE_PROJECT_CONFIG=1`
- 그 위에 시험할 설정만 얹기: `OPENCODE_CONFIG=test-config.json` (또는 `OPENCODE_CONFIG_CONTENT`)
- 플러그인이 의심되면: `--pure`

`OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1` 은 `~/.claude/skills` 만 숨기고 `~/.agents/skills` 는 남겼습니다. (Linux에서만 확인)

## 직접 바꿔 보기

1. `python isolated.py --global-config fake-global.json debug config` 의 결과와, `--global-config` 없이 실행한 결과를 비교해 보세요. `fake-global.json` 에 `"share": "disabled"` 를 추가하고 다시 보면 샌드박스의 전역 값으로 나타납니다.
2. `flags_demo.py` 의 `rows_spec` 에 `("--pure + PROJECT_CONFIG", ["--pure"], {"OPENCODE_DISABLE_PROJECT_CONFIG": "1"}, True)` 를 추가해 두 스위치를 함께 켰을 때를 확인해 보세요.
3. `.opencode/plugins/c4-marker.js` 를 열어 보고, 플러그인이 로드될 때 `C4_MARKER_FILE` 에 쓰는 한 줄이 어떤 스위치에서 사라지는지 `flags_demo.py` 와 맞춰 보세요.

## 주의할 점 / 문제 해결

- **모델 로그인이 샌드박스에 없습니다.** 평소 쓰는 모델(내 계정, API 키)은 `auth.json` 이나 전역 설정에 있으므로 격리하면 사라집니다. 모델이 필요하면 `-m opencode/big-pickle` 같은 무료 모델을 쓰거나, 필요한 설정을 `--global-config` 로 넘기세요. API 키를 파일에 적었다면 그 파일을 커밋하지 마세요.
- **`.opencode/` 폴더가 있으면 opencode 가 `@opencode-ai/plugin` 을 npm 에서 자동 설치하려 합니다.** (`package.json`, `node_modules` 생성) 인터넷도 미러도 없으면 첫 실행이 약 70초 멈춥니다. 샌드박스는 캐시도 매번 새로 만들므로 이 지연을 매번 겪을 수 있습니다. 설치된 파일은 `.gitignore` 대상입니다. 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다.
- `isolated.py` 는 HOME(USERPROFILE)을 바꾸지 않습니다. 홈 아래의 `~/.claude/skills`, `~/.agents/skills` 는 읽기만 하며 기본으로 숨깁니다. 다른 도구가 홈 아래에 쓰는 것은 막지 못합니다.
- 격리 실행은 `OPENCODE_DISABLE_PROJECT_CONFIG` 를 켜지 않는 한 **현재 폴더의 프로젝트 설정을 그대로 읽습니다.** 프로젝트 폴더에서 실행하면 그 폴더의 `opencode.json` 은 적용됩니다.
- Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`isolated.py` 는 샌드박스 `PATH` 에 `python` 심볼릭 링크를 넣어서, MCP 설정의 `"python"` 도 동작하게 합니다.)
- 실행 중 Ctrl+C 로 중단해도 임시 폴더는 지워집니다. `--keep` 으로 남긴 폴더만 직접 지우세요.
