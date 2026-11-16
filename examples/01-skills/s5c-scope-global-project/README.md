# S5c 스킬의 범위 — 전역, 프로젝트, 팀 공용 폴더, URL

> 구성: 프로젝트 1개 + 팀 공용 스킬 폴더 1개 + 데모 스크립트 | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, git(모노레포 시나리오만) | 슬라이드: 스킬 (범위와 배포)

## 무엇을 보여 주나

스킬이 어디에 있느냐에 따라 "누구에게 보이는가"가 달라집니다. 내 PC 전체(전역), 이 저장소(프로젝트), 팀이 같이 쓰는 폴더(`skills.paths`), 원격 서버(`skills.urls`) 네 곳을 임시 샌드박스에서 하나씩 켜 보고, `opencode debug skill` 이 돌려주는 **이름 → 위치 표**로 어느 스킬이 어디서 왔는지 확인합니다.
같은 이름이 두 곳에 있을 때 누가 이기는지, 상대 경로는 무엇을 기준으로 풀리는지, URL 스킬은 어디에 저장되는지처럼 직접 부딪혀 보지 않으면 모르는 규칙을 실제 실행 결과로 보여 줍니다.

## 실무에서는

- **팀 공용 스킬 저장소**: 코드 리뷰 형식, 릴리스 노트 형식 같은 스킬을 별도 git 저장소(`team-skills`)에 모아 두고, 각자 clone 한 뒤 프로젝트의 `opencode.json` 에서 `skills.paths` 로 가리킵니다. 스킬을 고치면 `git pull` 만으로 모두가 같은 버전을 씁니다.
- **프로젝트 전용 스킬**: 브랜치 규칙처럼 그 저장소에서만 의미가 있는 스킬은 `.opencode/skills/` 에 두고 코드와 함께 커밋합니다.
- **개인 스킬**: 내가 어디서나 쓰는 스킬(말투, 메모 습관)은 전역 폴더 `~/.config/opencode/skills/` 에 둡니다. 동료에게는 보이지 않습니다.
- **모노레포**: `packages/api/.opencode/skills/` 처럼 패키지마다 스킬을 두면, 그 패키지 안에서 실행할 때만 보입니다.
- **정적 호스팅으로 배포**: 인터넷이 막힌 팀 공용 서버에 `index.json` 과 스킬 파일만 올려 두고 `skills.urls` 로 가져오게 할 수도 있습니다 (제약이 많으니 아래 주의점을 꼭 읽으세요).

## 파일 구성

```
s5c-scope-global-project/
  README.md
  project/                                   이 예제의 "프로젝트" (opencode 를 여기서 실행)
    opencode.json                            skills.paths = ["../team-skills"]
    .opencode/skills/project-conventions/    프로젝트 스킬
  team-skills/                               "팀 공용 스킬 저장소" 대역 (실제로는 별도 git 저장소)
    backend/code-review-style/SKILL.md       하위 폴더 안에 있어도 찾음
    release-notes/SKILL.md
  demo.py                                    모든 시나리오를 임시 샌드박스에서 실행해 위치 표를 출력
  lab.py                                     임시 샌드박스를 만드는 공용 도우미
  check.py                                   자동 검증
```

`demo.py` 의 "전역 스킬 폴더"는 임시 폴더 안에 만든 **가짜**입니다. 내 진짜 `~/.config/opencode` 는 읽지도 쓰지도 않습니다.

> `.opencode/` 가 있는 폴더에서 처음 opencode 를 실행하면 `@opencode-ai/plugin` 이 npm 에서 `.opencode/` 안에 자동 설치됩니다(`package.json`, `node_modules/` 생성, git 제외). 레지스트리에 접근할 수 없으면 첫 실행이 약 70초 멈췄다가 계속됩니다.

## 따라 하기

Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요.

### 1. 전체 시나리오 보기 (모델 불필요, 약 40초)

PowerShell:

```powershell
cd examples\01-skills\s5c-scope-global-project
python demo.py
python demo.py --runs 20      # 같은 이름 충돌에서 승자를 20번 세어 봄
python demo.py --port 8851    # skills.urls 실험용 로컬 서버 포트 (기본 8851, 127.0.0.1 에만 열림)
```

Linux bash:

```bash
cd examples/01-skills/s5c-scope-global-project
python3 demo.py
python3 demo.py --runs 20
```

### 2. 예제 프로젝트에서 직접 확인

PowerShell:

```powershell
cd project
opencode debug skill      # 이름, description, location, content 가 JSON 으로 나옴
opencode                  # TUI 에서 /skills 를 입력하면 같은 목록이 선택창으로 나옴
```

Linux bash:

```bash
cd project
opencode debug skill
opencode
```

`debug skill` 결과에 `customize-opencode`(위치 `<built-in>`, opencode 에 내장)와 함께 `project-conventions`(프로젝트), `code-review-style`·`release-notes`(`team-skills`)가 보이면 성공입니다. TUI 에서는 평소 쓰는 모델로 `PR 리뷰 부탁해. 리뷰 스타일은 code-review-style 스킬을 따라줘` 처럼 이름을 직접 말해 보세요. 모델 설정이 없다면 `opencode -m opencode/big-pickle` 로 시작하세요.

### 3. 자동 검증

```bash
python3 ../../../tools/run_checks.py s5c            # 모델 없음
python3 ../../../tools/run_checks.py s5c --model    # 실제 모델 1회 추가
```

## 기대 결과

`python demo.py --runs 10` (Linux, opencode 1.19.5). 경로의 `<샌드박스>` 는 임시 폴더, `<작업폴더>` 는 데모가 복사해 만든 임시 작업 폴더입니다.

```
-- 1. 전역 스킬만 있고 프로젝트에는 스킬이 없음
   greeting  [전역]  <샌드박스>/config/opencode/skills/greeting/SKILL.md

-- 2. 프로젝트 .opencode/skills 만 (+ 위의 전역 greeting 도 같이 보임)
   greeting  [전역]  <샌드박스>/config/opencode/skills/greeting/SKILL.md
   project-conventions  [프로젝트]  <작업폴더>/ws-plain/project/.opencode/skills/project-conventions/SKILL.md

-- 3. 같은 이름 greeting 이 전역과 프로젝트에 모두 있음 (10번 반복해서 어느 쪽 위치가 이겼는지 셈)
   프로젝트: 10/10
   opencode 경고 로그: "duplicate skill name" name=greeting existing=<샌드박스>/config/…/greeting/SKILL.md duplicate=<작업폴더>/…/.opencode/skills/greeting/SKILL.md

-- 4-a. skills.paths = ["../team-skills"], project/ 에서 실행
   code-review-style  [skills.paths]  <작업폴더>/ws-paths/team-skills/backend/code-review-style/SKILL.md
   project-conventions  [프로젝트]  <작업폴더>/ws-paths/project/.opencode/skills/project-conventions/SKILL.md
   release-notes  [skills.paths]  <작업폴더>/ws-paths/team-skills/release-notes/SKILL.md

-- 4-b. 같은 프로젝트의 하위 폴더 project/sub/deeper 에서 실행 (상대 경로가 실행 폴더 기준이라 공용 스킬이 사라짐)
   project-conventions  [프로젝트]  <작업폴더>/ws-paths/project/.opencode/skills/project-conventions/SKILL.md
   opencode 경고 로그: "skill path not found" path=<작업폴더>/ws-paths/project/sub/team-skills

-- 4-c. 절대 경로로 쓰면 어디서 실행해도 찾음  → 4-a 와 같은 3개
-- 4-d. "~/team-skills" (HOME 을 임시 폴더로 바꿔서 실행): ['code-review-style', 'project-conventions', 'release-notes']

-- 5. release-notes 가 프로젝트 .opencode/skills 와 team-skills 양쪽에 있음 (10번 반복)
   skills.paths: 8/10
   프로젝트: 2/10

-- 6-a. skills.urls = ["http://127.0.0.1:8851/skills/"] (index.json + 스킬 파일을 내려받음)
   remote-glossary  [url]  <샌드박스>/cache/opencode/skills/remote-glossary/SKILL.md
      description: 원격 서버에서 내려받는 스킬 (v1)
-- 6-b. 서버 내용을 v2 로 바꿨지만 index.json 에 version 이 없음 -> 캐시가 그대로 쓰임
      description: 원격 서버에서 내려받는 스킬 (v1)
-- 6-c. index.json 에 "version": "2" 를 넣음 -> 다시 내려받음
      description: 원격 서버에서 내려받는 스킬 (v2)
   캐시 폴더 <샌드박스>/cache/opencode/skills/remote-glossary 안: ['.opencode-version', 'SKILL.md', 'examples.md']
-- 6-d. 서버를 끄고 다시 실행 -> 캐시가 있는데도 URL 스킬이 사라짐
   (스킬 없음 - 내장 customize-opencode 는 생략)

-- 7. 모노레포 - pkg/a/src 에서 실행
   pkg-a  [프로젝트]  <작업폴더>/mono/repo/pkg/a/.opencode/skills/pkg-a/SKILL.md
   repo-root  [프로젝트]  <작업폴더>/mono/repo/.opencode/skill/repo-root/SKILL.md
   (repo 루트와 pkg 에서 실행하면 repo-root 만 보임)
```

같은 이름 충돌의 승자 비율은 실행할 때마다 조금씩 다릅니다. 같은 컴퓨터에서 여러 번 돌린 결과는 "전역 vs 프로젝트"에서 프로젝트 승 51/53(첫 시도), 4/6, 10/10, 24/25 등이었고, "프로젝트 vs `skills.paths`"에서는 `skills.paths` 승 25/25, 8/10 이었습니다. 아래 "동작 원리"를 읽어 보세요.

## 동작 원리

**스캔 순서와 합치기.** opencode 는 시작할 때 다음 곳의 `SKILL.md` 를 모아 **이름이 같은 것끼리는 하나로 합칩니다**(교체가 아니라 이름 단위 병합).

| 순서 | 위치 | 비고 |
|---|---|---|
| 1 | `~/.config/opencode/skills/` (또는 `skill/`) | 전역. 이 예제는 `XDG_CONFIG_HOME` 을 임시 폴더로 바꿔 대신 사용 |
| 2 | 실행 폴더에서 git 루트까지 올라가며 만나는 모든 `.opencode/skills/` (또는 `skill/`) | 모노레포의 패키지 층 + 루트 층이 합쳐짐. git 루트 위쪽은 안 봄 |
| 3 | `skills.paths` 의 각 폴더 | `**/SKILL.md` 를 재귀 탐색 (깊은 하위 폴더도 가능) |
| 4 | `skills.urls` 가 내려받은 캐시 폴더 | 아래 참고 |

(`~/.claude/skills`, `~/.agents/skills` 도 외부 스킬로 읽지만 이 예제는 `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` 로 꺼 둡니다.)

**같은 이름이면 "나중에 등록된 쪽"이 대체로 이기지만 보장되지는 않습니다.** 위 순서에서 뒤쪽이 앞쪽을 덮어쓰도록 만들어져 있어 보통은 프로젝트 > 전역, `skills.paths` > 프로젝트입니다. 그런데 파일을 읽는 작업이 동시에 돌기 때문에, 먼저 끝난 쪽이 아니라 나중에 끝난 쪽이 이기는 경쟁 상태가 있어 가끔 결과가 뒤집힙니다(위 측정). 어느 쪽이 이겼든 `duplicate skill name` 경고가 로그에 남고(`opencode debug skill --print-logs` 로 볼 수 있음) 모델에게는 하나만 보입니다. **→ 같은 이름으로 덮어쓰기를 설계하지 말고, 이름을 고유하게 지으세요.**

**`skills.paths` 의 상대 경로는 "opencode 를 실행한 폴더" 기준입니다.** `opencode.json` 이 있는 폴더가 아닙니다. `project/` 에서 실행하면 `../team-skills` 가 맞지만 `project/sub/deeper` 에서 실행하면 `project/sub/team-skills` 를 찾다가 `skill path not found` 경고만 남기고 넘어갑니다(오류로 멈추지 않음). 절대 경로나 `~/` 로 쓰면 어디서 실행해도 됩니다. 존재하지 않는 경로는 조용히 건너뜁니다.

**팀 공용 저장소로 배포하기.**

1. 팀 스킬만 담은 저장소를 만듭니다. 스킬마다 `<이름>/SKILL.md` 한 폴더, 분류용 하위 폴더는 자유입니다.
2. 각자 `git clone <저장소 주소> ~/team-skills` 합니다.
3. 프로젝트 `opencode.json` 에 `"skills": { "paths": ["~/team-skills"] }` 를 커밋합니다. clone 위치가 사람마다 같다면 이 한 줄이면 됩니다. 프로젝트 옆에 두고 싶다면 `../team-skills` 도 되지만 위의 "실행 폴더 기준" 함정이 있습니다.
4. 스킬이 바뀌면 `git pull` 하고 **opencode 를 다시 시작**합니다 (스킬은 시작할 때 한 번 읽습니다).

**`skills.urls` (1.19.5에서 존재하고 동작함).** 로컬 `http.server` 방식 서버로 확인한 형식입니다.

```
http://127.0.0.1:8851/skills/index.json                  {"skills":[{"name":"remote-glossary","files":["SKILL.md","examples.md"],"version":"2"}]}
http://127.0.0.1:8851/skills/remote-glossary/SKILL.md    files 에 적은 파일마다 <URL>/<name>/<파일> 을 GET
```

- `"skills": { "urls": ["http://127.0.0.1:8851/skills/"] }` 처럼 `index.json` 이 있는 디렉터리 URL 을 적습니다. 항목마다 `files` 에 `SKILL.md` 가 없으면 `skill entry missing SKILL.md` 경고와 함께 무시됩니다.
- 내려받은 파일은 `<XDG_CACHE_HOME>/opencode/skills/<name>/` (Linux 기본 `~/.cache/opencode/skills/<name>/`)에 저장되고, 스킬의 location 도 그 캐시 경로입니다.
- **`version` 이 없으면 한 번 받은 뒤 서버 내용을 바꿔도 다시 받지 않습니다.** `version` 문자열을 바꿔야 다시 내려받습니다(`.opencode-version` 파일에 기록).
- **시작할 때마다 `index.json` 을 가져오려고 하며, 실패하면 캐시가 있어도 그 URL 의 스킬은 통째로 사라집니다.** 서버가 꺼져 있거나 오프라인이면 URL 스킬을 못 씁니다. 실패는 로그(`failed to fetch index`)에만 남습니다.
- 이 예제는 https 서버나 인증이 필요한 서버는 시험하지 않았습니다. 이 저장소의 예제는 인터넷에 나가지 않도록 `127.0.0.1` 로만 확인했습니다.

## 직접 바꿔 보기

1. `team-skills/release-notes/SKILL.md` 의 `name` 을 `release-notes-v2` 로 바꾸고 폴더 이름은 그대로 두세요. `opencode debug skill` 에 어떤 이름으로 나오는지 보세요. (1.19.5 는 폴더 이름이 아니라 frontmatter 의 `name` 으로 등록합니다. 내장 skill 문서의 "폴더 이름과 일치해야 한다"는 관례일 뿐 강제되지 않았습니다.)
2. `project/opencode.json` 의 `../team-skills` 를 이 폴더의 절대 경로로 바꿔 `project/sub/` 를 만들고 거기서 `opencode debug skill` 을 실행해 보세요.
3. `python demo.py --runs 30` 으로 같은 이름 충돌의 승자 비율이 어떻게 나오는지 보세요. 다른 프로그램을 같이 돌리면 비율이 달라집니다.

## 주의할 점 / 문제 해결

- **같은 이름 덮어쓰기에 기대지 마세요.** 위에서 본 것처럼 가끔 뒤집힙니다. 팀 스킬과 개인 스킬의 이름이 겹치지 않게 접두사(`team-`, `my-`)를 쓰세요.
- **상대 경로 `skills.paths` 는 하위 폴더에서 깨집니다.** 프로젝트 루트에서만 실행한다고 가정할 수 없다면 `~/` 나 절대 경로를 쓰세요.
- **URL 스킬은 서버가 항상 살아 있어야 합니다.** 오프라인 사용이 필요한 스킬은 `skills.paths` + git 저장소 방식이 안전합니다.
- **스킬은 시작할 때만 읽습니다.** 스킬 파일을 고치거나 `git pull` 했다면 opencode 를 다시 시작하세요.
- **`debug skill` 은 모델 목록이 아닙니다.** `permission.skill` 로 deny 한 스킬도 `debug skill` 에는 나옵니다. 모델이 실제로 받는 목록은 S5b 의 `show_prompt.py` 로 보세요.
- **전역 스킬 폴더 위치.** Linux 에서는 `$XDG_CONFIG_HOME/opencode/skills`(기본 `~/.config/opencode/skills`)임을 확인했습니다. Windows 에서도 `XDG_CONFIG_HOME` 을 지정한 샌드박스 안의 `opencode\skills` 는 같은 방식으로 동작했지만, `XDG_CONFIG_HOME` 이 없을 때의 Windows 기본 위치는 확인하지 않았습니다.
- **홈 폴더의 `~/.opencode/skills`** 는 시험하지 않았습니다(opencode 가 `~/.opencode/opencode.json` 설정은 읽는 것을 로그에서 봤습니다).
- **Windows.** 로그에 찍히는 Windows 경로는 역슬래시가 두 겹(`\\`)으로 나올 수 있습니다. 위치 비교는 슬래시로 정규화해서 하세요(check.py 가 그렇게 합니다).
