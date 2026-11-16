# S4a HTML 리포트 스킬 — 템플릿 + 스크립트로 산출물을 만든다

> 구성: 스킬(SKILL.md + scripts/ + templates/) | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, 웹 브라우저 | 슬라이드: 스킬 — 산출물을 만드는 스킬

## 무엇을 보여 주나

스킬이 만드는 결과물은 텍스트 답변만이 아니다. 이 스킬은 CSV 를 읽어 **브라우저에서 더블클릭만으로 열리는 HTML 파일**을 만든다.
틀(`templates/report.html`)과 계산·SVG 그래프 생성(`build_report.py`)이 스킬 폴더에 같이 있고, 모델은 스크립트를 실행한 뒤 숫자를 근거로 **인사이트 3가지를 요약**한다.
산출물은 외부 자원이 없다(CDN·JS 라이브러리·웹 폰트 없음, 그래프는 파이썬이 만든 인라인 SVG).

## 실무에서는

- 주간·월간 지표(매출, 사용량, 오류율) CSV 를 매번 같은 모양의 보고서로 뽑아 메신저나 메일로 공유
- 인터넷이 막힌 환경이나 팀 공용 서버에서, 설치할 것 없이 HTML 파일 하나로 결과를 전달
- 분석 결과를 "파일(산출물) + 한 문단 해설" 한 쌍으로 남겨 다음 달에 같은 명령으로 재생성

## 파일 구성

```
s4a-html-report/
├── README.md
├── fake_llm.py                                     # 가짜 모델 서버(m8 예제의 복사본): 실제 모델 없이 스킬 로드 → 스크립트 실행을 검증
├── check.py                                        # 자동 검증 (외부 리소스 없는지, 심어 둔 하락 구간 탐지 등)
├── data/sales.csv                                  # 합성 데이터: 2025년 12개월 x 지역 3곳 (36행)
├── out/report.html                                 # 생성 결과 (gitignored)
└── .opencode/skills/html-report/
    ├── SKILL.md                                    # 실행 명령, 인사이트 3가지 작성 규칙, 안내 문구
    ├── scripts/build_report.py                     # CSV → 집계 → SVG 차트 → 템플릿 채우기
    └── templates/report.html                       # HTML/CSS 틀 ({{title}}, {{kpis}}, {{chart}}, {{table}} 자리표시)
```

`data/sales.csv` 에는 알아볼 만한 패턴이 들어 있다: 11월 매출 급증, 부산의 7~9월 하락, 광주의 꾸준한 성장.

## 완성된 리포트는 이렇게 생겼다

(스크린샷 없이 설명) 페이지 맨 위에 제목 "월별 판매 리포트"와 원본 파일명·행 수가 있다. 그 아래 카드 4개가 가로로 놓인다:
총 매출, 총 판매 수량, 월 평균 매출, 최고 매출 월(2025-11). 다음 카드에는 **월별 그래프**가 있다 — 파란 막대가 월별 매출(왼쪽 축, 백만원),
주황색 선이 월별 판매 수량(오른쪽 축, 개)이고, 막대·점 위에 마우스를 올리면 값이 툴팁으로 뜬다. 3~8월은 비슷한 높이로 잔잔하다가
9월부터 오르고 11월에 가장 높다. 마지막 카드는 지역별 요약 표(지역, 매출, 수량, 매출 비중, 하반기/상반기 증감)와 합계 줄이다.
OS 가 다크 모드이면 배경·글자색이 어두운 테마로 바뀐다. 폭이 좁으면(휴대폰) 카드가 2열로 접힌다.

## 따라 하기

1. (선택) 스크립트를 먼저 직접 실행해 본다.

   PowerShell:
   ```powershell
   cd examples\01-skills\s4a-html-report
   python .opencode\skills\html-report\scripts\build_report.py data\sales.csv --out out\report.html
   start out\report.html
   ```
   Linux bash:
   ```bash
   cd examples/01-skills/s4a-html-report
   python3 .opencode/skills/html-report/scripts/build_report.py data/sales.csv --out out/report.html
   xdg-open out/report.html   # 원격 서버면 파일을 내려받아 로컬 브라우저로 연다
   ```

2. 이 폴더에서 opencode 를 실행한다. 평소 쓰는 모델로 실행하면 됩니다.
   (모델 설정이 없다면 `opencode run -m opencode/big-pickle --auto "<프롬프트>"` 처럼 무료 모델을 쓸 수 있다.)
   ```
   opencode
   ```
   입력할 프롬프트:
   ```
   html-report 스킬로 data/sales.csv 의 HTML 리포트를 만들어 줘. 인사이트 3가지도 요약해 줘.
   ```

3. 답변 끝에 나온 `out/report.html` 경로를 브라우저로 연다.

## 기대 결과

스크립트를 직접 실행하면 stdout 에 JSON 요약이 나오고 `out/report.html`(약 9 KB)이 만들어진다. 모델이 받는 근거 숫자는 다음과 같다(발췌).

```
output_absolute: …/s4a-html-report/out/report.html
total_revenue: 67,639,000원   total_units: 2,822
best_month: 2025-11 (8,021,000원)   biggest_mom_increase: 2025-11 +23.2%   biggest_mom_decrease: 2025-12 -8.7%
서울  비중 54.7%  하반기/상반기 +24.2%
부산  비중 26.2%  하반기/상반기 +4.0%   dip_months: 2025-07, 2025-08, 2025-09
광주  비중 19.1%  하반기/상반기 +46.2%
```

이 숫자에서 나올 만한 인사이트 예: ① 11월 매출이 전월 대비 23.2% 늘어 연중 최고(행사·계절 요인 가능성), ② 부산은 7~9월 하락 후 회복되어 하반기 증가율이 4.0% 에 그침(하락 원인 확인 필요), ③ 광주는 비중은 19.1% 로 작지만 하반기 +46.2% 로 가장 빠르게 성장. 리포트 화면의 모양은 위 "완성된 리포트는 이렇게 생겼다"를 참고한다. (위 인사이트는 숫자에서 뽑은 예시이며 실제 모델 출력이 아니다.)

> 모델 확인 상태: 이 예제의 **실제 모델 실행은 확인하지 못했다**(무료 모델 한도 소진). 위 출력은 모델 없이 스크립트를 직접 실행한 결과이고, 모델은 이 결과를 받아 SKILL.md 의 보고 형식대로 한국어 답변을 쓰게 된다. `check.py` 는 가짜 모델로 "skill 도구 → bash 도구로 스크립트 실행" 흐름이 Linux 와 Windows 에서 동작함을 검증한다.


## 동작 원리

1. 스킬을 로드하면 SKILL.md 뒤에 `Base directory for this skill: <절대 경로>` 와 스킬 폴더의 파일 목록(`scripts/…`, `templates/…`)이 붙는다.
2. 모델은 base directory + `scripts/build_report.py data/sales.csv --out out/report.html` 를 **프로젝트 루트**에서 실행한다. 입력(`data/`)과 출력(`out/`)은 프로젝트 기준 경로, 스크립트와 템플릿은 스킬 폴더 기준이다.
   스크립트는 템플릿 위치를 자기 위치(`Path(__file__)`)에서 찾기 때문에 어느 디렉터리에서 실행해도 틀을 찾는다.
3. 스크립트가 월별·지역별로 집계하고, 막대·선 SVG 를 직접 문자열로 만들어 `{{chart}}` 자리에 넣는다. 사용자 데이터는 `html.escape` 로 이스케이프한다.
4. stdout 의 JSON 요약(최고·최저 월, 전월 대비 증감, 지역별 비중과 하락 구간)이 모델에게 주는 근거 숫자다. 모델은 HTML 을 읽지 않고 이 JSON 으로 인사이트 3가지를 쓴다.
5. 같은 입력이면 같은 HTML 이 나온다(푸터의 생성 시각만 다르다). 모델이 HTML 을 직접 쓰지 않으므로 숫자가 틀리거나 형식이 흔들릴 일이 적다.

## 직접 바꿔 보기

1. `templates/report.html` 의 CSS 변수(`--bar`, `--trend`)로 색을 바꾸고 다시 생성해 본다. 스크립트는 그대로이고 모양만 달라진다.
2. `data/sales.csv` 에 지역을 한 곳 추가하거나 13번째 달을 넣고 재생성한다. 표와 그래프가 따라서 늘어난다.
3. `build_report.py` 의 `chart_svg()` 에서 선 그래프를 "수량" 대신 "3개월 이동 평균 매출"로 바꿔 본다.

## 주의할 점 / 문제 해결

- **CSV 형식**: UTF-8, 헤더 `month,region,units,revenue`. 열이 빠지거나 숫자가 아니면 종료 코드 2 와 `error: line N: …` 가 나온다. 엑셀에서 저장한 CSV 는 BOM 이 있어도 읽는다.
- **한글 글꼴**: HTML 은 `Malgun Gothic`(Windows), `Apple SD Gothic Neo`(macOS), `Noto Sans CJK KR`(Linux) 순으로 쓴다. 한글 글꼴이 없는 서버 화면에서는 글자가 깨져 보일 수 있다.
- **원격 서버에서 만든 경우** 브라우저가 서버에 없으므로 `out/report.html` 을 내려받아 연다. 파일 하나로 완결되므로 메일 첨부나 메신저 전송도 된다.
- **Windows 에서는 `python`, Linux 에서는 `python3`**: SKILL.md 는 `python` 으로 안내하고 "없으면 `python3`" 를 덧붙였다. Windows 에서 opencode 의 `bash` 도구는 Git Bash 가 아니라 **Windows PowerShell 5.1** 에서 명령을 실행한다. 그래서 SKILL.md 는 `&&`, `export`, `$변수`, `| head` 같은 bash 전용 문법 없이 `python <스킬 폴더>/scripts/… 인자` **한 줄**만 시킨다. 스킬 폴더 경로는 Windows 에서 `C:\...\.opencode\skills\<이름>` 처럼 역슬래시로 오지만, 파이썬에는 `/` 로 바꿔 넘겨도 동작한다(`check.py` 가 가짜 모델로 검증). 경로 구분자는 어느 쪽이든 스크립트가 `pathlib` 로 처리한다.
- `out/` 은 gitignore 대상이다. 첫 실행 지연(`.opencode/` 의 `@opencode-ai/plugin` 자동 설치 시도)은 S3a 와 같다. 이 예제에도 플러그인이 없어 레지스트리에 닿지 않아도 눈에 띄는 멈춤은 없었다. 자세한 내용은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러) 참고.
