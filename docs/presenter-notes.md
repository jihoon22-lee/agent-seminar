# 발표 준비 메모

발표자가 세미나 전에 한 번 읽고 따라 하는 문서입니다. 발표 시간은 60분(질문 5분 포함)이고, 데모는 여섯 개입니다(설정 1, 스킬 1, MCP 2, 플러그인 1, 종합 1).

## 전날: 데모 환경 만들기

1. **opencode 버전 확인**: `opencode --version` 이 `1.19.5` 인지 봅니다. 다르면 설정 형식이 달라 데모가 깨질 수 있습니다.
   발표 전날부터는 자동 업데이트를 꺼 두세요. 셸에 `OPENCODE_DISABLE_AUTOUPDATE=1` 을 설정하거나 전역 설정에 `"autoupdate": false` 를 넣으면 됩니다.
2. **npm 미러 지정**: 인터넷이 막힌 PC라면 검사보다 먼저 합니다. `.opencode/` 폴더가 있는 예제는 시작할 때 opencode가 npm 패키지 `@opencode-ai/plugin`을 설치하려 합니다.
   레지스트리에 닿지 않으면 플러그인이 있는 폴더는 **시작할 때마다** 약 70초(새 환경의 첫 시작은 약 130초) 멈추고, 이 패키지를 쓰는 플러그인 도구(P6, X1-c)는 조용히 사라집니다.
   ```powershell
   npm config set registry https://<패키지 미러 주소>/    # %USERPROFILE%\.npmrc 에 저장되고 opencode가 그대로 씁니다
   ```
3. **예제 검사**: 레포 루트에서 아래 명령을 실행합니다. 모두 `OK` 여야 합니다. 20분쯤 걸립니다.
   ```powershell
   python tools\run_checks.py examples
   ```
4. **데모 폴더 예열**: 데모할 폴더마다 준비 스크립트를 돌리고 `opencode debug skill` 을 한 번 실행해 npm 설치를 끝내 둡니다. 설치가 끝나면 다음부터는 1초 안팎으로 뜹니다.
   - `examples\00-config\c1-scope-merge` (`python demo.py` 를 한 번 실행)
   - `examples\01-skills\s1a-commit-message`: `python prepare.py` 후 `cd sandbox` 에서 실행 (데모도 `sandbox` 안에서 합니다)
   - `examples\02-mcp\m1-stdio-minimal`
   - `examples\02-mcp\m4-remote-http` (서버는 데모 때 터미널 1에서 띄웁니다)
   - `examples\03-plugins\p1-env-guard` (먼저 `python prepare.py`)
   - `examples\04-combined\x2-incident-analysis` (먼저 `python prepare.py`)
   - 시간이 남을 때 할 심화 데모: `examples\01-skills\s3a-log-analysis`, `examples\02-mcp\m6-sqlite-tickets` (둘 다 먼저 `python prepare.py`)
5. **모델 확인**: 데모에 쓸 모델로 짧은 질문을 하나 해 봅니다. 응답이 없으면 아래 "모델이 멈출 때"를 보세요.

## 당일: 화면 배치

- 발표 자료: https://jihoon22-lee.github.io/agent-seminar/ 를 열고 `F` 로 전체 화면. 인터넷이 없으면 레포에서 로컬 웹 서버로 띄웁니다: `cd slides` 후 `python -m http.server 8000`, 브라우저에서 `http://127.0.0.1:8000`. (`index.html` 을 파일로 직접 열어도 슬라이드는 보이지만, 발표자 창 동기화는 웹 서버로 열었을 때만 확인했습니다.)
- 발표자 창: `P` 를 누르면 새 창에 메모, 다음 슬라이드, 경과 시간이 나옵니다. 이 창을 노트북 화면에 두고, 발표 화면에는 원래 창을 띄웁니다. 시계를 누르면 0부터 다시 잽니다.
- 터미널: 글자 크기를 크게(20pt 이상) 하고, 데모 폴더별로 탭을 미리 열어 둡니다.
- 데모 슬라이드(어두운 배경)에 적힌 명령이 그대로 실행할 명령입니다.

## 60분에 맞추기: 짧은 버전

슬라이드는 혼자 읽어도 이해되도록 자세하게 만들었습니다. 그대로 다 넘기면 60분을 넘습니다.
발표할 때는 슬라이드 화면에서 `S` 를 눌러 **짧은 버전**을 켜세요. 오른쪽 위에 "심화"라고 표시된 슬라이드(S1b, S1c, S2a, S2c, S3b–S4b, S3a 데모, S5c, M1 도구 설명, M3, M5, M6 데모, M7, M9, P4–P8, X2 transcript 등과 부록, 모두 32장)를 건너뛰며 넘어갑니다.
발표자 창도 같은 설정을 따르고, 다음 슬라이드 미리보기도 건너뛴 다음 장을 보여 줍니다. 숫자 + `Enter` 로 이동하면 심화 슬라이드도 열 수 있습니다. 질문에 답할 때 쓰세요.
다시 `S` 를 누르면 전체 버전으로 돌아갑니다. 설정은 브라우저에 저장되므로 발표 전에 한 번 켜 두면 됩니다.

## 시간 배분

짧은 버전(`S`)을 켰을 때 기준입니다. 질문 시간 5분을 따로 남겨 두었습니다.

| 장 | 시간 | 데모 |
|---|---|---|
| 들어가며 | 4분 | |
| 개념 | 9분 | |
| opencode.json | 7분 | C1 설정 병합 (`python demo.py`) |
| 스킬 | 10분 | S1a 커밋 메시지 |
| MCP | 11분 | M1 표준 라이브러리 서버, M4 원격 |
| 플러그인 | 7분 | P1 .env 차단 |
| 종합과 마무리 | 7분 | X2 장애 분석 |
| 질문 | 5분 | |

데모가 늦어지면 M4 데모를 슬라이드로 대신합니다(앞 장 "M4 원격 서버"에 실제 결과가 있습니다). 다른 데모도 각 예제 README의 "기대 결과"에 실제 실행 결과가 있으니 그 화면을 보여 줘도 됩니다.
시간이 남으면 숫자 + `Enter` 로 심화 데모(S3a 로그 분석, M6 SQLite)를 엽니다.

## 모델이 멈출 때

- 화면에 아무것도 나오지 않고 멈추면 `Ctrl+C` 후 `opencode run --print-logs --log-level ERROR "안녕"` 으로 오류를 봅니다.
  무료 모델은 `Free usage limit reached` 가 나오면 한도가 찬 것입니다. 다른 모델로 바꾸거나, 미리 준비한 결과(각 예제 README의 "기대 결과")를 보여 줍니다.
- `opencode run` 이 입력을 기다리며 멈춘 것처럼 보이면, 파이프로 입력을 넘기지 않았는지 확인합니다.
- 스킬이 불리지 않으면 프롬프트에 스킬 이름을 넣습니다. 예: `log-analysis 스킬로 logs/app.log 를 분석해줘`.

## 질문이 나오면

맨 끝의 부록 장에 문제 해결 표, 확인 명령 모음, 버전 차이, 참고 자료가 있습니다. 슬라이드 번호를 누르고 `Enter` 를 치면 바로 이동합니다.
