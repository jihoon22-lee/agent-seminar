# S3b 릴리스 노트 스킬 — 분류는 스크립트, 문장은 모델

> 구성: 스킬(SKILL.md + scripts/ + references/) | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, git | 슬라이드: 스킬 — 스크립트를 품은 스킬

## 무엇을 보여 주나

커밋 메시지를 Conventional Commits 규칙(`feat`, `fix`, `perf`, `feat!` …)으로 분류하는 일은 정규식이면 충분하고 결과도 늘 같아야 한다.
그래서 분류는 스킬에 묶인 `release_notes.py` 가 하고, 모델은 그 Markdown 을 **사용자가 읽는 한국어 문장**으로 다시 쓴다.
`references/korean-style.md` 는 모델이 필요할 때만 읽는 보조 문서로, 문체 규칙을 SKILL.md 본문 밖에 두는 방법을 보여 준다.

## 실무에서는

- 배포 직전 "지난 릴리스 이후 뭐가 바뀌었나"를 사람이 `git log` 를 훑어 정리하던 일
- 개발자용 CHANGELOG 와 고객·팀원용 공지 문구를 같은 데이터에서 따로 만들어야 할 때
- 호환성이 깨지는 변경(`BREAKING CHANGE`)을 공지에서 빠뜨리지 않도록 맨 위에 모으고 싶을 때

## 파일 구성

```
s3b-release-notes/
├── README.md
├── fake_llm.py                                     # 가짜 모델 서버(m8 예제의 복사본): 실제 모델 없이 스킬 로드 → 스크립트 실행을 검증
├── check.py                                        # 자동 검증
├── prepare.py                                      # sandbox/ 생성: git 저장소 + v1.0.0 태그 + 뒤이은 커밋 12개 + .opencode 복사
├── sandbox/                                        # prepare.py 가 만든다 (gitignored, 자체 git init)
└── .opencode/skills/release-notes/
    ├── SKILL.md                                    # 스크립트 실행법과 한국어 재작성 규칙
    ├── scripts/release_notes.py                    # git log → Conventional Commits 분류 → Markdown/JSON
    └── references/korean-style.md                  # 사용자용 문체·섹션 제목 매핑 (필요할 때만 읽힘)
```

`sandbox/` 의 커밋에는 일부러 다음이 섞여 있다: scope 있는 `feat(cart)`, 호환성 깨짐 `feat(search)!` + `BREAKING CHANGE:` 본문, `perf`/`refactor`/`docs`/`test`/`ci`, 그리고 규칙을 안 지킨 `update stuff`.

## 따라 하기

1. sandbox 를 만든다. (git 이 필요하다)

   PowerShell:
   ```powershell
   cd examples\01-skills\s3b-release-notes
   python prepare.py
   cd sandbox
   ```
   Linux bash:
   ```bash
   cd examples/01-skills/s3b-release-notes
   python3 prepare.py
   cd sandbox
   ```

2. (선택) 스크립트를 직접 실행해 분류 결과를 본다.

   PowerShell:
   ```powershell
   python .opencode\skills\release-notes\scripts\release_notes.py --from v1.0.0 --to HEAD
   ```
   Linux bash:
   ```bash
   python3 .opencode/skills/release-notes/scripts/release_notes.py --from v1.0.0 --to HEAD
   ```

3. `sandbox/` 안에서 opencode 를 실행한다. 평소 쓰는 모델로 실행하면 됩니다.
   (모델 설정이 없다면 `opencode run -m opencode/big-pickle --auto "<프롬프트>"` 처럼 무료 모델을 쓸 수 있다.)
   ```
   opencode
   ```
   입력할 프롬프트:
   ```
   release-notes 스킬로 v1.0.0 이후 변경사항을 사용자용 한국어 릴리스 노트로 써줘
   ```
   > 스킬 이름 없이 "릴리스 노트 써줘" 만 말해도 로드되는 경우가 있지만, 모델에 따라 `git log` 를 직접 읽고 끝내기도 한다. 그럴 땐 스킬 이름을 명시한다.

4. 화면에서 `→ Skill "release-notes"`, `$ python … release_notes.py --from v1.0.0 --to HEAD`, 그리고 `references/korean-style.md` 를 읽는 동작을 확인한다.

## 기대 결과

스크립트를 직접 실행한 결과(모델이 받는 입력)다.

```
# Changes v1.0.0 -> HEAD

12 commits, 2026-10-12 .. 2026-10-26, 3 author(s).

## Breaking changes

- **search**: replace /search?q= with /v2/search (`77fe600`)
  - the old /search endpoint is removed; clients must call /v2/search.

## Features

- **cart**: add coupon code support (`df6e7b0`)
- **search**: replace /search?q= with /v2/search (`77fe600`)
- **auth**: support login with one-time email code (`3f2a39d`)

## Bug fixes

- **cart**: round totals to whole won (`02b0954`)
- prevent duplicate orders on double click (`a2ea187`)
- **auth**: refresh expired session token instead of logging out (`8228f9a`)

## Performance

- **api**: cache product list for 60 seconds (`a43b6c1`)

## Refactoring

- **db**: extract connection helper (`85d26d3`)

## Documentation

- describe the coupon API in README (`eebd57d`)

## Tests

- cover coupon edge cases (`d4185e3`)

## CI

- run tests on every pull request (`b04a584`)

## Other (not Conventional Commits)

- update stuff (`d145dd2`)
```

모델은 이를 `references/korean-style.md` 규칙대로 다시 쓴다. 기대하는 모양(예시):

```markdown
# v1.1 릴리스 노트

## 호환성이 깨지는 변경
- 검색 API 가 `/search?q=` 에서 `/v2/search` 로 바뀌었습니다. 기존 `/search` 는 제거되었으니 호출 주소를 바꿔 주세요.

## 새로운 기능
- 장바구니에서 쿠폰 코드로 할인받을 수 있습니다.
- 이메일로 받은 일회용 코드로 로그인할 수 있습니다.

## 버그 수정
- 장바구니 합계가 원 단위로 반올림됩니다.
- 세션이 만료돼도 로그아웃되지 않고 자동으로 갱신됩니다.
- 주문 버튼을 두 번 눌러도 주문이 중복 생성되지 않습니다.

## 성능 개선
- 상품 목록 응답이 빨라졌습니다.

## 분류 확인 필요
- "update stuff" 커밋은 내용을 알 수 없어 분류하지 못했습니다.
```

(위 한국어 예시는 규칙을 따랐을 때의 **예상 모양**이며 실제 모델 출력이 아니다.)

> 모델 확인 상태: 이 예제의 **실제 모델 실행은 확인하지 못했다**(무료 모델 한도 소진). 위 출력은 모델 없이 스크립트를 직접 실행한 결과이고, 모델은 이 결과를 받아 SKILL.md 의 보고 형식대로 한국어 답변을 쓰게 된다. `check.py` 는 가짜 모델로 "skill 도구 → bash 도구로 스크립트 실행" 흐름이 Linux 와 Windows 에서 동작함을 검증한다.


## 동작 원리

1. opencode 가 `sandbox/.opencode/skills/release-notes/SKILL.md` 를 발견하고 `description` 의 "릴리스 노트 써줘", "changelog 만들어줘" 같은 문구로 모델이 스킬을 고르게 한다.
   `sandbox/` 는 자체 `git init` 한 저장소이므로 `prepare.py` 가 `.opencode/` 를 그 안으로 복사해 둔다. (opencode 는 현재 프로젝트의 `.opencode/` 를 읽는다.)
2. 스킬이 로드되면 SKILL.md 뒤에 `Base directory for this skill: <절대 경로>` 가 붙는다. 모델은 이 경로 + `scripts/release_notes.py` 로 실행한다.
   **작업 디렉터리는 sandbox 그대로**이므로 스크립트의 `git log` 는 sandbox 저장소를 읽는다.
3. 스크립트는 `git log --no-merges v1.0.0..HEAD` 를 구분자 포맷으로 읽고, 첫 줄을 `type(scope)!: 설명` 규칙으로 파싱한다.
   `!` 또는 본문의 `BREAKING CHANGE:` 가 있으면 맨 위 "Breaking changes" 로 모은다(Features 에도 남는다). 규칙에 안 맞는 커밋은 "Other" 로 분리한다.
4. 모델은 Markdown 을 받아 `references/korean-style.md` 의 문체·제목 매핑대로 다시 쓴다. SKILL.md 가 "스크립트에 없는 변경을 만들어 내지 말 것", "분류가 불확실하면 확인 필요로 남길 것" 을 지시한다.

## 직접 바꿔 보기

1. `korean-style.md` 의 문체를 "~합니다" 체로 바꾸고 같은 요청을 다시 해 본다. 스크립트는 그대로인데 결과 문장만 바뀌는 것을 확인한다.
2. `release_notes.py` 의 `SECTIONS` 에서 `chore` 를 지워 보고 어떤 커밋이 "Other" 로 가는지 본다. (분류표가 코드에 있다는 것이 포인트)
3. `--from v1.0.0 --to HEAD~3` 처럼 끝 지점을 바꾸거나 `--format json` 을 붙여 실행해 본다.

## 주의할 점 / 문제 해결

- **git 이 PATH 에 있어야 한다.** 없으면 스크립트가 `error: git not found` 와 종료 코드 2 를 낸다.
- **Windows 에서는 `python`, Linux 에서는 `python3`**: SKILL.md 는 `python` 으로 안내하고 "없으면 `python3`" 를 덧붙였다. Windows 에서 opencode 의 `bash` 도구는 Git Bash 가 아니라 **Windows PowerShell 5.1** 에서 명령을 실행한다. 그래서 SKILL.md 는 `&&`, `export`, `$변수`, `| head` 같은 bash 전용 문법 없이 `python <스킬 폴더>/scripts/… 인자` **한 줄**만 시킨다. 스킬 폴더 경로는 Windows 에서 `C:\...\.opencode\skills\<이름>` 처럼 역슬래시로 오지만, 파이썬에는 `/` 로 바꿔 넘겨도 동작한다(`check.py` 가 가짜 모델로 검증).
- **`sandbox/` 에서 실행해야 한다.** 예제 폴더에서 실행하면 상위 저장소의 로그를 읽거나 `v1.0.0` 태그가 없다는 오류(종료 코드 2)가 난다.
- `prepare.py` 는 전역 git 설정을 읽지 않고(`GIT_CONFIG_GLOBAL` 비움) 작성자를 `dev-alpha/beta/gamma` 로 고정해 같은 이력을 만든다. 해시는 실행 환경에 따라 달라질 수 있다.
- 첫 실행 지연(`.opencode/` 의 `@opencode-ai/plugin` 자동 설치 시도)은 S3a 와 같다. 이 예제에도 플러그인이 없어 레지스트리에 닿지 않아도 눈에 띄는 멈춤은 없었다. 자세한 내용은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러) 참고.
