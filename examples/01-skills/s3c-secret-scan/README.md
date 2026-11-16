# S3c 시크릿 스캔 스킬 — 커밋 전에 한 번 돌리는 안전망

> 구성: 스킬(SKILL.md + scripts/) | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, git | 슬라이드: 스킬 — 스크립트를 품은 스킬

## 무엇을 보여 주나

"비밀값이 섞였는지 검사"는 규칙(정규식, 엔트로피)이 정해진 결정적 작업이라 스크립트로 만들고, 스킬이 **언제 돌리고 결과를 어떻게 판단·보고할지**를 정한다.
스크립트는 값을 마스킹해서 `파일:줄:규칙` 으로 출력하고 발견되면 종료 코드 1 을 낸다. 모델은 그 결과를 "진짜 비밀값 / 오탐 / 파일 자체가 문제"로 분류하고 환경 변수·시크릿 파일로 옮기는 방법을 제안한다.

이 예제의 가짜 비밀값은 **`prepare.py` 가 실행할 때 문자열을 이어 붙여 만든다.** 저장소에 커밋된 파일에는 토큰 모양 문자열이 하나도 없다
(GitHub push protection 이 막기 때문이고, `check.py` 가 이를 검사한다).

## 실무에서는

- `git commit` 직전에 "이번 변경에 키가 섞였나" 확인하는 습관 / pre-commit 훅이나 CI 단계에서 같은 스크립트를 종료 코드로 사용
- `.env` 를 `.gitignore` 에 넣는 것을 깜빡한 신규 프로젝트
- 이미 올라간 키는 스캔으로 찾더라도 **폐기·재발급이 먼저**라는 사고 대응 순서를 팀에 일관되게 안내

## 파일 구성

```
s3c-secret-scan/
├── README.md
├── fake_llm.py                                     # 가짜 모델 서버(m8 예제의 복사본): 실제 모델 없이 스킬 로드 → 스크립트 실행을 검증
├── check.py                                        # 자동 검증 (값이 출력에 새지 않는지 포함)
├── prepare.py                                      # sandbox/ 생성: 가짜 비밀값이 섞인 git 저장소
├── sandbox/                                        # prepare.py 가 만든다 (gitignored)
└── .opencode/skills/secret-scan/
    ├── SKILL.md                                    # 실행 시점, 결과 분류, 보고·조치 형식
    └── scripts/scan_secrets.py                     # 규칙 기반 스캐너 (표준 라이브러리만)
```

`sandbox/` 의 상태: 커밋됨 = `README.md`, `app.py`(환경 변수를 올바르게 사용), `.env.example` / 스테이징 = `config.py` / untracked = `.env`, `deploy/`, `notes.md`.
일부러 넣은 것: 코드 안 키·비밀번호, `.env`, 접속 URL 안의 비밀번호, 개인 키 헤더 줄, git SHA(오탐 후보), 플레이스홀더(`changeme`, 검사 제외), `secret-scan: ignore` 가 붙은 줄(검사 제외).

## 따라 하기

1. sandbox 를 만든다.

   PowerShell:
   ```powershell
   cd examples\01-skills\s3c-secret-scan
   python prepare.py
   cd sandbox
   ```
   Linux bash:
   ```bash
   cd examples/01-skills/s3c-secret-scan
   python3 prepare.py
   cd sandbox
   ```

2. (선택) 스크립트를 직접 실행한다. 값이 `sk-***(43 chars)` 처럼 가려져 나온다.

   PowerShell:
   ```powershell
   python .opencode\skills\secret-scan\scripts\scan_secrets.py --changed
   echo $LASTEXITCODE
   ```
   Linux bash:
   ```bash
   python3 .opencode/skills/secret-scan/scripts/scan_secrets.py --changed
   echo $?
   ```

3. `sandbox/` 안에서 opencode 를 실행한다. 평소 쓰는 모델로 실행하면 됩니다.
   (모델 설정이 없다면 `opencode run -m opencode/big-pickle --auto "<프롬프트>"` 처럼 무료 모델을 쓸 수 있다.)
   ```
   opencode
   ```
   입력할 프롬프트:
   ```
   secret-scan 스킬로 커밋하기 전에 비밀값이 섞였는지 검사하고, 어떻게 고치면 되는지 알려줘. 파일은 고치지 마.
   ```

4. `→ Skill "secret-scan"` 과 `$ python … scan_secrets.py --changed` 를 확인하고, 답변이 **마스킹되지 않은 값을 옮겨 적지 않는지** 본다.

## 기대 결과

스크립트를 직접 실행한 결과(`sandbox/` 에서 `--changed`)다. 값은 앞 3글자와 길이만 남고 가려진다. 마지막 `exit=1` 이 종료 코드다.

```
.env:1:env-file: .env file: keep it out of git (add to .gitignore) and share via a secret store
.env:1:known-token-prefix: API_KEY=sk-***(43 chars)
.env:2:url-credentials: DATABASE_URL=postgres://app:I3A***(14 chars)@localhost:5432/shop
.env:3:env-secret: SESSION_SECRET=1b6***(32 chars)
config.py:2:known-token-prefix: API_KEY = "sk-***(43 chars)"
config.py:3:hardcoded-credential: DB_PASSWORD = "I3A***(14 chars)"
config.py:6:high-entropy-string: BUILD_ID = "4a3***(40 chars)"
deploy/ci.yml:2:known-token-prefix: - run: git clone https://ci-bot:ghp***(40 chars)@example.invalid/shop.git
deploy/ci.yml:3:known-token-prefix: env: { AWS_ACCESS_KEY_ID: AKI***(20 chars) }
deploy/id_demo:1:private-key-header: -----BEGIN OPENSSH PRIVATE KEY-----
notes.md:4:known-token-prefix: - 임시: stripe = "sk_***(32 chars)"  # 테스트 후 폐기
# 11 finding(s) in 5 file(s); 7 file(s) scanned
exit=1
```

`SMTP_PASSWORD = "changeme"`(플레이스홀더)와 `# secret-scan: ignore` 가 붙은 줄은 목록에 없고, 커밋된 `app.py` 는 환경 변수를 쓰므로 깨끗하다.
`config.py:6 high-entropy-string` 은 40자리 16진수 `BUILD_ID` 로, git SHA 일 수 있는 **오탐 후보**다. 모델이 이를 구분해 보고하는 것이 이 예제의 관전 포인트다.

> 모델 확인 상태: 이 예제의 **실제 모델 실행은 확인하지 못했다**(무료 모델 한도 소진). 위 출력은 모델 없이 스크립트를 직접 실행한 결과이고, 모델은 이 결과를 받아 SKILL.md 의 보고 형식대로 한국어 답변을 쓰게 된다. `check.py` 는 가짜 모델로 "skill 도구 → bash 도구로 스크립트 실행" 흐름이 Linux 와 Windows 에서 동작함을 검증한다.


## 동작 원리

1. 스킬 로드 후 모델은 `Base directory for this skill` 경로 + `scripts/scan_secrets.py --changed` 를 `bash` 도구로 실행한다. 작업 디렉터리는 sandbox(검사할 저장소)다.
2. `--changed` 는 `git ls-files -m -o --exclude-standard` 와 `git diff --cached --name-only` 로 수정·스테이징·untracked 파일만 고른다. 인자 없이 실행하면 현재 폴더 전체를 본다.
3. 규칙: ① `api_key|secret|password|token = "값"` ② 잘 알려진 토큰 접두어 ③ `user:password@host` URL ④ 개인 키 헤더 줄 ⑤ `.env` 파일과 그 안의 `*_SECRET=` 류 ⑥ 길고 무작위로 보이는 문자열(섀넌 엔트로피). 플레이스홀더(`changeme`, `<your key>`, `${VAR}`)는 건너뛴다.
4. 값은 앞 3글자 + 길이만 남기고 가려서 출력한다(`sk-***(43 chars)`). 그래서 스크립트 결과가 모델의 컨텍스트와 대화 기록에 들어가도 값이 남지 않는다.
5. 종료 코드가 0/1/2 로 나뉘어 있어 사람(모델)뿐 아니라 pre-commit 훅·CI 도 같은 스크립트를 쓸 수 있다.
6. 모델의 몫은 분류와 조치 제안이다: BUILD_ID 의 40자리 16진수는 git SHA 일 수 있어 "오탐 가능"으로, `.env` 는 "파일 자체가 문제"로 구분한다.

## 직접 바꿔 보기

1. `config.py` 의 `API_KEY` 줄을 `os.environ["API_KEY"]` 로 바꾸고 스크립트를 다시 실행해 해당 건이 사라지는 것을 확인한다.
2. `BUILD_ID` 줄 끝에 `# secret-scan: ignore` 를 붙여 오탐을 끄고 다시 실행한다.
3. `scan_secrets.py` 에 자체 서비스의 토큰 형식 같은 규칙을 `RE_KNOWN` 에 한 줄 추가해 본다. (규칙은 코드에 있으므로 모델 프롬프트를 고칠 필요가 없다)

## 주의할 점 / 문제 해결

- **가짜 값을 파일에 직접 적지 말 것**: 토큰 모양 문자열을 커밋하면 GitHub push protection 이 푸시를 거절한다. 이 예제처럼 실행 시점에 조립하거나 `demo-token-123` 같은 누가 봐도 가짜인 값을 쓴다.
- **마스킹은 스크립트 출력에만 적용된다.** 모델이 `cat .env` 를 직접 실행하면 값이 대화에 들어간다. SKILL.md 가 이를 금지하지만, 더 강하게 막으려면 plugin 으로 `.env` 읽기를 차단하는 방법이 있다(plugin 예제 참고).
- **오탐/미탐은 있다.** 엔트로피 규칙은 해시·빌드 ID 를 잡고, 짧거나 평문인 비밀번호는 `password = "…"` 형태가 아니면 놓친다. 이 스캐너는 안전망 하나일 뿐 전문 도구(gitleaks 등)를 대체하지 않는다.
- **Windows 에서는 `python`, Linux 에서는 `python3`**: SKILL.md 는 `python` 으로 안내하고 "없으면 `python3`" 를 덧붙였다. Windows 에서 opencode 의 `bash` 도구는 Git Bash 가 아니라 **Windows PowerShell 5.1** 에서 명령을 실행한다. 그래서 SKILL.md 는 `&&`, `export`, `$변수`, `| head` 같은 bash 전용 문법 없이 `python <스킬 폴더>/scripts/… 인자` **한 줄**만 시킨다. 스킬 폴더 경로는 Windows 에서 `C:\...\.opencode\skills\<이름>` 처럼 역슬래시로 오지만, 파이썬에는 `/` 로 바꿔 넘겨도 동작한다(`check.py` 가 가짜 모델로 검증). 종료 코드 확인은 PowerShell 은 `$LASTEXITCODE`, bash 는 `$?`.
- `prepare.py` 는 `sandbox/` 를 지우고 다시 만든다. Windows 에서 `.git` 안의 읽기 전용 파일도 지우도록 처리돼 있다.
- 첫 실행 지연(`.opencode/` 의 `@opencode-ai/plugin` 자동 설치 시도)은 S3a 와 같다.
