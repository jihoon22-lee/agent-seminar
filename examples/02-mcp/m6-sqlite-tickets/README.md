# M6 업무 시스템 연결하기: 읽기 전용 장애 티켓 DB

> 구성: 합성 티켓 DB(SQLite, 약 200건) + 조회 전용 MCP 서버 | 난이도: ★★★ | 필요: opencode 1.19.5, Python 3.10+ (sqlite3 내장) | 슬라이드: MCP — 실제 시스템 연결

## 무엇을 보여 주나

"에이전트가 업무 시스템을 알게 한다"는 말의 실제 모습이다. 장애 티켓 DB를 에이전트에게 열어 주되, **읽기 전용으로**, **결과 크기를 제한해서**, **모델이 오해하지 않게 도구 설명을 꼼꼼히 써서** 노출한다.
이 세 가지(최소 권한, 결과 크기 제한, 설명이 곧 설명서)는 이슈 트래커, 모니터링, 배포 이력 같은 어떤 시스템을 연결하든 똑같이 적용된다.
그다음 "지난주 payment 서비스 장애 티켓 요약해줘"라는 평범한 문장 하나가 도구 호출 몇 번으로 풀리는 과정을 본다.

## 실무에서는

- 장애 대응/회고 때 티켓, 알림, 배포 이력을 사람이 이 화면 저 화면에서 모아 요약한다. MCP로 조회 도구를 연결해 두면 "지난주 payment 장애 요약", "SEV1이 가장 많은 서비스는?" 같은 질문을 에이전트가 직접 모아서 답한다.
- 연결 대상이 이슈 트래커 API든 자체 운영 DB든 모니터링이든 설계 질문은 같다: **무엇을 읽게 할까, 무엇은 절대 못 하게 할까, 한 번에 얼마나 돌려줄까, 모델에게 어떻게 설명할까.**
- 쓰기 도구(티켓 닫기, 배포 실행)는 읽기 도구가 충분히 검증된 뒤에 별도 서버로 분리해서, 권한 설정(`permission`, M8)과 함께 추가하는 것이 안전하다.

## 파일 구성

```
m6-sqlite-tickets/
  README.md        이 문서
  prepare.py       tickets.db를 처음부터 다시 만든다 (약 200건, 같은 기준일이면 항상 같은 내용)
  server.py        읽기 전용 MCP 서버: search_tickets, get_ticket, ticket_stats
  opencode.json    mcp.tickets: ["python", "server.py"]
  tickets.db       (prepare.py가 생성, .gitignore 대상)
  check.py         자동 검증 (읽기 전용, 결과 제한, 결정적 생성 등)
  fake_llm.py      가짜 LLM 서버. check.py 가 모델 없이 opencode 의 요청을 기록·재현하는 데 씀
```

## 따라 하기

> Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`opencode.json`의 `command`도 `["python3", "server.py"]`로)
> 이 예제 폴더에서 실행한다.

**1. 티켓 DB 만들기**

```powershell
cd examples\02-mcp\m6-sqlite-tickets
python prepare.py
```

```bash
cd examples/02-mcp/m6-sqlite-tickets
python3 prepare.py
```

날짜는 "실행한 날을 기준으로 며칠 전"으로 만들어진다. 그래서 **'지난주'를 물어보려면 그 주에 prepare.py를 실행**해야 한다. 며칠 뒤에 다시 하려면 `prepare.py`를 다시 실행한다. (기준일을 고정하려면 `python prepare.py --today 2026-03-18`)

**2. 연결 확인**

```powershell
opencode mcp list
```

```bash
opencode mcp list
```

**3. 질문하기** — 평소 쓰는 모델로 `opencode`를 실행하고 입력한다.

```
지난주 payment 서비스 장애 티켓 요약해줘
```

모델 설정이 없다면:

```powershell
opencode run -m opencode/big-pickle --auto "지난주 payment 서비스 장애 티켓 요약해줘"
```

```bash
opencode run -m opencode/big-pickle --auto "지난주 payment 서비스 장애 티켓 요약해줘"
```

이어서 물어볼 만한 질문:

```
SEV1 장애 티켓 하나를 자세히 보여주고 담당자가 누구인지 알려줘
최근 30일 동안 서비스별 티켓 건수를 알려줘
```

**4. (선택) 에이전트 없이 서버 시험하기** — `python server.py`를 켜고 JSON 한 줄을 붙여 넣는다 (M1 참고).

## 기대 결과

`opencode mcp list`:

```
●  ✓ tickets connected
│      python server.py
```

질문을 하면 opencode 화면에는 모델이 부른 도구가 `⚙ tickets_search_tickets {...}` 줄로 나타난다 (`서버이름_도구이름`). 모델이 위 질문에서 서버로 보내는 호출은 대략 아래와 같고(기준일 2026-11-17, 화요일), 서버가 돌려주는 결과가 **모델이 실제로 읽는 내용**이다. 아래는 같은 인자로 서버를 직접 호출해 얻은 실제 출력이다.

```
>> search_tickets {"service": "payment", "since": "2026-11-09", "until": "2026-11-15", "limit": 20}
총 12건 중 최신 12건 표시
#1195 | 2026-11-15 13:15 | payment | SEV4 | open | dev-e | 결제 영수증 메일의 금액 표기 오류
#1188 | 2026-11-14 10:04 | payment | SEV4 | resolved | dev-b | 결제 승인 응답 지연 (p99 6초)
    해결: DB 커넥션 풀 크기를 상향하고 서비스를 재시작했다
#1187 | 2026-11-14 08:50 | payment | SEV2 | investigating | dev-b | 환불 요청 9건이 대기 상태에서 멈춤
...
#1170 | 2026-11-11 10:05 | payment | SEV1 | resolved | dev-a | 결제 승인 전면 실패 (전체 결제 불가 17분)
    해결: 배포된 설정 변경을 롤백하고 승인 서버를 재기동했다. 포스트모템 작성 예정
...
#1162 | 2026-11-09 19:14 | payment | SEV4 | closed | dev-b | 카드사 연동 타임아웃으로 결제 실패율 39% 상승
    해결: 카드사 장애 확인 후 보조 승인 경로로 우회했다

>> ticket_stats {"group_by": "severity", "service": "payment", "since": "2026-11-09", "until": "2026-11-15"}
severity별 건수 (합계 12건)
- SEV3: 4건
- SEV4: 4건
- SEV2: 3건
- SEV1: 1건
```

모델의 요약은 모델마다 다르다. 좋은 답이라면 기간과 건수(12건), SEV1 1건(#1170, 결제 승인 전면 실패 17분)과 같은 핵심, 미해결 건(#1195, #1187, #1169, #1165)을 짚어야 한다. 요약에 쓰인 숫자가 위 결과와 맞는지 비교해 보자. DB는 실행한 날을 기준으로 만들어지므로 날짜와 건수는 여러분의 결과와 다르다.

잘못된 인자에 대한 서버 응답 (모델이 읽고 다시 시도하는 오류 메시지):

```
>> search_tickets {"service": "pay"}
'service' 값이 올바르지 않습니다: 'pay'. 허용 값: payment, auth, search, notification, billing-batch, gateway
>> search_tickets {"since": "어제"}
'since'는 YYYY-MM-DD 형식이어야 합니다 (받은 값: '어제').
```

## 동작 원리

### 1) 최소 권한: 읽기 전용으로 연다

```python
conn = sqlite3.connect(f"{DB_PATH.resolve().as_uri()}?mode=ro", uri=True)
conn.execute("PRAGMA query_only = ON")
```

- `?mode=ro`로 열면 SQLite 자체가 쓰기를 거부한다. `INSERT`/`UPDATE`/`DELETE`/`DROP`은 모두 `attempt to write a readonly database`로 실패한다. (`check.py`가 `DELETE`와 `DROP TABLE`을 시도해 확인한다.) `PRAGMA query_only`는 연결 수준의 이중 안전장치다.
- 도구가 **조회 세 개뿐**이고, 모델에게 SQL을 직접 쓰게 하지 않는다. 필터(`service`, `status`, `since` ...)는 값으로만 받아서 `?` 바인딩으로 SQL에 넣는다. `group_by`처럼 열 이름이 들어가는 곳은 허용 목록(`service`, `severity`, `status`, `assignee`)에 있는 값만 쓴다. 그래서 `' OR 1=1 --` 같은 문자열도 그냥 검색어일 뿐이다.
- 진짜 시스템이라면 서버 코드의 방어에만 기대지 말고 **연결 계정 자체를 읽기 전용으로** 만든다. (DB는 SELECT 권한만 있는 계정, API는 조회 범위 토큰.) 코드의 방어는 마지막 방어선이다.
- 검색어에 든 `%`, `_`는 LIKE 와일드카드가 아니라 글자 그대로 취급하도록 이스케이프한다.

### 2) 결과 크기 제한

| 제한 | 값 | 이유 |
|------|----|------|
| `search_tickets`가 돌려주는 최대 건수 | 20 (기본 10, `limit`로 조절) | 도구 결과는 모델의 대화에 그대로 쌓인다. 수백 건을 돌려주면 컨텍스트와 비용이 낭비되고 모델이 중요한 줄을 놓친다 |
| 긴 문장(제목, 해결 내용) | 120자에서 자름 | 한 건이 길어도 목록 전체가 읽을 만하게 |
| 전체 건수 | 항상 `총 N건 중 최신 M건 표시`로 알려 줌 | 잘렸다는 사실을 모델이 알아야 "이게 전부"라고 착각하지 않는다 |
| 생략된 건수 | `나머지 K건은 생략: ...좁히거나 limit을 늘리세요` | 다음에 무엇을 하면 되는지(조건을 좁힌다)를 알려 준다 |

범위를 벗어난 `limit`(예: 500)은 오류로 거절하는 대신 20으로 **조용히 보정**한다. 모델이 한 번에 실패하지 않고 쓸 수 있는 결과를 받는다.

### 3) 도구 설명이 곧 설명서

모델이 도구를 쓰는 근거는 `description`과 `inputSchema`뿐이다. `server.py`의 설명에는 아래가 모두 적혀 있다.

- **날짜 형식과 상대 표현**: "날짜는 YYYY-MM-DD 형식이다. '지난주', '어제' 같은 상대 표현은 오늘 날짜를 기준으로 계산해 since/until(둘 다 그날 포함)로 넘겨라." — 이 문장이 없으면 모델이 `since="지난주"`처럼 도구가 이해 못 하는 값을 넣는다. 서버는 이런 값을 `YYYY-MM-DD 형식이어야 합니다`라는 `isError` 메시지로 돌려보내고, 모델은 그 메시지를 읽고 다시 시도한다.
- **허용 값**: `service`, `status`, `severity`는 `enum`으로 전체 후보를 보여 준다. 모델이 `"payments"`처럼 추측하지 않는다.
- **한계**: "최대 20건", "건수가 많으면 조건을 좁혀 다시 호출하라".
- **무엇에 쓰는 도구인가**: `search_tickets`(목록 찾기) / `get_ticket`(한 건 자세히) / `ticket_stats`(분포). 역할이 겹치지 않으면 모델이 올바른 도구를 고른다.
- **오류 메시지도 설명서**: 잘못된 값에는 "허용 값: payment, auth, ..."을, 없는 번호에는 "search_tickets로 번호를 먼저 확인하세요"를 돌려준다.

### 4) "지난주 payment 서비스 장애 티켓 요약해줘"가 풀리는 과정

1. 모델이 질문을 읽고 `tickets_search_tickets`(`서버이름_도구이름`)가 적합하다고 판단한다.
2. 모델이 오늘 날짜를 알아야 '지난주'를 `since`/`until`로 바꿀 수 있다. opencode는 모델에게 가는 시스템 프롬프트에 `Today's date: Tue Nov 17 2026` 같은 줄을 넣어 준다 (가짜 모델 서버로 요청 본문을 기록해 확인했고, `check.py`가 검사한다). 그래도 모델이 계산을 틀릴 수 있으니 화면의 `⚙ tickets_search_tickets {...}` 줄에서 `since`/`until`을 확인하고, 결과의 `created_at`이 기대한 주와 맞는지 본다.
3. `{"service": "payment", "since": "...", "until": "..."}`로 호출하면 서버가 `총 N건 중 최신 M건 표시`와 함께 최신순 목록을 돌려준다.
4. 건수가 `limit`보다 많으면 모델이 조건을 좁히거나 `limit`을 늘려 다시 부르고, 심각한 건(`SEV1`)은 `tickets_get_ticket`으로 자세히 본다.
5. 모델이 수집한 결과를 요약한다. 요약은 모델의 몫이고, 도구가 하는 일은 **정확한 데이터를 적당한 크기로** 주는 것까지다.

## 직접 바꿔 보기

1. **쓰기를 시도해 보기** — `server.py`의 `open_readonly()`에서 `?mode=ro`를 지우고, `python`으로 `conn.execute("DELETE FROM tickets")`가 어떻게 달라지는지 본다. (확인 뒤 되돌린다. 이 DB는 `prepare.py`로 언제든 다시 만들 수 있다.)
2. **설명 망가뜨리기** — `search_tickets`의 `description`에서 날짜 형식과 상대 표현 안내 문장을 지우고 같은 질문을 해 본다. 모델이 어떤 값을 넣는지, 서버의 `isError` 메시지를 받고 어떻게 고치는지 본다.
3. **한도 바꾸기** — `MAX_LIMIT`을 200으로 바꾸고 `limit: 200`을 요구하는 질문("payment 티켓 전부 보여줘")을 해 본다. 응답이 얼마나 길어지고 모델의 요약이 어떻게 달라지는지 비교한다.
4. **도구 추가** — `severity`가 SEV1/SEV2인 열린 티켓만 돌려주는 `open_incidents` 도구를 추가한다. 새 도구가 기존 도구와 역할이 겹치지 않게 설명을 쓰는 연습이다.

## 주의할 점 / 문제 해결

- **`티켓 DB를 읽지 못했습니다` / `tickets.db 파일이 없습니다`** — `python prepare.py`를 먼저 실행한다. 서버는 DB가 없어도 시작은 되고, 도구를 부를 때 `isError`로 안내한다.
- **'지난주' 결과가 비어 있다** — DB를 만든 지 오래됐다. `prepare.py`를 다시 실행해 기준일을 오늘로 새로 잡는다.
- **'지난주'의 범위가 모델마다 다르다** — 지난 7일로 해석하기도 하고, 지난 월~일 한 주로 해석하기도 한다. 모델이 쓴 `since`/`until`을 `⚙ tickets_search_tickets {...}` 줄에서 확인한다. 요약의 근거 기간을 같이 말해 달라고 요청하면 좋다.
- **Windows에서 DB 파일이 지워지지 않는다** — 열린 DB 연결이 남아 있으면 Windows는 파일을 지우지 못한다. `server.py`가 `closing()`으로 호출마다 연결을 닫는 이유다. 직접 스크립트를 만들 때도 `conn.close()`를 잊지 말자.
- **경로에 한글/공백이 있어도** `Path.as_uri()`가 올바른 `file:` URI로 바꿔 준다. 직접 `f"file:{path}?mode=ro"`로 만들면 Windows 경로(`C:\...`)에서 깨질 수 있다.
- **opencode를 이 예제 폴더에서 실행해야 한다.** `command`의 `server.py`는 opencode를 실행한 폴더 기준이다. (M1 참고)
- 이 DB의 담당자 이름(`dev-a` ...)과 티켓 내용은 모두 연습용 가짜 데이터다.
