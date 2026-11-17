# S1d 스크립트 없이 기존 CLI만 쓰는 스킬

> 구성: SKILL.md 한 장(스크립트 없음) + 실습용 git 저장소 | 난이도: ★☆☆ | 필요: opencode 1.19.5, Python 3.10+, git | 슬라이드: 스킬 — 스크립트가 필요 없는 경우

## 무엇을 보여 주나

지금까지의 스킬 예제 가운데 스크립트를 품은 것은 모두 Python 이었습니다. 하지만 **스킬에 스크립트가 꼭 필요한 것은 아닙니다.** 이 예제의 `branch-cleanup` 은 `git` 이 이미 출력해 주는 짧은 결과를 그대로 읽고, 사람이 직접 하던 **절차**(무엇을 지우고 무엇을 남기는가)만 SKILL.md 에 적어 둡니다.

- `main` 에 병합된 로컬 브랜치만 지운다 (`git branch --merged main`)
- `main` 과 지금 브랜치는 절대 지우지 않는다
- 삭제는 `git branch -d` 로만 한다. 강제 삭제 옵션은 쓰지 않는다
- 무엇을 남겼고 왜 남겼는지 표로 보고한다

명령은 한 줄에 하나씩, `&&`·파이프·`$(...)`·`xargs` 없이 적습니다. 그래서 같은 SKILL.md 가 bash 와 Windows PowerShell 5.1 에서 똑같이 동작하도록 만들어져 있습니다.

## 실무에서는

- 머지가 끝난 브랜치가 쌓여서 `git branch` 가 한 화면을 넘을 때 "병합된 브랜치 정리해줘" 한마디로 정리합니다. 어떤 것을 남겼는지 이유까지 받습니다.
- 팀이 "지우기 전에 이 순서로 확인한다"는 절차를 갖고 있다면, 문서로 두는 대신 스킬로 두면 사람마다 다르게 하던 순서가 같아집니다.
- Python 이 없는 PC(Windows 일반 PC 등)에서도 `git` 만 있으면 쓸 수 있습니다. 스크립트를 배포하지 않아도 됩니다.

## 파일 구성

```
s1d-cli-only/
├── README.md
├── check.py                               자동 검증
├── fake_llm.py                            가짜 LLM 서버 (check.py 가 모델 없이 스킬 사용을 재현)
├── prepare.py                             실습용 git 저장소 sandbox/ 생성
└── .opencode/skills/branch-cleanup/
    └── SKILL.md                           절차와 규칙 (이 폴더에 스크립트는 없음)
```

`prepare.py` 가 만드는 `sandbox/`(git 에 올라가지 않음)의 브랜치:

| 브랜치 | 상태 | 기대하는 처리 |
|---|---|---|
| `main` | 기본 브랜치 | 보존 |
| `feature/login` | main 에 병합됨(병합 커밋) | 삭제 |
| `fix/typo` | main 에 병합됨(fast-forward) | 삭제 |
| `chore/deps` | main 에 병합됨(fast-forward) | 삭제 |
| `wip/search` | 커밋이 main 에 없음 | 보존 (병합 안 됨) |
| `feature/current` | main 과 같은 지점이라 병합된 상태지만 **지금 체크아웃 중** | 보존 (현재 브랜치) |

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 아래 `opencode run` 에 `-m opencode/big-pickle` 을 붙여 보세요.

1. 실습용 저장소를 만듭니다. (다시 실행해도 안전합니다. sandbox 를 지우고 새로 만듭니다.)

   PowerShell:
   ```powershell
   cd examples\01-skills\s1d-cli-only
   python prepare.py
   cd sandbox
   git branch
   ```
   Linux bash (`python` 명령이 없으면 `python3` 로 바꾸세요):
   ```bash
   cd examples/01-skills/s1d-cli-only
   python3 prepare.py
   cd sandbox
   git branch
   ```
   브랜치 6개가 보여야 합니다.

2. 스킬이 보이는지 확인합니다.

   ```
   opencode debug skill
   ```
   목록에 `branch-cleanup` 이 있고 `location` 이 `sandbox/.opencode/skills/branch-cleanup/SKILL.md` 를 가리키면 됩니다.

3. 요청합니다.

   ```
   opencode run "병합된 브랜치 정리해줘"
   ```
   또는 `opencode` 를 열고 같은 문장을 입력합니다.

4. 결과를 확인합니다.

   ```
   git branch
   ```
   `main`, `feature/current`, `wip/search` 세 개가 남아야 합니다. 다시 해 보려면 `python prepare.py` 를 다시 실행하세요.

## 기대 결과

`python check.py` 가 가짜 모델로 확인한 결과입니다. (opencode 1.19.5, Linux. 가짜 모델이 스킬을 불러 SKILL.md 의 명령을 정해진 순서로 실행하도록 했으므로 **모델이 규칙을 지키는지**가 아니라 **SKILL.md 에 적힌 명령이 실제 저장소에서 의도대로 동작하는지**를 보여 줍니다.)

```
(각 출력의 줄바꿈을 공백으로 이어 적음)
실행 전  git branch:                    chore/deps  * feature/current  feature/login  fix/typo  main  wip/search
git branch --merged main:               chore/deps  * feature/current  feature/login  fix/typo  main
git branch --no-merged main:            wip/search
git branch -d wip/search:               error: the branch 'wip/search' is not fully merged
실행 후  git branch:                    * feature/current  main  wip/search
```

- `--merged main` 에는 병합된 3개뿐 아니라 `main` 과 현재 브랜치(`*`)도 나옵니다. 그래서 SKILL.md 규칙 2가 필요합니다.
- 병합되지 않은 `wip/search` 는 `git branch -d` 가 스스로 거절합니다. 강제 삭제 옵션이 필요 없다는 뜻입니다. (git 은 거절하면서 강제 삭제 명령을 안내하는 힌트를 함께 출력합니다. SKILL.md 규칙 3은 그 힌트를 따르지 않도록 막습니다.)
- 모델이 받는 시스템 프롬프트에는 스킬의 이름과 description 만 있고 본문은 없습니다. 스킬을 불러야 본문이 도구 결과로 들어옵니다. (S1a 와 같음)

실제 모델로 돌린 출력은 이 문서를 쓸 때 확인하지 못했습니다(`python check.py --model` 이 소프트 검사로 한 번 시도합니다).

## 동작 원리

1. SKILL.md 의 명령 블록은 `git branch --show-current` → `git branch --merged main` → `git branch --no-merged main` → (지울 브랜치마다) `git branch -d <이름>` → `git branch` 입니다. 모델은 목록 출력을 읽고 규칙에 따라 `<이름>` 을 채웁니다. "무엇을 지울까"의 판단은 출력 몇 줄을 읽는 일이라 모델이 하고, 삭제는 `git` 이 합니다.
2. **한 줄에 한 명령** 규칙의 이유: `&&` 는 PowerShell 5.1 에서 지원되지 않고, `$(...)`·`xargs`·파이프는 두 셸에서 문법과 인코딩이 달라집니다. 명령마다 결과를 따로 보고 다음 명령을 정하면 이런 문법이 필요 없습니다. `check.py` 가 명령 블록에 `&&`, `||`, 파이프, `;`, `$`, 백틱, `xargs`, 리다이렉트가 없음을 검사합니다.
3. 안전장치는 SKILL.md 의 문장과 `git` 자체의 보호가 겹쳐 있습니다. 문장: main·현재 브랜치를 지우지 않음, 강제 삭제 옵션을 쓰지 않음. `git`: 현재 브랜치는 삭제를 거절하고, 병합 안 된 브랜치는 `-d` 가 거절합니다.
4. **SKILL.md 에는 강제 삭제 옵션(d 의 대문자)을 글자로 적지 않았습니다.** 모델이 규칙 문장을 읽다가 그 옵션을 따라 쓸 가능성을 줄이려는 것이고, `check.py` 가 이 문자열이 파일 어디에도 없음을 확인합니다. 모델이 git 의 힌트를 보고 스스로 쓰는 것까지 막지는 못합니다. 막으려면 [C5](../../00-config/c5-permissions/README.md) 의 `bash` 권한으로 `git branch -D*` 를 deny 하세요.

### 스크립트가 필요 없는 때와 필요한 때

| | 스크립트 없이 CLI 만 (이 예제) | 스크립트를 넣는 스킬 ([S3a](../s3a-log-analysis/README.md)) |
|---|---|---|
| 도구의 출력 | 이미 짧고 읽기 쉽다 (브랜치 몇 줄) | 길거나 지저분하다 (수천 줄 로그) |
| 스킬의 가치 | **절차와 규칙** (무엇을 지우고 무엇을 남기나) | 결정적인 계산·가공 (집계, 파싱, 변환) |
| 모델이 맡는 일 | 출력을 읽고 규칙대로 고름 | 스크립트가 줄인 요약을 해석 |
| 실행 환경 | `git` 만 있으면 됨 | Python 등 런타임이 필요 |
| 스크립트로 옮길 신호 | 같은 명령 조합이 길어지거나, 출력 가공이 필요해지거나, 매번 같은 결과를 보장해야 할 때 | |

한 줄로: CLI 가 이미 **작고 정확한 출력**을 주고 가치가 **절차**에 있으면 SKILL.md 만으로 충분합니다. 출력이 크거나 가공이 필요하면 스크립트를 붙입니다.

## 직접 바꿔 보기

- `sandbox` 에서 `git checkout main` 으로 현재 브랜치를 바꾼 뒤 다시 요청해 보세요. 이제 `feature/current` 도 병합된 브랜치라 지워지는지 보세요.
- `sandbox/.opencode/skills/branch-cleanup/SKILL.md` 사본의 규칙 3을 지우고 같은 요청을 해 보세요. 병합 안 된 `wip/search` 는 `git branch -d` 가 거절하므로 여전히 남는지 확인합니다. (예제 폴더의 원본을 고친 것은 `prepare.py` 를 다시 실행해야 sandbox 에 복사됩니다.)
- 보고 형식에 "마지막 커밋 날짜" 열을 추가하고 `git log -1 --format=%cd <이름>` 한 줄을 절차에 넣어 보세요. 명령은 여전히 한 줄에 하나입니다.

## 주의할 점

- **Windows(PowerShell 5.1)에서도 같은 검사를 통과했습니다.** 가짜 모델이 SKILL.md 의 명령 줄을 그대로 실행했고, 지워진 브랜치와 남은 브랜치가 Linux 와 같았습니다. `check.py` 의 정적 검사는 두 셸에서 의미가 달라지는 문법이 명령에 없다는 것을 추가로 확인합니다. 실제 모델이 규칙을 지키는지는 확인하지 못했습니다(미검증).
- `sandbox/` 에서 실행하세요. 세미나 저장소 폴더에서 실행하면 이 저장소의 실제 브랜치가 대상이 됩니다. 기본 `-d` 가 안전하더라도 의도치 않은 저장소에서 실행하지 않도록 하세요.
- 스킬은 원격 브랜치를 건드리지 않습니다. 원격까지 정리하려면 명령과 규칙을 직접 추가해야 합니다.
- 기본 브랜치가 `main` 이 아닌 저장소에서는 스킬이 멈추고 알립니다(규칙 5). 이름을 바꾸려면 SKILL.md 의 `main` 을 모두 바꾸세요.
- `.opencode/` 가 있는 폴더에서는 opencode 가 `@opencode-ai/plugin` 을 설치하려고 시도하고 `.opencode/` 안에 `package.json`, `node_modules/` 등이 생길 수 있습니다(모두 git 에서 제외). 자세한 내용은 [S1a README](../s1a-commit-message/README.md#주의할-점--문제-해결) 를 보세요.
- Linux 에서 `python` 명령이 없으면 `python3` 로 바꾸세요. (`check.py` 는 어느 쪽이든 동작합니다.)
