# P3 감사 로그 플러그인 (audit-log)

> 구성: 플러그인(JS) `tool.execute.after` + 요약 스크립트(Python) | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ (Node 는 단위 테스트에만) | 슬라이드: 플러그인 — 도구 실행 기록

## 무엇을 보여 주나

`tool.execute.after` 훅은 도구 실행이 **끝난 뒤**에 호출되어, 어떤 도구가 어떤 인자로 실행됐고 결과가 얼마나 컸는지 알려 줍니다.
이 예제는 그 정보를 `logs/audit.jsonl` 에 한 줄(JSON)씩 쌓고, `summarize_audit.py` 가 "무엇을 몇 번 했는지"와 시간순 타임라인으로 요약합니다.
에이전트가 자리를 비운 사이에 한 일을 사후에 확인하는 가장 기본적인 방법입니다.

## 실무에서는

- `--auto` 로 오래 돌린 작업이 끝난 뒤 "그동안 어떤 파일을 읽고 어떤 명령을 실행했는가"를 5분 안에 훑어볼 수 있습니다.
- 팀에서 에이전트를 도입할 때 "어떤 도구를 많이 쓰는가", "bash 로 무엇을 하는가"를 보고 권한 정책(`permission`)을 정하는 근거로 씁니다.
- 사고가 났을 때 "언제, 어느 세션이, 어느 파일을 건드렸는가"를 되짚는 자료가 됩니다.

## 파일 구성

```
p3-audit-log/
├── README.md
├── fake_llm.py                       # 검증용 가짜 LLM (표준 라이브러리만, 복사본)
├── check.py                            # 자동 검증 (단위 테스트 + 요약 스크립트 + 플러그인 로드 + --model)
├── notes.txt                           # 모델 시험용 파일 (내용이 로그에 남지 않는지 확인하는 표식 포함)
├── summarize_audit.py                  # audit.jsonl 요약: 도구별 횟수 + 타임라인
├── .opencode/plugins/audit-log.js      # 플러그인 본체 (기록, 가림, 로테이션)
├── tests/audit.test.mjs                # 훅을 직접 호출하는 시험 (node)
└── logs/                               # 실행하면 생김: plugin-load.log, audit.jsonl, audit.<시각>.jsonl
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. (모델 설정이 없다면 무료 모델 `-m opencode/big-pickle` 을 붙이세요.)

1. 이 폴더에서 opencode 를 실행합니다. 처음 실행하면 opencode 가 `.opencode/` 안에 `@opencode-ai/plugin` 을 npm 으로 설치하려고 합니다. 인터넷이 막혀 있고 패키지 미러도 없으면 첫 시작이 70초쯤 멈췄다가 계속 진행됩니다. 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다.

   PowerShell:
   ```powershell
   cd examples\03-plugins\p3-audit-log
   opencode
   ```
   Linux bash:
   ```bash
   cd examples/03-plugins/p3-audit-log
   opencode
   ```

2. 아래처럼 시킵니다.

   - `notes.txt 를 읽고 한 줄로 요약해 줘. 그다음 bash 로 echo audit-demo 를 실행해 줘.`

3. 종료한 뒤 요약을 봅니다. (Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요.)

   ```
   python summarize_audit.py
   ```
   원본 JSONL 도 직접 열어 보세요: PowerShell `Get-Content logs\audit.jsonl`, Linux bash `cat logs/audit.jsonl`

4. 옵션: `--tool bash`(특정 도구만 타임라인에 표시), `--session <ID>`(세션별), `--all`(로테이션된 파일까지).

5. 자동 검증: `python check.py` / `python check.py --model`.

## 기대 결과

아래 출력은 `check.py` 가 쓰는 **가짜 LLM**(`fake_llm.py`: 정해진 도구 호출을 대신 수행하는 OpenAI 호환 서버, 표준 라이브러리만 사용)으로 실제 `opencode 1.19.5` 를 실행해 얻은 것입니다. 모델이 무엇을 시키든 플러그인이 어떻게 반응하는지를 매번 똑같이 재현할 수 있습니다. 실제 모델(무료 모델)로는 이번 확인 시점에 한도 초과/시간 초과로 결과를 얻지 못해 **미검증**입니다. 평소 쓰는 모델로 해 보면 모델의 말투와 시도 순서는 다르겠지만 차단/기록 동작은 같아야 합니다.

가짜 LLM 이 `notes.txt` 읽기 → `echo audit-demo` → 새 파일 쓰기를 시도했을 때(Linux) `logs/audit.jsonl`:

```
{"ts":"2026-11-16T17:10:22.875Z","sessionID":"ses_e1aa9635bffenxGiKalUL4x22p","tool":"read","args":{"filePath":"/…/p3-audit-log/notes.txt"},"title":"examples/03-plugins/p3-audit-log/notes.txt","outputLength":237}
{"ts":"2026-11-16T17:10:23.059Z","sessionID":"ses_e1aa9635bffenxGiKalUL4x22p","tool":"bash","args":{"command":"echo audit-demo","description":"demo"},"title":"echo audit-demo","outputLength":11}
{"ts":"2026-11-16T17:10:23.190Z","sessionID":"ses_e1aa9635bffenxGiKalUL4x22p","tool":"write","args":{"filePath":"/…/p3-audit-log/logs/scratch.txt","content":"<23자 생략>"},"title":"examples/03-plugins/p3-audit-log/logs/scratch.txt","outputLength":24}
```

`notes.txt` 의 내용(`SENTINEL-CONTENT-4242`)은 모델에게는 전달됐지만 로그에는 없고, `write` 의 본문은 `<23자 생략>` 으로 길이만 남았습니다.

`python summarize_audit.py`:

```
기록 3건 · 세션 1개 · 파일 1개

도구별 호출 횟수
  read            1  #
  bash            1  #
  write           1  #

타임라인
  02:10:22  L4x22p  read        /…/p3-audit-log/notes.txt  [출력 237자]
  02:10:23  L4x22p  bash        echo audit-demo  [출력 11자]
  02:10:23  L4x22p  write       /…/p3-audit-log/logs/scratch.txt  [출력 24자]
```

## 동작 원리

1. `tool.execute.after(input, output)` 의 입력은 이렇게 생겼습니다 (1.19.5 에서 관찰).

   | 위치 | 내용 |
   |---|---|
   | `input` | `tool`(도구 이름), `sessionID`, `callID`, `args`(실행에 쓴 인자) |
   | `output` | `title`(예: bash 는 명령 자체, read 는 상대 경로), `output`(도구가 돌려준 본문 문자열), `metadata` |

   이 훅은 도구가 성공적으로 끝난 뒤에 불리고, `tool.execute.before` 에서 throw 되어 막힌 호출은 기록되지 않습니다. (차단 기록은 p1·p2 처럼 `before` 에서 직접 남겨야 합니다.)
2. 플러그인은 한 호출을 이런 JSON 한 줄로 만듭니다: `ts`(UTC ISO 시각), `sessionID`, `tool`, `args`(요약), `title`, `outputLength`.
3. **인자 요약 규칙** (`summarizeValue`)
   - 경로(`filePath`, `path` …)는 그대로 둡니다. 감사에는 "어느 파일"이 가장 중요하기 때문입니다.
   - `bash` 의 `command` 는 300자, 그 밖의 문자열은 120자에서 자르고 `…(+N자)` 를 붙입니다.
   - `content`, `oldString`, `newString`, `patchText` 같은 **내용**은 `<N자 생략>` 으로 길이만 남깁니다.
   - 도구 출력 본문(`output.output`)은 길이(`outputLength`)만 남기고 저장하지 않습니다.
4. 기록은 `appendFileSync` 로 한 줄씩 추가합니다. JSONL 은 한 줄이 한 레코드라서 프로세스가 중간에 끊겨도 앞 줄은 멀쩡하고, `grep`·`jq`·Python 으로 바로 처리할 수 있습니다.
5. 훅 안의 모든 작업은 `try/catch` 로 감쌉니다. **감사 로그 실패가 에이전트 작업을 멈추게 해서는 안 되기** 때문입니다.
6. `summarize_audit.py` 는 파일을 읽어 `Counter` 로 도구별 횟수를 세고, 시각순으로 정렬해 로컬 시각 타임라인을 출력합니다. 깨진 줄은 건너뛰고 개수만 알려 줍니다.

### 개인정보와 비밀 (꼭 읽으세요)

- **파일 내용과 출력 본문을 로그에 남기지 않는 것이 기본입니다.** 내용을 남기기 시작하면 감사 로그가 `.env` 보다 더 위험한 비밀 저장소가 됩니다. 그래서 `write`/`edit` 의 본문은 길이만, 도구 출력은 길이만 남깁니다.
- `command` 안에 들어간 비밀은 별도로 가립니다: `Bearer <값>`, `password=<값>`, `--token <값>`, `api_key=<값>`, `postgres://사용자:비밀번호@호스트` 의 비밀번호 부분이 `***` 로 바뀝니다. 다만 정규식 기반이라 **모든 비밀을 잡는다고 보장할 수 없습니다.** 프롬프트에 비밀을 직접 적는 습관 자체를 피하세요.
- 경로와 명령에는 사용자 이름, 프로젝트 이름 같은 정보가 들어 있을 수 있습니다. 로그를 외부에 공유하기 전에 한 번 훑어보세요.
- `logs/` 는 `.gitignore` 에 있어 커밋되지 않습니다. 팀 서버에서 쓴다면 로그 폴더 권한을 소유자만 읽도록 제한하세요.

### 로테이션 (파일이 계속 커지지 않게)

- 플러그인이 기록할 때마다 `audit.jsonl` 의 크기를 보고, `AUDIT_MAX_BYTES`(기본 1 MiB)를 넘으면 `audit.<yyyymmdd-hhmmss>.jsonl` 로 이름을 바꾸고 새 파일을 시작합니다.
- 이전 파일은 최근 `AUDIT_KEEP`개(기본 5)만 남기고 지웁니다.
- 환경변수로 조절합니다. PowerShell: `$env:AUDIT_MAX_BYTES = 200000; opencode` / Linux bash: `AUDIT_MAX_BYTES=200000 opencode`
- 더 오래 보관해야 하면 로테이션 파일을 압축해 다른 곳으로 옮기는 작업(예: 하루 한 번 스케줄러)을 따로 두세요. 플러그인은 압축·업로드를 하지 않습니다.
- 이 예제의 로테이션은 한 번에 opencode 프로세스 하나가 쓴다고 가정합니다. 같은 폴더에서 여러 개를 동시에 돌리면 줄이 섞이거나 이름이 겹칠 수 있습니다.

## 직접 바꿔 보기

1. `AUDIT_MAX_BYTES=2000` 으로 낮춰서 몇 번 작업시킨 뒤 `logs/` 에 `audit.<시각>.jsonl` 이 생기는지, `python summarize_audit.py --all` 이 이전 파일까지 합쳐 보여 주는지 확인해 보세요.
2. `summarizeValue` 에서 `url` 키의 쿼리스트링(`?` 뒤)을 잘라 내도록 바꿔 보세요. 감사 로그에 토큰이 URL 로 들어가는 것을 막는 방법입니다.
3. `record` 에 `durationMs` 를 추가해 보세요. `tool.execute.before` 에서 `callID` 별 시작 시각을 `Map` 에 저장해 두면 됩니다.

## 주의할 점 / 문제 해결

- **export 는 플러그인 함수만 하세요.** 상수나 보조 함수를 export 하면 opencode 가 그것도 플러그인으로 호출하다가 오류 메시지 없이 파일 전체를 건너뜁니다. 그래서 요약 함수는 export 하지 않고, 테스트는 훅을 직접 호출합니다.
- 기록 파일은 **opencode 를 실행한 폴더** 기준 `logs/` 입니다 (플러그인이 받는 `directory` 값). 다른 폴더에서 실행하면 그 폴더에 `logs/` 가 생깁니다.
- 시각은 UTC(`2026-…Z`)로 저장되고, `summarize_audit.py` 가 로컬 시각으로 바꿔 보여 줍니다.
- 하위 에이전트(`task` 도구)가 쓴 도구 호출도 같은 훅으로 들어오는지는 이번에 확인하지 않았습니다.
- `node` 가 없으면 `check.py` 가 경고(WARN)를 내고 단위 테스트를 건너뜁니다. opencode 실행에는 Node 가 필요 없습니다.
