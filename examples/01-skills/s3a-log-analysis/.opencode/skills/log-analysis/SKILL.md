---
name: log-analysis
description: 애플리케이션 로그 파일(*.log)을 분석해 에러 급증 구간과 원인 후보를 찾는다. "로그 분석", "에러 급증", "장애 원인 찾아줘", "app.log 봐줘", "타임아웃이 왜 늘었지" 같은 요청에 사용한다. Analyze large application logs, find error spikes and likely causes.
---

# 로그 분석 스킬

로그 파일은 수천~수백만 줄일 수 있다. **로그 전체를 읽거나 `cat`/`read` 로 열지 않는다.**
번들된 스크립트가 파일을 스트리밍으로 훑어서 요약(JSON)만 만들어 준다. 너는 그 요약을 해석한다.

## 1. 스크립트 먼저 실행

이 스킬의 스크립트는 **스킬 디렉터리 기준** `scripts/summarize_log.py` 이다.
스킬을 불러올 때 알려 주는 base directory(스킬 폴더 경로)를 앞에 붙여서 실행한다.

```
python <스킬 폴더>/scripts/summarize_log.py <로그 파일> --window 5m --top 10
```

- 예: 프로젝트 루트에서 `python .opencode/skills/log-analysis/scripts/summarize_log.py logs/app.log --window 5m --top 10`
- `python` 명령이 없는 환경(Linux 등)에서는 `python3` 로 바꿔서 실행한다.
- 셸이 PowerShell(Windows)이든 bash(Linux)이든 같도록 `&&`, `export`, `$변수`, 파이프(`| head`) 없이 **명령 한 줄**만 실행한다. 경로는 `/` 로 써도 된다.
- 출력은 JSON 하나다. 주요 필드: `levels`, `components`, `errors_by_component`, `top_errors`(숫자·ID를 마스킹해 묶은 메시지),
  `spike_rule`, `spike_windows`(에러가 급증한 5분 구간), `incidents`(붙어 있는 급증 구간을 합친 것).
- 종료 코드: 0 = 성공, 2 = 인자 오류·파일 없음·로그 형식 불일치.

## 2. 필요하면 범위를 좁혀 다시 실행

급증 구간을 찾았다면 그 **직전 시간대**와 해당 컴포넌트만 다시 요약해 원인 단서를 찾는다. 같은 스크립트의 옵션을 쓴다.

```
python <스킬 폴더>/scripts/summarize_log.py <로그 파일> --from 2026-11-03T10:30:00 --to 2026-11-03T10:40:00 --sample 15
python <스킬 폴더>/scripts/summarize_log.py <로그 파일> --component db --window 1m
```

`--sample N` 은 WARN/ERROR 원문을 최대 N줄 보여 준다. 원문이 필요할 때도 이 방법만 쓰고, 파일 전체를 열지 않는다.
(에러가 아닌 WARN 이 급증 직전에 먼저 나타나는 경우가 많다. `levels` 에서 WARN 이 눈에 띄면 그 시간대를 확인한다.)

## 3. 해석해서 보고

스크립트 결과에 있는 숫자만 근거로 쓴다. 추측은 추측이라고 표시한다. 아래 형식으로 한국어로 답한다.

1. **한 줄 요약** — 언제부터 언제까지, 어떤 컴포넌트에서, 무슨 에러가 몇 건
2. **타임라인** — 급증 직전 징후 → 급증 시작 → 종료 (시각 포함)
3. **원인 가설** — 가능성 높은 순으로 2~3개. 각각 근거(스크립트 수치)와 반증 가능한 확인 방법
4. **다음 단계** — 바로 확인할 것(대시보드, 설정, 배포 이력), 임시 완화책, 재발 방지 후보
5. **한계** — 이 요약만으로 알 수 없는 것

## 하지 말 것

- 로그 파일 전체를 읽기, 수백 줄을 붙여 넣기
- 스크립트를 고치거나 새로 만들기 (옵션이 부족하면 사용자에게 말한다)
- 요약에 없는 서비스·원인을 사실처럼 단정하기
