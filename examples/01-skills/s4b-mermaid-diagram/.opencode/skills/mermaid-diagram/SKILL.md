---
name: mermaid-diagram
description: 파이썬 프로젝트의 모듈 import 구조를 읽어 Mermaid 다이어그램과 디렉터리 트리를 만들고 아키텍처를 설명한다. "아키텍처 다이어그램", "모듈 구조 그려줘", "의존성 그래프", "순환 import 찾아줘", "구조 설명해줘" 같은 요청에 사용한다. Draw a Mermaid import graph for a Python project and detect import cycles.
---

# Mermaid 다이어그램 스킬

소스를 `ast` 로 읽어 import 관계를 뽑고 Mermaid 코드를 만드는 일은 번들된 스크립트가 처리한다(코드를 실행하지 않는다).
너는 결과를 보고 **구조를 설명하고 순환 import 를 짚는다.** Mermaid 코드를 손으로 그리지 않는다.

## 1. 스크립트 실행

스크립트는 **스킬 디렉터리 기준** `scripts/scan_structure.py` 이다.
스킬을 불러올 때 알려 주는 base directory(스킬 폴더 경로)를 앞에 붙이고, **프로젝트 루트에서** 실행한다.

```
python <스킬 폴더>/scripts/scan_structure.py <분석할 폴더> --out out/architecture.md
```

- 예: `python .opencode/skills/mermaid-diagram/scripts/scan_structure.py sample-app --out out/architecture.md`
- `python` 명령이 없는 환경(Linux 등)에서는 `python3` 로 바꿔서 실행한다.
- 셸이 PowerShell(Windows)이든 bash(Linux)이든 같도록 `&&`, `export`, `$변수`, 파이프(`| head`) 없이 **명령 한 줄**만 실행한다. 경로는 `/` 로 써도 된다.
- 분석할 폴더를 사용자가 말하지 않았다면 소스가 있는 폴더(예: `src`, `app`)를 물어보거나, 프로젝트 안의 파이썬 패키지 폴더를 찾아 쓴다.
- 종료 코드: 0 = 성공, 2 = 폴더 없음 / `.py` 없음 / 문법 오류로 파싱 불가.
- stdout 은 JSON 요약이다: `modules`, `edges`(`lazy: true` 는 함수 안 import), `cycles`(순환 경로), `most_imported`, `entry_points`.
- `--out` 파일은 Markdown 이다: Mermaid 그래프, 디렉터리 트리, 순환 목록, 모듈별 import 수 표.

## 2. 설명

JSON 요약과 생성된 파일에 있는 사실만 근거로 한국어로 설명한다.

1. **구조 요약** — 진입점(`entry_points`)에서 시작해 계층이 어떻게 쌓이는지 3~5문장. 가장 많이 import 되는 모듈(`most_imported`)이 공용 기반인지 짚는다.
2. **순환 import** — `cycles` 가 비어 있지 않으면 경로를 `a -> b -> c -> a` 로 적고,
   - 왜 문제인지(초기화 순서에 따라 ImportError, 테스트·재사용 어려움),
   - 끊는 방법 2~3가지(공용 부분을 새 모듈로 분리, 의존 방향 뒤집기, 함수 안에서 늦게 import)를 **이 코드의 모듈 이름으로** 제안한다.
   - 어느 방법이 맞는지는 코드를 읽어야 알 수 있으므로, 필요하면 순환에 포함된 파일만 읽는다. 없으면 "순환 없음"이라고 쓴다.
3. **그림 보는 법** — 결과 파일 경로(`output_absolute`)와 아래 방법을 안내한다.
   - GitHub 에 올리면 `.md` 안의 ` ```mermaid ` 블록이 자동으로 그려진다.
   - VS Code 는 Mermaid 지원 확장(예: "Markdown Preview Mermaid Support")을 설치하고 Markdown 미리보기로 본다.
   - 인터넷이 막힌 환경에서는 확장이나 `mmdc`(mermaid-cli)를 패키지 미러로 설치해 PNG/SVG 로 변환한다.

## 하지 말 것

- Mermaid 코드를 직접 새로 쓰거나 고치기 (그래프를 바꾸고 싶으면 스크립트를 다시 실행)
- 스크립트가 보여 주지 않은 의존 관계(동적 import, 문자열로 만든 import 등)를 있는 것처럼 쓰기. 한계로 밝힌다.
