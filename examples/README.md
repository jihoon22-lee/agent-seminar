# 예제 목록

세미나의 모든 예제를 한눈에 보는 표입니다. 폴더 이름의 번호(C1, S1a, M1, P1, X1)는 슬라이드와 가이드에서 쓰는 번호와 같습니다.
모든 예제는 **opencode 1.19.5** 기준입니다. 각 폴더의 `README.md`에 따라 하기, 기대 결과, 동작 원리, 문제 해결이 있습니다.

- **난이도**는 각 README의 머리말 줄에서 그대로 옮겼습니다.
- **모델 필요 여부**: `불필요`는 모델 없이 끝까지 해 볼 수 있다는 뜻입니다. `선택`은 핵심은 모델 없이 확인되고 모델을 붙이면 실제 대화까지 볼 수 있다는 뜻입니다. `필요`는 스킬이나 도구가 쓰이는 모습을 보려면 모델이 있어야 한다는 뜻입니다. 모델 설정이 없다면 무료 모델 `-m opencode/big-pickle`을 지정하세요.
- 모든 예제의 `check.py`는 모델 없이(가짜 모델 서버로) 동작을 검증합니다. 실행 방법은 `python check.py` (Linux는 `python3 check.py`)입니다.
- 처음 열었을 때 `.opencode/` 폴더가 있는 예제는 `@opencode-ai/plugin` 자동 설치를 시도합니다. 인터넷이 막혀 있으면 첫 시작이 약 70초 멈출 수 있습니다. ([플러그인 가이드](../docs/guide/04-plugins.md)의 첫 실행 절)

가이드: [0. 개념](../docs/guide/00-concepts.md) · [1. 설정](../docs/guide/01-config.md) · [2. 스킬](../docs/guide/02-skills.md) · [3. MCP](../docs/guide/03-mcp.md) · [4. 플러그인](../docs/guide/04-plugins.md) · [5. 문제 해결](../docs/guide/05-troubleshooting.md)

## 설정 (00-config)

| ID | 폴더 | 무엇을 보여 주나 | 난이도 | 모델 | 가이드 |
|---|---|---|---|---|---|
| C1 | [c1-scope-merge](00-config/c1-scope-merge/) | 설정 다섯 겹이 쌓이는 순서와 배열·객체·단일 값의 병합 규칙 | ★☆☆ | 불필요 | [1. 설정](../docs/guide/01-config.md) |
| C2 | [c2-variables](00-config/c2-variables/) | `{env:}`, `{file:}` 치환과 `debug config` 마스킹의 함정 | ★★☆ | 선택 | [1. 설정](../docs/guide/01-config.md) |
| C3 | [c3-config-content-overlay](00-config/c3-config-content-overlay/) | `OPENCODE_CONFIG_CONTENT`로 이번 실행에만 MCP와 설정 얹기 | ★★☆ | 선택 | [1. 설정](../docs/guide/01-config.md) |
| C4 | [c4-isolated-testing](00-config/c4-isolated-testing/) | 일회용 샌드박스에서 설정을 안전하게 실험하고 격리 스위치 비교 | ★★☆ | 불필요 | [1. 설정](../docs/guide/01-config.md) |
| C5 | [c5-permissions](00-config/c5-permissions/) | `permission`의 allow/ask/deny와 "마지막 일치가 이긴다" 규칙 | ★★☆ | 선택 | [1. 설정](../docs/guide/01-config.md) |

## 스킬 (01-skills)

| ID | 폴더 | 무엇을 보여 주나 | 난이도 | 모델 | 가이드 |
|---|---|---|---|---|---|
| S1a | [s1a-commit-message](01-skills/s1a-commit-message/) | `SKILL.md` 한 장으로 팀 커밋 메시지 규칙 적용 | ★☆☆ | 필요 | [2. 스킬](../docs/guide/02-skills.md) |
| S1b | [s1b-code-review](01-skills/s1b-code-review/) | 리뷰 체크리스트와 출력 형식을 스킬로 고정 | ★☆☆ | 필요 | [2. 스킬](../docs/guide/02-skills.md) |
| S1c | [s1c-postmortem](01-skills/s1c-postmortem/) | 한 스킬이 대화형과 문서(메모 기반) 두 모드로 동작 | ★★☆ | 필요 | [2. 스킬](../docs/guide/02-skills.md) |
| S2a | [s2a-workthrough](01-skills/s2a-workthrough/) | 템플릿과 예시를 필요할 때만 읽는 점진적 공개 | ★★☆ | 필요 | [2. 스킬](../docs/guide/02-skills.md) |
| S2b | [s2b-api-design](01-skills/s2b-api-design/) | `SKILL.md`를 목차로 두고 `references/`를 요청별로 읽게 하기 | ★★☆ | 필요 | [2. 스킬](../docs/guide/02-skills.md) |
| S2c | [s2c-adr](01-skills/s2c-adr/) | 템플릿(구조)과 예시(수준)를 곁들인 ADR 스킬 | ★★☆ | 필요 | [2. 스킬](../docs/guide/02-skills.md) |
| S3a | [s3a-log-analysis](01-skills/s3a-log-analysis/) | 스크립트가 로그를 요약하고 모델이 해석 | ★★☆ | 필요 | [2. 스킬](../docs/guide/02-skills.md) |
| S3b | [s3b-release-notes](01-skills/s3b-release-notes/) | 커밋 분류는 스크립트가, 문장은 모델이 | ★★☆ | 필요 | [2. 스킬](../docs/guide/02-skills.md) |
| S3c | [s3c-secret-scan](01-skills/s3c-secret-scan/) | 커밋 전 비밀값 검사 스크립트와 오탐 판단 | ★★☆ | 필요 | [2. 스킬](../docs/guide/02-skills.md) |
| S4a | [s4a-html-report](01-skills/s4a-html-report/) | CSV로 브라우저에서 열리는 HTML 리포트 생성 | ★★☆ | 필요 | [2. 스킬](../docs/guide/02-skills.md) |
| S4b | [s4b-mermaid-diagram](01-skills/s4b-mermaid-diagram/) | 소스의 import를 읽어 Mermaid 다이어그램과 순환 import 탐지 | ★★☆ | 필요 | [2. 스킬](../docs/guide/02-skills.md) |
| S5a | [s5a-description-good-bad](01-skills/s5a-description-good-bad/) | description 한 줄이 스킬이 열리는지를 가른다 | ★☆☆ | 선택 | [2. 스킬](../docs/guide/02-skills.md) |
| S5b | [s5b-manual-and-permission](01-skills/s5b-manual-and-permission/) | `permission.skill`로 수동 전용 스킬 만들기 (머리말 플래그는 무효) | ★★☆ | 선택 | [2. 스킬](../docs/guide/02-skills.md) |
| S5c | [s5c-scope-global-project](01-skills/s5c-scope-global-project/) | 전역, 프로젝트, `skills.paths`, `skills.urls`의 범위와 함정 | ★★☆ | 불필요 | [2. 스킬](../docs/guide/02-skills.md) |

## MCP (02-mcp)

| ID | 폴더 | 무엇을 보여 주나 | 난이도 | 모델 | 가이드 |
|---|---|---|---|---|---|
| M1 | [m1-stdio-minimal](02-mcp/m1-stdio-minimal/) | 표준 라이브러리만으로 만든 가장 작은 stdio 서버와 JSON-RPC 대화 | ★☆☆ | 선택 | [3. MCP](../docs/guide/03-mcp.md) |
| M2 | [m2-python-sdk](02-mcp/m2-python-sdk/) | 같은 서버를 공식 Python SDK로 (코드 124줄 대 24줄) | ★★☆ | 선택 | [3. MCP](../docs/guide/03-mcp.md) |
| M3 | [m3-env-config](02-mcp/m3-env-config/) | `environment`로 토큰과 설정 넘기기, 토큰이 없을 때의 거절 | ★★☆ | 선택 | [3. MCP](../docs/guide/03-mcp.md) |
| M4 | [m4-remote-http](02-mcp/m4-remote-http/) | 같은 서버를 Streamable HTTP 원격으로, `oauth: false`와 401 진단 | ★★☆ | 선택 | [3. MCP](../docs/guide/03-mcp.md) |
| M5 | [m5-team-shared-server](02-mcp/m5-team-shared-server/) | 팀이 함께 쓰는 원격 서버: 사용자별 토큰, 감사 로그, 토큰 교체 | ★★☆ | 선택 | [3. MCP](../docs/guide/03-mcp.md) |
| M6 | [m6-sqlite-tickets](02-mcp/m6-sqlite-tickets/) | 장애 티켓 DB를 읽기 전용, 작은 도구, 작은 결과로 연결 | ★★★ | 선택 | [3. MCP](../docs/guide/03-mcp.md) |
| M7 | [m7-resources-prompts](02-mcp/m7-resources-prompts/) | MCP의 resources(`@`)와 prompts(`/서버:프롬프트`) 노출 방식 | ★★☆ | 선택 | [3. MCP](../docs/guide/03-mcp.md) |
| M8 | [m8-enable-disable-deny](02-mcp/m8-enable-disable-deny/) | 서버 끄기, 도구 deny, 에이전트별 설정과 토큰 비용 측정 | ★★☆ | 불필요 | [3. MCP](../docs/guide/03-mcp.md) |
| M9 | [m9-pitfalls](02-mcp/m9-pitfalls/) | 일부러 고장 낸 서버 네 가지와 진단 순서 | ★★☆ | 불필요 | [3. MCP](../docs/guide/03-mcp.md) |

## 플러그인 (03-plugins)

| ID | 폴더 | 무엇을 보여 주나 | 난이도 | 모델 | 가이드 |
|---|---|---|---|---|---|
| P1 | [p1-env-guard](03-plugins/p1-env-guard/) | `tool.execute.before`로 `.env` 읽기와 수정을 차단 | ★★☆ | 필요 | [4. 플러그인](../docs/guide/04-plugins.md) |
| P2 | [p2-dangerous-command-guard](03-plugins/p2-dangerous-command-guard/) | 규칙 표로 `rm -rf`, `git push --force` 등 위험 명령 차단 | ★★☆ | 필요 | [4. 플러그인](../docs/guide/04-plugins.md) |
| P3 | [p3-audit-log](03-plugins/p3-audit-log/) | `tool.execute.after`로 도구 호출을 JSONL 감사 로그로 기록 | ★★☆ | 필요 | [4. 플러그인](../docs/guide/04-plugins.md) |
| P4 | [p4-notify-on-idle](03-plugins/p4-notify-on-idle/) | `event` 훅으로 작업 완료와 승인 대기 알림 | ★★☆ | 필요 | [4. 플러그인](../docs/guide/04-plugins.md) |
| P5 | [p5-shell-env](03-plugins/p5-shell-env/) | `shell.env`로 에이전트의 셸에만 환경 변수 주입 | ★☆☆ | 필요 | [4. 플러그인](../docs/guide/04-plugins.md) |
| P6 | [p6-custom-tool](03-plugins/p6-custom-tool/) | `tool` 훅으로 모델이 부르는 커스텀 도구 등록, 패키지 미러 | ★★☆ | 필요 | [4. 플러그인](../docs/guide/04-plugins.md) |
| P7 | [p7-compaction-context](03-plugins/p7-compaction-context/) | 실험적 훅으로 세션 압축 때 고정 사실을 요약에 포함 | ★★★ | 필요 | [4. 플러그인](../docs/guide/04-plugins.md) |
| P8 | [p8-load-methods](03-plugins/p8-load-methods/) | 플러그인을 불러오는 네 가지 방법과 중복 로드, `--pure` | ★★☆ | 불필요 | [4. 플러그인](../docs/guide/04-plugins.md) |

## 종합 (04-combined)

| ID | 폴더 | 무엇을 보여 주나 | 난이도 | 모델 | 가이드 |
|---|---|---|---|---|---|
| X1 | [x1-three-ways](04-combined/x1-three-ways/) | 같은 "용어 조회"를 스킬, MCP, 플러그인으로 각각 만들어 비교 | ★★☆ | 필요 | [0. 개념](../docs/guide/00-concepts.md) |
| X2 | [x2-incident-analysis](04-combined/x2-incident-analysis/) | MCP(데이터) + 스킬(절차) + 플러그인(감사, 쓰기 범위 제한)이 한 작업에서 협력 | ★★★ | 필요 | [4. 플러그인](../docs/guide/04-plugins.md) |
