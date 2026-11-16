# agent-seminar

**AI 에이전트 확장하기: 스킬, MCP, 플러그인 (opencode 편)**

코딩 에이전트 opencode에 팀의 지식과 시스템, 규칙을 붙이는 세 가지 방법을 다룬 60분 세미나 자료입니다.
발표 슬라이드와 글로 읽는 가이드, 그리고 직접 실행해 볼 수 있는 예제 38개가 들어 있습니다.

- **발표 자료**: https://jihoon22-lee.github.io/agent-seminar/ (브라우저에서 바로 열립니다. `?` 키로 단축키를 볼 수 있습니다)
- **가이드**: [docs/guide](docs/guide/)
- **예제 목록**: [examples/README.md](examples/README.md)

모든 내용은 **opencode 1.19.5**에서 직접 실행해 확인했습니다. Windows(PowerShell)와 Linux 양쪽에서 검증했습니다.

## 한 줄 요약

| 확장 | 한 줄 설명 | 이럴 때 |
|---|---|---|
| **스킬** | 모델이 필요할 때 꺼내 읽는 업무 매뉴얼 (`SKILL.md`) | 모델이 알아야 할 절차나 지식: 커밋 규칙, 리뷰 기준, 분석 순서 |
| **MCP** | 에이전트 바깥의 프로그램이 도구를 제공하는 표준 방식 | 에이전트 밖의 시스템에 닿아야 할 때: 티켓 DB, 위키, 모니터링 |
| **플러그인** | 도구 실행 앞뒤에 끼어드는 코드 | 모델 판단과 상관없이 항상 일어나야 할 때: 차단, 감사 로그, 알림 |

셋을 켜고 끄는 곳은 `opencode.json`입니다. 개념 설명은 [가이드 0. 개념](docs/guide/00-concepts.md)에서 시작하세요.

## 준비물

- **opencode 1.19.5** (`opencode --version`으로 확인)
- **Python 3.10 이상**: 예제 스크립트와 MCP 서버는 표준 라이브러리만 씁니다. M2 예제만 `mcp` 패키지를 설치합니다.
- **git**
- **Node** (선택): 플러그인 예제의 단위 테스트를 돌릴 때 씁니다.
- **모델**: 평소 쓰는 모델을 그대로 쓰면 됩니다. 설정된 모델이 없다면 무료 모델 `opencode/big-pickle`을 `-m`으로 지정할 수 있습니다.

예제는 실행 중에 인터넷에 접속하지 않습니다.
`.opencode/` 폴더가 있는 예제는 처음 실행할 때 opencode가 npm 패키지 `@opencode-ai/plugin`을 설치하려고 합니다.
npm 레지스트리나 미러에 닿지 않으면 첫 시작이 1분쯤 멈췄다가 그대로 진행됩니다.

## 시작하기

PowerShell:

```powershell
git clone https://github.com/jihoon22-lee/agent-seminar
cd agent-seminar\examples\01-skills\s1a-commit-message
opencode
```

Linux bash:

```bash
git clone https://github.com/jihoon22-lee/agent-seminar
cd agent-seminar/examples/01-skills/s1a-commit-message
opencode
```

예제 폴더 하나하나가 독립된 opencode 프로젝트입니다. 폴더에 들어가서 opencode를 실행하면 그 예제의 설정, 스킬, 플러그인만 적용됩니다.
각 README는 같은 순서로 되어 있습니다: 무엇을 보여 주나, 실무에서는, 파일 구성, 따라 하기, 기대 결과, 동작 원리, 직접 바꿔 보기, 주의할 점.

Linux에서 `python` 명령이 없으면 예제 설정과 명령의 `python`을 `python3`로 바꾸세요.

## 예제

| 폴더 | 내용 | 예제 |
|---|---|---|
| [examples/00-config](examples/00-config/) | opencode.json의 위치와 병합, 환경 변수, 설정 덧씌우기, 격리, 권한 | C1–C5 |
| [examples/01-skills](examples/01-skills/) | `SKILL.md` 하나짜리부터 참고 문서, 스크립트, 결과물 생성까지. description 작성법과 공유 방법 | S1a–S5c |
| [examples/02-mcp](examples/02-mcp/) | 표준 라이브러리 서버, 공식 SDK, 환경 변수, 원격 HTTP, SQLite, 리소스와 프롬프트, 도구 관리, 함정 | M1–M9 |
| [examples/03-plugins](examples/03-plugins/) | .env 차단, 위험 명령 차단, 감사 로그, 알림, 셸 환경, 커스텀 도구, 압축 훅, 불러오는 방법 | P1–P8 |
| [examples/04-combined](examples/04-combined/) | 같은 일을 셋으로 해 보기, 셋을 엮은 장애 분석 | X1, X2 |

전체 목록과 난이도는 [examples/README.md](examples/README.md)에 있습니다.

## 가이드

| 문서 | 내용 |
|---|---|
| [0. 개념](docs/guide/00-concepts.md) | 스킬, MCP, 플러그인은 무엇이고 무엇이 다른가 |
| [1. opencode.json](docs/guide/01-config.md) | 설정 위치와 범위, 병합, 변수 치환, 권한 |
| [2. 스킬](docs/guide/02-skills.md) | 스킬 만들기와 공유하기 |
| [3. MCP](docs/guide/03-mcp.md) | MCP 서버 만들기, 로컬과 원격 |
| [4. 플러그인](docs/guide/04-plugins.md) | 훅, 이벤트, 플러그인 만들기 |
| [5. 문제 해결](docs/guide/05-troubleshooting.md) | 증상별 원인과 해결, Windows 주의점 |

## 예제가 내 PC에서 도는지 확인하기

모든 예제에는 `check.py`가 있습니다. 실제 opencode 설정과 세션 기록은 건드리지 않습니다. 임시 폴더로 격리해서 실행하고, 끝나면 지웁니다.

```powershell
python tools\run_checks.py examples\01-skills        # 모델 없이 (몇 분)
python tools\run_checks.py examples --model          # 실제 모델 호출까지
```

```bash
python3 tools/run_checks.py examples/01-skills
python3 tools/run_checks.py examples --model
```

모델 없이 하는 검사는 opencode를 실제로 실행합니다. 모델 응답이 필요한 부분은 정해진 도구 호출을 하는 가짜 모델 서버로 확인합니다.
`--model`을 붙이면 실제 모델로도 확인합니다. 모델 응답은 실행마다 달라서 이 검사는 경고(WARN)로만 표시합니다.

## 발표 자료 조작법

| 키 | 동작 |
|---|---|
| `→` `Space` / `←` | 다음 / 이전 |
| 숫자 + `Enter` | 해당 슬라이드로 이동 |
| `O` | 전체 보기 |
| `N` | 발표자 메모 |
| `P` | 발표자 창 (메모, 다음 슬라이드, 타이머) |
| `F` | 전체 화면 |
| `S` | 짧은 버전: 오른쪽 위에 "심화"라고 표시된 슬라이드를 건너뛰며 넘김 (60분 발표용) |

브라우저의 인쇄(PDF로 저장)를 쓰면 한 장에 슬라이드 하나씩 출력됩니다.
슬라이드 원본은 `slides/src/`에 있고, `python tools/build_slides.py`가 `slides/index.html`을 만듭니다.

## 알려 둘 것

- 실제 모델 응답 예시는 무료 모델로 얻은 것입니다. 무료 모델 한도 때문에 확인하지 못한 부분은 각 README에 "미검증"으로 표시했습니다.
- opencode는 빠르게 바뀝니다. 공식 문서 사이트에는 다음 버전의 설정 형식(`mcp.servers`, `plugins`)이 먼저 올라와 있는데, 1.19.5에서는 동작하지 않습니다.
- [S2a 작업 기록 스킬](examples/01-skills/s2a-workthrough/)은 MIT 라이선스 스킬을 옮겨 온 것입니다. 출처와 라이선스는 해당 폴더의 `NOTICE.md`에 있습니다.
- 글꼴: 발표 자료는 IBM Plex Sans KR / IBM Plex Mono(SIL Open Font License 1.1)를 발표에 쓰는 글자만 남겨 줄인 것입니다. 라이선스 조건에 따라 이름을 바꿨습니다. 자세한 내용은 [slides/assets/fonts](slides/assets/fonts/)를 보세요.

## 라이선스

[MIT](LICENSE)
