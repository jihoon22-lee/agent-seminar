---
name: html-report
description: CSV 데이터로 브라우저에서 바로 열리는 단일 HTML 리포트(요약 표 + 막대·선 그래프)를 만들고 인사이트를 요약한다. "HTML 리포트 만들어줘", "매출 리포트", "CSV 시각화", "데이터 보고서", "그래프로 보여줘" 같은 요청에 사용한다. Build a self-contained HTML report from CSV data.
---

# HTML 리포트 스킬

표 계산·차트 그리기는 번들된 스크립트가 결정적으로 처리한다(외부 CDN·JS 라이브러리 없음, 파이썬 표준 라이브러리만 사용).
HTML 은 `templates/report.html` 틀에 스크립트가 만든 표와 SVG 그래프를 채워서 만든다. **HTML 을 직접 쓰거나 고치지 않는다.**

## 1. 리포트 만들기

스크립트는 **스킬 디렉터리 기준** `scripts/build_report.py` 이다.
스킬을 불러올 때 알려 주는 base directory(스킬 폴더 경로)를 앞에 붙이고, **프로젝트 루트에서** 실행한다.

```
python <스킬 폴더>/scripts/build_report.py data/sales.csv --out out/report.html
```

- 예: `python .opencode/skills/html-report/scripts/build_report.py data/sales.csv --out out/report.html`
- `python` 명령이 없는 환경(Linux 등)에서는 `python3` 로 바꿔서 실행한다.
- 셸이 PowerShell(Windows)이든 bash(Linux)이든 같도록 `&&`, `export`, `$변수`, 파이프(`| head`) 없이 **명령 한 줄**만 실행한다. 경로는 `/` 로 써도 된다.
- CSV 는 UTF-8, 헤더 `month,region,units,revenue` (month 는 `YYYY-MM`). 다른 열 구성이면 사용자에게 알리고, 스크립트를 고치지 않는다.
- 성공하면 종료 코드 0 과 함께 JSON 요약이 stdout 으로 나온다. 종료 코드 2 는 입력 오류(열 누락, 숫자가 아닌 값 등)이다. 오류 메시지를 그대로 전달한다.
- 요약 JSON 의 주요 필드: `output_absolute`(만들어진 파일 절대 경로), `total_revenue`, `best_month`, `worst_month`,
  `biggest_mom_increase/decrease`(전월 대비 최대 증감), `regions_detail`(지역별 비중, 하반기/상반기 증감률, `dip_months`).

## 2. 인사이트 3가지 정리

JSON 요약에 있는 숫자만 근거로 한국어로 **정확히 3가지** 쓴다. 각 인사이트는 "무슨 일이 있었나 → 숫자 → 해볼 만한 확인/조치" 한 문단(2~3문장)이다.
데이터에 없는 원인은 단정하지 말고 "가능한 원인"으로 표시한다. (예: 특정 달 급증 → 행사·계절 요인 가능성, 확인 필요)

## 3. 마무리 안내

답변 마지막에 다음을 반드시 적는다.

- 브라우저에서 열 파일: `output_absolute` 의 절대 경로 (Windows 는 탐색기에서 더블클릭, 또는 `start out\report.html`, Linux 는 `xdg-open out/report.html`)
- 다시 만들려면 같은 명령을 다시 실행하면 된다는 것 (같은 이름으로 덮어쓴다)

## 하지 말 것

- 생성된 HTML 을 통째로 출력하거나 읽어서 붙여 넣기 (수치는 JSON 요약을 쓴다)
- 외부 라이브러리·CDN 링크를 넣도록 템플릿 바꾸기
