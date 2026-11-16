---
name: release-notes
description: git 태그 이후의 커밋을 Conventional Commits 기준으로 분류해 한국어 릴리스 노트를 만든다. "릴리스 노트 써줘", "변경사항 정리", "v1.0.0 이후 뭐가 바뀌었어", "changelog 만들어줘" 같은 요청에 사용한다. Generate user-facing release notes from git history.
---

# 릴리스 노트 스킬

커밋 분류(feat/fix/perf/…, 호환성 깨짐 감지)는 번들된 스크립트가 결정적으로 처리한다.
너는 스크립트 결과를 **사용자가 읽는 한국어 문장**으로 다시 쓴다. `git log` 를 직접 파싱하지 않는다.

## 1. 스크립트 실행

스크립트는 **스킬 디렉터리 기준** `scripts/release_notes.py` 이다.
스킬을 불러올 때 알려 주는 base directory(스킬 폴더 경로)를 앞에 붙이고, **작업 중인 git 저장소 안에서** 실행한다.

```
python <스킬 폴더>/scripts/release_notes.py --from <이전 태그> --to HEAD
```

- 예: `python .opencode/skills/release-notes/scripts/release_notes.py --from v1.0.0 --to HEAD`
- `python` 명령이 없는 환경(Linux 등)에서는 `python3` 로 바꿔서 실행한다.
- 셸이 PowerShell(Windows)이든 bash(Linux)이든 같도록 `&&`, `export`, `$변수`, 파이프(`| head`) 없이 **명령 한 줄**만 실행한다. 경로는 `/` 로 써도 된다.
- `--from` 을 생략하면 가장 최근 태그부터 비교한다. 사용자가 범위를 말하지 않았다면 `git tag` 로 태그를 확인하고 묻거나, 가장 최근 태그를 쓴다.
- 구조화된 데이터가 더 편하면 `--format json` 을 붙인다.
- 종료 코드: 0 = 성공, 2 = git 저장소가 아님 / 없는 태그·ref.

## 2. 한국어로 다시 쓰기

먼저 `references/korean-style.md` (스킬 폴더 기준)를 읽고 문체 규칙과 섹션 제목 매핑을 따른다.

- 스크립트 출력의 구조(섹션 순서, "Breaking changes" 가 맨 위)는 유지한다.
- 커밋 메시지를 그대로 번역하지 말고 사용자 관점으로 풀어 쓴다.
- **Breaking changes 에는 반드시 대응 방법**(무엇을 무엇으로 바꿔야 하는지)을 적는다. 커밋 본문에 없으면 지어내지 말고 "대응 방법 확인 필요"라고 표시한다.
- "Other (not Conventional Commits)" 항목은 내용만으로 분류가 불확실하면 추측하지 말고 맨 아래에 "분류 확인 필요"로 남긴다.
- 스크립트가 보여 주지 않은 변경을 만들어 내지 않는다.

## 3. 출력

- 사용자가 파일 저장을 요청하면 그 경로에, 아니면 답변에 Markdown 으로 보여 준다.
- 제목은 `# <버전 또는 범위> 릴리스 노트`, 맨 끝에 한 줄로 "커밋 N개, 작성자 M명" 같은 요약을 붙인다.
