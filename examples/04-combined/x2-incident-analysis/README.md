# X2 장애 분석 - MCP + 스킬 + 플러그인이 함께 일하기

> 구성: MCP(데이터) + 스킬(절차) + 플러그인(감사·가드) | 난이도: ★★★ | 필요: opencode 1.19.5, Python 3.10+, 첫 실행 때 npm 레지스트리/미러 | 슬라이드: 종합 데모

## 무엇을 보여 주나

세 가지 확장이 **각자 맡은 일**이 다르다는 것을 한 작업으로 보여 줍니다. "이번 주 payment 서비스 장애 분석 리포트 만들어줘" 한 문장에서

- **MCP** 는 *데이터*를 줍니다: 티켓 DB 를 **읽기 전용**으로 조회하는 도구들.
- **스킬** 은 *절차*를 줍니다: 통계 → 관련 티켓 → 가설 → 템플릿대로 리포트 작성.
- **플러그인** 은 *안전장치*를 겁니다: 모든 도구 호출을 감사 로그로 남기고, `reports/` 밖으로의 파일 쓰기를 막습니다.

## 실무에서는

- 장애 회고(포스트모템) 초안, 주간 운영 리포트처럼 **"데이터 조회 + 정해진 분석 순서 + 정해진 서식"** 이 있는 반복 업무.
- 에이전트에게 운영 데이터를 줄 때: 읽기 전용 MCP 로 데이터를 주고, 쓰기 범위는 플러그인 가드로 좁히고, 무슨 일을 했는지 감사 로그로 남기는 3단 구성.
- 같은 틀에서 데이터 소스만 바꾸면(모니터링, 로그 검색) 다른 분석 리포트도 만들 수 있습니다.

## 파일 구성

```
x2-incident-analysis/
├── README.md
├── prepare.py                 # 가짜 티켓 DB(tickets.db) 생성. 여러 번 실행해도 됨
├── check.py                   # 자동 검증
├── opencode.json              # MCP: tickets = ["python", "tickets_server.py"]
├── tickets_server.py          # 읽기 전용 티켓 DB MCP 서버 (stdio, 표준 라이브러리)
├── .opencode/
│   ├── skills/incident-analysis/
│   │   ├── SKILL.md           # 5단계 절차
│   │   └── templates/report.md  # 리포트 서식
│   └── plugins/audit-guard.js # 감사 로그 + reports/ 밖 쓰기 차단
├── tickets.db                 # (prepare.py 가 생성, git 제외)
├── reports/                   # (리포트 저장 위치, git 제외)
└── logs/audit.jsonl           # (감사 로그, git 제외)
```

## 따라 하기

> 평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 `opencode -m opencode/big-pickle` 처럼 무료 모델을 지정하세요.
> Linux 에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`opencode.json` 의 `command` 도 함께)

PowerShell:

```powershell
cd examples\04-combined\x2-incident-analysis
python prepare.py
opencode mcp list        # ✓ tickets connected
opencode
```

Linux (bash):

```bash
cd examples/04-combined/x2-incident-analysis
python3 prepare.py
opencode mcp list
opencode
```

`prepare.py` 는 **오늘을 기준일**로 삼아 "최근 7일 동안 payment 장애가 있었던" 가짜 데이터를 만듭니다. (고정하려면 `python prepare.py --as-of 2026-11-17`)

opencode 에 입력:

```
이번 주 payment 서비스 장애 분석 리포트 만들어줘
```

끝나면 `reports/<기준일>-payment.md` 가 생기고, `logs/audit.jsonl` 에 모든 도구 호출이 남습니다. 가드를 시험하려면 이어서:

```
방금 분석 내용을 프로젝트 루트의 notes.txt 에도 저장해 줘
```

모델이 `write` 를 부르면 플러그인이 막고, 모델은 "reports/ 밖에는 쓸 수 없다" 는 오류를 받습니다.

자동 검증: `python check.py` (Linux: `python3 check.py`). 검증이 끝나면 만든 `tickets.db`, `reports/`, `logs/` 를 지우므로 직접 해 볼 때는 `prepare.py` 를 다시 실행하세요.

## 기대 결과

`check.py` 가 **스크립트된 가짜 모델**(정해진 순서로 도구를 호출하는 로컬 서버)로 같은 흐름을 실제 opencode 에 태운 transcript 입니다. `→`, `⚙`, `✗` 줄은 opencode 가 낸 그대로입니다(Linux, 기준일 2026-11-17).

```
> build · scripted

→ Skill "incident-analysis"
⚙ tickets_week_range Unknown
⚙ tickets_week_range {"offset":1}
⚙ tickets_ticket_stats {"service":"payment","from_date":"2026-11-11","to_date":"2026-11-17"}
⚙ tickets_ticket_stats {"service":"payment","from_date":"2026-11-04","to_date":"2026-11-10"}
⚙ tickets_search_tickets {"service":"payment","from_date":"2026-11-13","to_date":"2026-11-14","severity":"P1"}
⚙ tickets_recent_deploys {"service":"payment","from_date":"2026-11-11","to_date":"2026-11-17"}
⚙ tickets_get_ticket {"ticket_id":1030}
→ Read .opencode/skills/incident-analysis/templates/report.md
✗ Write notes.txt failed
Error: [audit-guard] reports/ 밖에는 파일을 쓸 수 없습니다: .../x2-incident-analysis/notes.txt. 리포트는 reports/ 폴더 안에 저장하세요.

← Write reports/2026-11-17-payment.md
Wrote file successfully.
```

`logs/audit.jsonl` (일부, 실제 출력):

```
{"ts":"2026-11-16T16:07:54.933Z","phase":"call","tool":"tickets_ticket_stats","session":"ses_...","callID":"call_..._0","args":"{\"service\":\"payment\",\"from_date\":\"2026-11-11\",\"to_date\":\"2026-11-17\"}"}
{"ts":"2026-11-16T16:07:54.950Z","phase":"result","tool":"tickets_ticket_stats","callID":"call_..._0","ms":17,"outputChars":...}
{"ts":"2026-11-16T16:07:55.186Z","phase":"blocked","tool":"write","callID":"call_..._0","reason":"reports/ 밖에는 파일을 쓸 수 없습니다: ...notes.txt. ..."}
```

`prepare.py` 가 만드는 이야기(가짜): 기준일 -4일 14:05 에 `payment-api v2.14.0`(DB 커넥션 풀 max 40→10, 카드사 호출 재시도 추가)이 배포된 뒤 티켓이 급증(피크 일자 18건),
-3일 09:30 의 `v2.14.1` 핫픽스(풀 max 20) 뒤 감소, -2일 카드사 B 지연으로 일부 재발. 최근 7일 43건 vs 그 전 7일 6건.
좋은 리포트라면 배포 시각과 티켓 급증을 연결하고, 카드사 B 같은 외부 요인도 가설에 넣습니다.

실제 모델이 만든 리포트와 transcript 는 이 문서를 쓰는 시점에 무료 모델 한도가 소진되어 **확인하지 못했습니다**(`python check.py --model` 로 확인).

## 누가 무엇을 했나 - transcript 읽는 법

| transcript 줄 | 하는 쪽 | 역할 |
|---|---|---|
| `→ Skill "incident-analysis"` | **스킬** | 모델이 요청 문장을 보고 스킬을 로드. 이후 행동은 `SKILL.md` 의 5단계를 따름 |
| `⚙ tickets_week_range`, `ticket_stats` ... | **MCP** | 1~3단계: 기간 정하기, 통계, 관련 티켓·배포 조회. 데이터는 전부 MCP 에서 옴 |
| `→ Read .../templates/report.md` | **스킬** | 5단계: 스킬이 가리킨 서식 파일을 읽음 (스킬 폴더의 부속 파일) |
| `✗ Write notes.txt failed ... [audit-guard]` | **플러그인** | `tool.execute.before` 훅이 예외를 던져 차단. 오류 문장이 모델에게 전달됨 |
| `← Write reports/2026-11-17-payment.md` | 모델 + 플러그인 허용 | `reports/` 안이라 통과 |
| (화면에는 없음) `logs/audit.jsonl` | **플러그인** | 위 모든 호출(`skill`, `tickets_*`, `read`, `write`)이 훅으로 기록됨 |

## 동작 원리

- **MCP (`tickets_server.py`)**: 도구 6개(`week_range`, `list_services`, `ticket_stats`, `search_tickets`, `get_ticket`, `recent_deploys`). 쓰기 도구가 없고,
  DB 도 sqlite 의 `mode=ro` URI 로 열어서 **도구 설계와 DB 연결 두 겹**으로 읽기 전용입니다(`check.py` 가 `DELETE` 가 거부되는 것을 확인).
  "이번 주" 를 모델이 추측하지 않도록 `week_range` 가 기준일까지 최근 7일을 알려 줍니다.
- **스킬 (`incident-analysis`)**: `description` 에 "장애 분석 리포트", "포스트모템 초안" 같은 한국어 트리거를 넣어 요청 문장과 맞게 했고, 본문은 5단계 절차 + 저장 규칙입니다.
  서식(`templates/report.md`)은 스킬 폴더 안에 둬서 스킬을 복사하면 같이 따라갑니다.
- **플러그인 (`audit-guard.js`)**: 두 훅을 씁니다.
  - `tool.execute.before`: 호출을 기록하고, `write`/`edit`/`apply_patch` 의 대상 경로가 `reports/` 밖이면 예외를 던져 막습니다. `..` 로 빠져나가는 경로도 `path.relative` 로 막습니다.
  - `tool.execute.after`: 걸린 시간과 결과 크기를 기록합니다. MCP 도구의 결과는 `output.output` 문자열이 아니라 `output.content`(MCP 원형)로 오기 때문에 둘 다 처리합니다.
  - 훅은 **내장 도구, 스킬, MCP 도구 호출 모두에** 불립니다(확인: 감사 로그에 `skill`, `tickets_*`, `read`, `write` 가 전부 남음).

## 직접 바꿔 보기

1. `SKILL.md` 3단계에 "배포가 없었던 서비스(예: `search`)는 비교용으로 한 번 더 조회" 같은 단계를 추가하고 리포트가 바뀌는지 보세요.
2. 가드의 허용 폴더를 `reports/` 에서 `out/` 으로 바꿔 보세요(`audit-guard.js` 의 `reportsDir`). 리포트 저장이 막히는 것을 확인합니다.
3. 가드를 더 강하게: `opencode.json` 에 `"permission": {"bash": "deny"}` 를 추가해 셸 우회를 선언적으로 막아 보세요.

## 주의할 점 / 문제 해결

- **가드의 한계**: 이 가드는 `write`/`edit`/`apply_patch` 만 검사합니다. 모델이 `bash` 로 `echo x > notes.txt` 처럼 쓰는 것은 **막지 못하고 기록만** 합니다.
  실제로 쓰기를 막아야 한다면 `permission` 설정(위 3번)을 함께 쓰세요. `apply_patch` 는 일부 모델에서만 제공되어 이 환경에서는 가드 로직을 단위 검사로만 확인했습니다.
- **export 는 플러그인 함수만 하세요.** 숫자·문자열·객체 같은 함수가 아닌 값(`export const X = 1`)을 export 하면 opencode 가 **파일 전체를 건너뜁니다.** 평소 실행에는 아무 출력도 없고, `opencode --print-logs` 로 실행해야 `failed to load plugin ... Plugin export is not a function` 오류가 보입니다. 보조 함수를 export 하면 파일은 로드되지만 그 함수까지 플러그인으로 호출됩니다. 그러니 도우미는 export 하지 마세요. 문법 오류나 import 오류는 `--print-logs` 에도 아무것도 남기지 않으니, 플러그인이 로드됐는지는 플러그인이 직접 남기는 흔적(로드 로그 등)으로 확인하세요.
- `tickets.db` 가 없으면 MCP 서버가 `prepare.py` 를 먼저 실행하라는 오류를 냅니다.
- 인자가 없는 도구 호출은 transcript 에 `Unknown` 으로 찍힙니다(`⚙ tickets_week_range Unknown`). 오류가 아닙니다.
- `opencode run` 으로 실행할 때는 프로젝트 폴더에서 실행하세요. (Linux 에서는 `$PWD` 가 프로젝트 폴더를 정합니다.)
- `.opencode/` 가 있어 첫 실행에 `@opencode-ai/plugin` 자동 설치가 일어납니다. 필요 없는 의존성이지만(이 플러그인은 import 하지 않음) 설치 시도는 합니다.
  레지스트리에 닿지 않으면 플러그인이 있는 이 폴더는 **시작할 때마다 약 70초** 멈춥니다. 완전히 새 환경에서의 첫 시작은 약 130초까지 걸렸습니다([P6](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러) 참고). 이 플러그인은 설치와 무관하게 로드됩니다.
- 로그에 인자 일부(300자)가 그대로 남습니다. 비밀 값을 인자로 받는 도구가 있다면 기록 전에 가려야 합니다.
