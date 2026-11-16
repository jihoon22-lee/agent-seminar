---
name: secret-scan
description: 커밋·푸시 전에 코드와 설정 파일에 하드코딩된 비밀값(API 키, 비밀번호, 토큰, 개인 키, .env)이 섞였는지 검사한다. "비밀값 검사", "시크릿 스캔", "커밋 전에 키 새는지 확인", "API 키 하드코딩 찾아줘", "push 해도 되는지 봐줘" 같은 요청에 사용한다. Scan for leaked secrets before commit.
---

# 시크릿 스캔 스킬

정규식·엔트로피 규칙은 번들된 스크립트가 결정적으로 처리한다. 너는 결과를 보고 **진짜 비밀값인지 판단**하고, 옮길 방법을 제안한다.
스크립트는 비밀값을 마스킹해서 출력한다. **마스킹되지 않은 원문 값을 찾아서 답변에 적지 않는다.** (`cat .env`, 파일 전체 읽기 금지)

## 1. 커밋 전에 스크립트 실행

스크립트는 **스킬 디렉터리 기준** `scripts/scan_secrets.py` 이다.
스킬을 불러올 때 알려 주는 base directory(스킬 폴더 경로)를 앞에 붙이고, **검사할 프로젝트(git 저장소) 안에서** 실행한다.

```
python <스킬 폴더>/scripts/scan_secrets.py --changed
```

- 예: `python .opencode/skills/secret-scan/scripts/scan_secrets.py --changed`
- `--changed` 는 git 이 수정·스테이징·untracked 로 보고하는 파일만 검사한다. 저장소 전체는 인자 없이 실행하거나 경로를 준다: `... scan_secrets.py src config.py`
- `python` 명령이 없는 환경(Linux 등)에서는 `python3` 로 바꿔서 실행한다.
- 셸이 PowerShell(Windows)이든 bash(Linux)이든 같도록 `&&`, `export`, `$변수`, 파이프(`| head`) 없이 **명령 한 줄**만 실행한다. 경로는 `/` 로 써도 된다.
- 출력 한 줄 = 한 건: `파일:줄번호:규칙: 값을 마스킹한 줄`. 마지막 `#` 줄은 요약이다. `--format json` 도 지원한다.
- 종료 코드: **0 = 발견 없음, 1 = 발견됨**, 2 = 인자·경로·git 오류. 1 이면 커밋하지 말라고 알린다.

규칙 이름: `hardcoded-credential`(api_key/password/secret = "…"), `known-token-prefix`(잘 알려진 토큰 모양),
`url-credentials`(접속 URL 안에 박힌 사용자:비밀번호), `private-key-header`(개인 키 헤더 줄), `env-file`/`env-secret`(.env 파일),
`high-entropy-string`(길고 무작위로 보이는 문자열).

## 2. 결과 분류

각 건을 직접 확인해서 세 가지로 나눈다. 값을 알아야 하면 해당 **줄 번호 주변만** 읽되, 값은 답변에 옮겨 적지 않는다.

- **진짜 비밀값** — 키·비밀번호·토큰·개인 키. 이미 원격에 올라간 적이 있으면 "폐기·재발급이 우선"이라고 먼저 알린다.
- **오탐 가능성** — `high-entropy-string` 은 git SHA, 해시, 빌드 ID 일 수 있다. 근거(변수 이름, 용도)와 함께 "오탐으로 보임"이라고 쓴다.
- **파일 자체가 문제** — `.env` 는 내용과 상관없이 커밋 대상이 아니어야 한다.

## 3. 보고와 조치 제안

한국어로 아래 순서로 보고한다. **파일을 직접 고치지는 않는다**(사용자가 요청하면 그때 수정).

1. 결론 한 줄: 커밋해도 되는지 / 안 되는지
2. 표: `파일:줄 | 규칙 | 판단(진짜/오탐/파일 문제) | 조치`
3. 조치 제안 (해당하는 것만)
   - 코드 안의 값 → 환경 변수로 읽기 (`os.environ["API_KEY"]`, `process.env.API_KEY`)
   - `.env` → `.gitignore` 에 추가하고, 변수 이름만 적은 `.env.example` 을 커밋
   - 개인 키·인증서 → 저장소 밖(예: `~/.ssh`)이나 시크릿 매니저로 옮기고 경로만 설정으로 전달
   - 이미 커밋된 적이 있는 값 → 키 폐기·재발급이 먼저. 히스토리 정리는 그 다음
   - 오탐 → 해당 줄 끝에 `secret-scan: ignore` 주석
4. 조치 뒤에 같은 명령을 다시 실행해 종료 코드가 0 인지 확인하라고 안내
