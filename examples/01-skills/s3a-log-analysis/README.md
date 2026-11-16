# S3a 로그 분석 스킬 — 스크립트가 요약하고 모델이 해석한다

> 구성: 스킬(SKILL.md + scripts/) | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: 스킬 — 스크립트를 품은 스킬

## 무엇을 보여 주나

스킬은 지침(SKILL.md)만 담는 것이 아니라 **실행 가능한 스크립트를 같은 폴더에 묶어 둘 수 있다.**
이 예제의 스킬은 수천 줄짜리 로그를 모델에게 읽히는 대신, 번들된 `summarize_log.py` 가 로그를 훑어서 작은 JSON 요약으로 줄여 준다.
모델은 그 요약만 보고 장애를 해석한다. "결정적인 일은 코드가, 판단은 모델이" 라는 역할 분담이 핵심이다.

## 실무에서는

- 장애 직후 수십 MB 의 애플리케이션 로그에서 "언제부터, 어디서, 무슨 에러가 늘었는지"를 먼저 잡아야 할 때
- 온콜 인수인계 전에 최근 몇 시간 로그의 에러 분포를 같은 형식으로 요약해 두고 싶을 때
- 팀 공용 서버에서 로그를 모델 컨텍스트로 통째로 올리기 어렵거나 올리면 안 될 때(요약만 모델에게 전달)

## 파일 구성

```
s3a-log-analysis/
├── README.md
├── fake_llm.py                                     # 가짜 모델 서버(m8 예제의 복사본): 실제 모델 없이 스킬 로드 → 스크립트 실행을 검증
├── check.py                                        # 자동 검증
├── prepare.py                                      # logs/app.log 생성 (약 2,000줄, 시드 고정)
├── logs/app.log                                    # prepare.py 가 만든다 (gitignored)
└── .opencode/skills/log-analysis/
    ├── SKILL.md                                    # 언제·어떻게 스크립트를 실행하고 어떻게 보고할지
    └── scripts/summarize_log.py                    # 로그 → JSON 요약 (표준 라이브러리만, 스트리밍)
```

로그에는 `2026-11-03 10:40~10:55` 에 **payment 게이트웨이 타임아웃 급증**이 심어져 있다.
그 5분 전부터 db 커넥션 풀 사용률 경고(WARN)가 먼저 나온다. 에러가 아니라서 급증 목록에는 안 잡히므로, 모델이 "직전 시간대"를 다시 들여다봐야 찾을 수 있다.

## 따라 하기

1. 예제 폴더에서 샘플 로그를 만든다.

   PowerShell:
   ```powershell
   cd examples\01-skills\s3a-log-analysis
   python prepare.py
   ```
   Linux bash:
   ```bash
   cd examples/01-skills/s3a-log-analysis
   python3 prepare.py
   ```

2. 스크립트를 직접 먼저 실행해 본다(모델 없이도 된다). 출력이 어떤 모양인지 보면 3번이 이해된다.

   PowerShell:
   ```powershell
   python .opencode\skills\log-analysis\scripts\summarize_log.py logs\app.log --window 5m --top 10
   ```
   Linux bash:
   ```bash
   python3 .opencode/skills/log-analysis/scripts/summarize_log.py logs/app.log --window 5m --top 10
   ```

3. 이 폴더에서 opencode 를 실행하고 요청한다. 평소 쓰는 모델로 실행하면 됩니다.
   (모델 설정이 없다면 `opencode run -m opencode/big-pickle --auto "<프롬프트>"` 처럼 무료 모델을 쓸 수 있다.)
   ```
   opencode
   ```
   입력할 프롬프트:
   ```
   log-analysis 스킬로 logs/app.log 의 장애 원인을 분석해줘. 파일이 크니까 전체를 읽지는 마.
   ```
   > 스킬 이름을 말하지 않아도 "로그 분석해줘", "에러가 왜 늘었어?" 같은 요청에 스킬이 로드될 수 있지만, 모델에 따라 스킬을 건너뛰고 직접 `grep`/`cat` 하는 경우가 있다.
   > 그럴 때는 위처럼 스킬 이름을 명시한다.

4. 화면에서 `→ Skill "log-analysis"` 줄(스킬 로드)과 `$ python … summarize_log.py …` 줄(스크립트 실행)을 확인한다.

## 기대 결과

**실제 실행 결과** (Linux, 모델 `opencode/big-pickle`, 1회 실행 — 모델 답변은 실행마다 문장이 달라진다). 화면에는 이렇게 나왔다.

```
→ Skill "log-analysis"

$ wc -l logs/app.log
2059 logs/app.log

$ python3 /…/s3a-log-analysis/.opencode/skills/log-analysis/scripts/summarize_log.py logs/app.log --window 5m --top 10
{ …JSON 요약(약 200줄)… }

$ python3 /…/summarize_log.py logs/app.log --from 2026-11-03T10:35:00 --to 2026-11-03T10:55:00 --window 1m --sample 15
$ python3 /…/summarize_log.py logs/app.log --from 2026-11-03T10:35:00 --to 2026-11-03T10:55:00 --component db --window 1m --sample 10
```

최종 답변(앞부분 발췌):

```
1. **한 줄 요약** — `2026-11-03T10:40:00~10:55:00`에 `payment`(81건)·`db`(20건)에서 총 101건 ERROR 급증. 주요 메시지: `payment gateway timeout after <N>ms` 64건, `db connection pool exhausted` 20건, `payment charge failed ... upstream_unavailable` 17건 (`logs/app.log`, 2059줄/2039줄 파싱).

2. **타임라인**
   - **급증 직전 징후 (10:35:22~10:39:11)**: `db` WARN `connection pool usage 82~97% (active 41~49/50)` 다수 관측(10:35~10:55 구간 샘플/집계, db WARN 20건).
   - **급증 시작 (10:40:16~10:40:42)**: `payment charge failed ... upstream_unavailable`(최초 10:40:16), `payment gateway timeout`(최초 10:40:17), `db connection pool exhausted`(최초 10:40:42) 발생.
   - **급증 구간/종료 (10:40:00~10:55:00)**: 5분 윈도우별 ERROR 37/35/29건(임계치 22.12). 마지막 관련 에러 `payment gateway timeout` 10:54:53, `db pool exhausted` 10:54:17.

3. **원인 가설** (가능성 순, 요약 수치 근거)
   - **결제 게이트웨이/업스트림 지연·장애 (유력)**: `payment` 에러 81건 중 timeout 64건·upstream_unavailable 17건이 동일 구간(10:40:16~10:54:53)에 집중. *확인*: 결제 게이트웨이 상태/응답지연·타임아웃 설정·해당 시간대 외부 장애 공지.
   - **DB 커넥션 풀 포화(연쇄/공동 요인 가능)**: 급증 직전부터 pool usage 82~97% WARN 후 10:40:42~10:54:17에 exhausted 20건. 느린 쿼리·트랜잭션 장기 점유 또는 payment 지연 대기 누적으로 풀이 소진됐을 가능성(추측). *확인*: 슬로우쿼리/락, active·waiting 추이, pool 크기·timeout, payment 호출 중 DB 점유 구간.
   - **부하 증가에 따른 자원 경합 (보조 가설)**: 동일 15분 내 incident로 묶일 만큼 에러가 집중됨. *확인*: 10:35~10:55 트래픽/RPS·결제 요청량·배포/설정 변경 이력.

4. **다음 단계**
   - **즉시 확인**: 결제 게이트웨이/외부 연동 모니터링, DB pool(active/waiting)·슬로우쿼리·락 대시보드, 10:35~10:55 배포/설정 변경.
 …
```

모델은 로그를 직접 열지 않고 스크립트를 3번(전체 요약 → 급증 직전~구간 → db 만) 실행했다. 급증 직전의 db 경고(WARN)를 찾아낸 것은 두 번째·세 번째 실행 덕분이다.
스크립트 출력의 핵심 부분(직접 실행해서 확인할 수 있다):

```json
"incidents": [{ "start": "2026-11-03T10:40:00", "end": "2026-11-03T10:55:00", "errors": 101,
  "top_components": [{"name": "payment", "count": 81}, {"name": "db", "count": 20}],
  "top_messages": [{"name": "gateway timeout after <N>ms (order=ORD-<N>)", "count": 64}, …] }]
```

> 모델 확인 상태: Linux 1회 성공(위). **Windows 의 실제 모델 실행은 무료 모델 한도 소진으로 확인하지 못했다.**
> 대신 `check.py` 가 가짜 모델로 "skill 도구 → bash 도구로 `python <스킬 폴더 절대 경로>/scripts/summarize_log.py …`" 흐름을 Linux 와 Windows 에서 검증한다.
> 가짜 모델은 opencode 가 스킬 결과(`Base directory for this skill: …` 포함)와 스크립트 출력(JSON)을 모델에게 돌려주는지를 확인하는 용도이고, 모델이 스스로 그렇게 행동하는지는 보여 주지 않는다.


## 동작 원리

1. **발견** — opencode 는 시작할 때 `.opencode/skills/*/SKILL.md` 의 `name` 과 `description` 만 읽어서 모델에게 "쓸 수 있는 스킬 목록"으로 알려 준다.
   `description` 에 "로그 분석", "장애 원인" 같은 사용자가 실제로 칠 말을 넣어 둔 이유다.
2. **로드** — 모델이 내장 `skill` 도구로 `log-analysis` 를 부르면 SKILL.md 본문이 컨텍스트에 들어온다.
   이때 도구 결과 끝에 **`Base directory for this skill: <스킬 폴더 절대 경로>`** 와 스킬 폴더 안 파일 목록이 함께 붙는다.
3. **실행** — SKILL.md 가 "스킬 폴더 기준 `scripts/summarize_log.py`" 라고 쓰고, 모델은 base directory 를 앞에 붙여 `python3 <절대 경로>/scripts/summarize_log.py logs/app.log …` 를 `bash` 도구로 실행한다.
   스크립트는 스킬 폴더에 있지만 작업 디렉터리(cwd)는 프로젝트 루트 그대로이므로 로그 경로는 프로젝트 기준으로 쓴다.
4. **요약** — 스크립트는 파일을 한 줄씩 스트리밍하며 레벨·컴포넌트별 개수를 세고, 에러 메시지의 숫자·ID 를 `<N>` 으로 바꿔(정규화) 같은 종류끼리 묶고, 5분 창별 에러 수가 `평균 + 2×표준편차` 이상인 구간을 급증으로 표시한다. 결과는 JSON 한 덩어리(약 200줄)다.
5. **해석** — 모델은 JSON 만 보고 SKILL.md 의 보고 형식(요약 → 타임라인 → 가설 → 다음 단계 → 한계)대로 답한다.
   필요하면 `--from/--to/--component/--sample` 로 같은 스크립트를 좁혀서 다시 실행한다.

왜 스크립트로 빼는가: 로그를 모델이 직접 읽으면 토큰이 크게 들고, 매번 세는 방식이 달라져 숫자가 흔들린다.
스크립트는 같은 입력에 항상 같은 숫자를 낸다. 모델은 숫자를 새로 계산하지 않고 설명만 한다.

## 직접 바꿔 보기

1. **창 크기 바꾸기**: `--window 1m` 으로 실행해 보고 급증 구간이 어떻게 달라지는지 본다. SKILL.md 의 명령 예시도 바꿔 보고 모델이 따르는지 확인한다.
2. **새 규칙 넣기**: `summarize_log.py` 의 `MASKS` 에 마스킹 규칙(예: `user=u1234` 의 사용자 ID)을 추가해 `top_errors` 가 어떻게 묶이는지 본다.
3. **다른 로그로**: 자신의 서비스 로그 한 줄 형식이 다르면 `LINE_RE` 한 줄만 고치면 된다. 줄 형식이 안 맞으면 종료 코드 2 와 안내 메시지가 나온다.

## 주의할 점 / 문제 해결

- **Windows 에서는 `python`, Linux 에서는 `python3`**: SKILL.md 는 `python` 으로 안내하고 "없으면 `python3`" 를 덧붙였다. Windows 에서 opencode 의 `bash` 도구는 Git Bash 가 아니라 **Windows PowerShell 5.1** 에서 명령을 실행한다. 그래서 SKILL.md 는 `&&`, `export`, `$변수`, `| head` 같은 bash 전용 문법 없이 `python <스킬 폴더>/scripts/… 인자` **한 줄**만 시킨다. 스킬 폴더 경로는 Windows 에서 `C:\...\.opencode\skills\<이름>` 처럼 역슬래시로 오지만, 파이썬에는 `/` 로 바꿔 넘겨도 동작한다(`check.py` 가 가짜 모델로 검증).
- **스킬이 안 불리면**: 프롬프트에 스킬 이름을 넣는다. `opencode debug skill` 로 스킬이 발견되는지(이름·description) 먼저 확인한다.
- **첫 실행의 `@opencode-ai/plugin` 설치 시도.** `.opencode/`가 있는 폴더에서는 opencode가 시작할 때 `@opencode-ai/plugin`을 npm에서 설치하려 시도하고, 성공하면 `.opencode/` 안에 `package.json`, `node_modules/`, `.gitignore`가 생긴다(모두 git에서 제외). 이 예제는 그 패키지를 쓰지 않고 플러그인도 없어서(`.opencode/plugins/*.js`)이 없어서, 레지스트리에 닿지 않는 환경에서도 눈에 띄는 멈춤은 없었다(연결을 거부하는 레지스트리로 측정: `opencode debug skill` 약 2초, `opencode run` 약 4초. TUI는 확인하지 못했다). 설치 시도 자체는 일어난다. 같은 환경에서 `.opencode/plugins/*.js`가 있는 폴더(P1~P8 등)는 시작할 때마다 약 70초 멈춘다(새 환경의 맨 처음 시작은 약 130초). 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있다.
- **인코딩**: 스크립트는 파일을 UTF-8 로 열고 stdout 을 UTF-8 로 고정한다(Windows 기본 cp949 대비). 로그가 다른 인코딩이면 깨진 글자는 대체 문자로 읽는다.
- `logs/` 는 gitignore 대상이다. `prepare.py` 를 다시 실행하면 같은 내용으로 다시 만든다.
