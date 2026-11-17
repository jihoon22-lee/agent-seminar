# P9 파일을 고친 직후 포맷하고, 검사 결과를 모델에게 돌려주기 (format-on-save)

> 구성: 설정 `formatter` + 플러그인(JS) `tool.execute.after` | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+ (Node 는 단위 테스트에만) | 슬라이드: 플러그인 — 도구 결과 가공

## 무엇을 보여 주나

에이전트가 `write`/`edit` 로 파일을 고친 직후에 할 수 있는 일은 두 가지이고, 서로 하는 일이 다릅니다.

- **Part A, 내장 `formatter` (설정만)**: `opencode.json` 의 `formatter` 키에 명령을 적으면 파일을 쓴 직후 그 명령이 실행되어 파일을 고쳐 씁니다. 이 예제는 `.json` 파일의 키를 정렬하고 2칸 들여쓰기로 다시 쓰는 `scripts/fmt_json.py` 를 겁니다. 눈에 바로 보이고 안전합니다.
- **Part B, 플러그인 (`tool.execute.after`)**: formatter 는 파일을 고칠 뿐 **모델에게는 아무것도 알려 주지 않습니다.** 플러그인은 같은 시점에 검사기(`scripts/check_file.py`)를 돌리고, 결과를 도구 결과(`output.output`) 뒤에 붙입니다. 모델은 "린트 결과: 쓰지 않는 import 가 있다"를 도구 결과로 받아 다음 단계에서 스스로 고칩니다.

검사기가 없거나 실패해도 **편집은 그대로 성립**하고 플러그인은 로그만 남깁니다. after 훅에서 throw 하면 어떻게 되는지도 직접 확인해 두었습니다(아래 "주의할 점").

## 실무에서는

- 팀 포매터(ruff format, clang-format 등)를 `formatter` 로 걸어 두면, 모델이 들여쓰기나 import 순서를 신경 쓰지 않아도 파일이 항상 팀 규칙대로 저장됩니다.
- 포매터가 못 하는 일 — 쓰지 않는 import, 문법 오류, 타입 오류처럼 **사람이(모델이) 고쳐야 하는 문제** — 는 린터 결과를 모델에게 돌려줘야 합니다. 이 예제의 플러그인이 그 자리를 채웁니다. 모델은 파일을 쓸 때마다 즉시 피드백을 받으므로, 나중에 한꺼번에 CI 에서 실패하는 일이 줄어듭니다.

### 내장 formatter vs 플러그인: 언제 무엇으로 충분한가

| | 내장 `formatter` (설정) | 플러그인 `tool.execute.after` |
|---|---|---|
| 하는 일 | 파일을 **자동으로 고쳐 씀** | 검사하고 결과를 **모델에게 전달** |
| 모델이 아는가 | 모릅니다. 도구 결과에 아무 표시가 없고, 파일 내용만 모델이 쓴 것과 달라집니다 | 압니다. 도구 결과 끝에 `[린트 결과]` 가 붙습니다 |
| 사람이 고쳐야 하는 문제 (쓰지 않는 import, 문법 오류) | 못 다룸 | 다룸 |
| 작성 | JSON 몇 줄 | JS 플러그인 + 테스트 |
| 실패했을 때 | 조용히 건너뜀 (깨진 JSON 은 파일을 그대로 두고 종료 코드 1) | 이 예제는 로그만 남기고 편집은 유지 |
| 충분한 경우 | 들여쓰기·정렬·공백처럼 **기계적으로 고칠 수 있는** 규칙 | 린트·타입·보안 검사처럼 **모델이 읽고 판단해야** 하는 결과 |

둘은 함께 쓰는 것이 보통입니다(이 예제도 그렇습니다). formatter 가 먼저 파일을 정리하고, 플러그인은 정리된 파일을 검사합니다. 1.19.5 에서 이 순서를 확인했습니다: after 훅이 불리는 시점에 파일은 이미 formatter 가 끝낸 상태입니다.

## 파일 구성

```
p9-format-on-save/
├── README.md
├── opencode.json                      # Part A: formatter 설정 (.json -> scripts/fmt_json.py)
├── fake_llm.py                        # 검증용 가짜 LLM (표준 라이브러리만, 복사본)
├── check.py                           # 자동 검증 (단위 테스트 + 가짜 모델로 formatter/플러그인 + --model 검사)
├── scripts/
│   ├── fmt_json.py                    # formatter: 키 정렬 + 2칸 들여쓰기 (표준 라이브러리만)
│   └── check_file.py                  # 검사기: .py 문법/미사용 import/긴 줄, .json 문법 (표준 라이브러리만)
├── sample/lint_me.py                  # 따라 하기용: 쓰지 않는 import 가 일부러 들어 있음
├── .opencode/plugins/format-check.js  # Part B: 플러그인 본체
├── tests/after.test.mjs               # 훅을 직접 호출하는 단위 테스트 (24건, node)
└── logs/                              # 실행하면 생김: plugin-load 를 겸한 format-check.log
```

도우미 스크립트는 `.opencode/plugins/` 밖(`scripts/`)에 둡니다. 그 폴더 안의 모든 `.js` 가 플러그인으로 로드되기 때문입니다.

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. (모델 설정이 없다면 무료 모델 `-m opencode/big-pickle` 을 붙이세요.) 이 README 의 프롬프트로 실제 모델을 돌려 본 것은 아니어서, 모델의 말투와 순서는 **미검증**입니다. 가짜 모델로 한 결과는 아래 "기대 결과" 입니다.

1. 먼저 모델 없이 훅과 스크립트를 시험합니다.

   PowerShell:
   ```powershell
   cd examples\03-plugins\p9-format-on-save
   node tests\after.test.mjs
   python scripts\check_file.py sample\lint_me.py
   ```
   Linux bash:
   ```bash
   cd examples/03-plugins/p9-format-on-save
   node tests/after.test.mjs
   python3 scripts/check_file.py sample/lint_me.py
   ```
   `format-check: 24 checks, 0 failed` 와 `1행: 쓰지 않는 import: os` 가 나오면 정상입니다.

2. opencode 를 실행합니다. 처음 실행하면 opencode 가 `.opencode/` 안에 `@opencode-ai/plugin` 을 npm 으로 설치하려고 합니다. 인터넷이 막혀 있고 패키지 미러도 없으면 첫 시작이 70초쯤 멈췄다가 계속 진행됩니다. 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 아주 처음, 새 환경에서의 첫 시작은 약 130초까지 걸렸습니다(패킷을 조용히 버리는 레지스트리면 200초를 넘을 수도 있습니다). 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다. (이 단계는 패키지 미러가 필요할 수 있습니다. 모델 없이 하는 1번과 `python check.py` 는 필요 없습니다.)

   ```
   opencode
   ```

3. **Part A**: 키 순서가 엉망인 JSON 을 쓰게 합니다.

   `demo.json 파일을 만들어 줘. 내용은 정확히 {"version": 2, "name": "demo", "deps": {"zeta": 1, "alpha": 2}} 한 줄이야.`

   만들어진 파일을 열면 한 줄이 아니라 `deps`, `name`, `version` 순서로 정렬된 2칸 들여쓰기 JSON 입니다. 이어서 `demo.json 의 name 값을 "zz" 로 바꿔 줘` 라고 하면 `edit` 뒤에도 정렬이 유지됩니다.

4. **Part B**: 검사 결과를 보고 모델이 고치게 합니다.

   `sample/lint_me.py 맨 아래에 print("done") 한 줄을 추가해 줘. 도구 결과에 린트 결과가 나오면 그 문제도 고쳐 줘.`

   (`sample/lint_me.py` 가 실제로 고쳐지므로 끝난 뒤 되돌리세요.)

5. 기록 확인:

   PowerShell: `Get-Content -Encoding UTF8 logs\format-check.log`
   Linux bash: `cat logs/format-check.log`

6. 자동 검증: `python check.py` / `python check.py --model` (Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요).

## 기대 결과

아래 출력은 `check.py` 가 쓰는 **가짜 LLM**(`fake_llm.py`: 정해진 도구 호출을 대신 수행하는 OpenAI 호환 서버)으로 실제 `opencode 1.19.5`(Linux)를 실행해 얻은 것입니다. 실제 모델은 이번에 돌리지 않아 **미검증**입니다.

가짜 LLM 이 `write a.json`(키 순서 엉망) → `edit a.json` → `write lint.py`(미사용 import) → `edit lint.py`(import 제거) → `write broken.json`(깨진 JSON) 을 차례로 했을 때의 화면:

```
← Write a.json
Wrote file successfully.

[린트 결과] a.json: 문제 없음

← Edit a.json
Index: .../a.json
@@ -1,7 +1,7 @@
 {
-  "a": {
+  "b": 1,
+  "zz": {
     "y": 2,
     "z": 1
-  },
-  "b": 1
+  }
 }

← Write lint.py
Wrote file successfully.

[린트 결과] lint.py: 문제 발견. 다음 단계에서 고쳐 주세요.
1행: 쓰지 않는 import: os

← Edit lint.py
(diff)

← Write broken.json
Wrote file successfully.

[린트 결과] broken.json: 문제 발견. 다음 단계에서 고쳐 주세요.
1행: JSON 문법 오류: Illegal trailing comma before end of object
```

- `edit` 는 화면에 **diff**(metadata)를 보여 주고 `[린트 결과]` 는 보여 주지 않습니다. 하지만 모델이 받는 도구 결과에는 `Edit applied successfully.\n\n[린트 결과] lint.py: 문제 없음` 처럼 붙어 있습니다(가짜 모델 서버가 받은 요청 본문으로 확인). 화면에 안 보여도 모델은 받습니다.
- `a.json` 의 diff 는 formatter 가 정렬한 결과입니다: 모델이 `"a"` 를 `"zz"` 로 바꿨지만 파일에서는 `"b"` 뒤로 이동했습니다.
- 깨진 JSON 은 formatter 가 파일을 건드리지 않고(종료 코드 1) 넘어가고, 도구 결과에는 formatter 쪽 표시가 없었습니다. 알려 준 것은 플러그인뿐입니다.

`logs/format-check.log`:

```
2026-11-17T07:50:47.064Z format-check loaded
2026-11-17T07:50:48.743Z FOUND lint.py: 1건
2026-11-17T07:50:48.842Z FOUND b.json: 1건
```

단위 테스트와 `check.py`:

```
$ node tests/after.test.mjs
format-check: 24 checks, 0 failed
$ python3 check.py
== 19 checks, 0 failed, 0 warnings
```

## 동작 원리

1. **Part A.** `opencode.json` 의 `formatter.json-sorted` 는 `command: ["python","scripts/fmt_json.py","$FILE"]`, `extensions: [".json"]` 입니다. `$FILE` 이 방금 쓴 파일의 경로로 바뀝니다. `write` 와 `edit` **둘 다** 뒤에 실행되는 것을 확인했습니다(`write` 만 한 `.json` 도, `edit` 한 `.json` 도 정렬됨).
2. **Part B.** 플러그인은 `async ({ directory }) => 훅 객체` 를 export 하고, `tool.execute.after(input, output)` 에서 `input.tool` 이 `write`/`edit` 이고 `input.args.filePath` 의 확장자가 `.py`/`.json` 일 때만 동작합니다. `scripts/check_file.py` 를 **인자 배열**로 실행하고(셸 없음, 시간 제한 10초), 출력이 있으면 `output.output += "\n\n[린트 결과] ..."` 합니다. 바꾼 `output.output` 이 모델이 받는 도구 결과가 됩니다.
3. **검사기의 약속.** 종료 코드 0 = 깨끗함(`문제 없음` 한 줄만 붙임), 1 = 문제 있음(stdout 의 목록을 붙임), 그 밖 = 검사기 자체 실패(붙이지 않고 로그만). ruff 같은 실제 린터도 같은 규약입니다. 종료 코드 1 인데 출력이 비어 있으면(파이썬 검사기가 예외로 죽은 경우) 실패로 취급합니다.
4. **실패해도 편집은 유지.** 검사기 파일 없음, 파이썬 없음, 시간 초과, 비정상 종료, 대상 파일 없음은 모두 `logs/format-check.log` 에 `SKIP`/`FAIL` 로만 남기고 도구 결과는 그대로 둡니다. 훅 전체가 `try/catch` 이므로 어떤 예외도 밖으로 나가지 않습니다. `tests/after.test.mjs` 가 각 경우(검사기 없음, 종료 코드 3, 예외로 죽음, 시간 초과, 파이썬 없음, 이상한 입력)를 시험합니다.
5. **보내는 양을 제한.** 검사기는 최대 20건만 출력하고 플러그인은 붙이는 글자를 2000자로 자릅니다. 결과가 길어서 모델 맥락을 채우는 일을 막으려는 것입니다.

### 실제 도구로 바꾸기 (아래는 이 환경에서 **실행하지 않았습니다**, 미검증)

Part A, 설정만 바꾸면 됩니다.

```json
{
  "formatter": {
    "ruff-format": { "command": ["ruff", "format", "$FILE"], "extensions": [".py"] },
    "clang-format": { "command": ["clang-format", "-i", "$FILE"], "extensions": [".c", ".cc", ".cpp", ".h", ".hpp"] }
  }
}
```

(opencode 에 이미 내장된 formatter 와 이름·확장자가 겹칠 때 어느 쪽이 쓰이는지는 확인하지 못했습니다.)

Part B, 플러그인에서 검사기를 부르는 줄을 바꿉니다. `format-check.js` 의 `run(py, [checker, file], ...)` 를 예를 들어 다음처럼 바꿉니다.

```js
result = await run("ruff", ["check", "--output-format=concise", file], directory, timeout);
```

ruff 는 문제가 있으면 종료 코드 1 로 끝나므로 위의 약속과 맞습니다. clang-tidy 는 경고가 있어도 종료 코드 0 이라서, 종료 코드가 아니라 stdout 이 비었는지로 판단하도록 `0`/`1` 분기를 고쳐야 합니다. 두 도구 모두 `EXTENSIONS` 에 확장자를 추가해야 하고, 도구가 PATH 에 없으면 `ENOENT` 로 `FAIL` 이 기록되고 편집은 그대로입니다(같은 경로를 `P9_PYTHON=없는이름` 으로 시험해 `ENOENT` 가 기록되는 것은 확인).

## 직접 바꿔 보기

1. `scripts/check_file.py` 의 `MAX_LINE` 을 80 으로 바꾸고 `node tests/after.test.mjs` 가 어떤 사례에서 깨지는지 보세요. 검사 규칙을 바꾸는 일은 플러그인을 건드리지 않습니다.
2. `check_py` 에 규칙을 하나 추가해 보세요(예: `print(` 호출을 찾아 "디버그 출력이 남아 있다"). 모델이 `sample/lint_me.py` 에서 그것을 보고 지우는지 확인합니다.
3. 플러그인의 `EXTENSIONS` 에 `.txt` 를 넣고, 검사기가 `.txt` 를 모르면 종료 코드 0(`문제 없음`)이 붙는다는 것을 확인한 뒤, 모르는 확장자는 아무것도 붙이지 않게 고쳐 보세요.
4. (선택) `format-check.js` 의 마지막 `catch` 안에 `throw err` 를 넣고 의도적으로 실패시킨 뒤, 아래 "after 훅에서 throw 하면" 과 같은 결과가 나오는지 보세요.

## 주의할 점 / 문제 해결

- **after 훅에서 throw 하면 (직접 확인)**: 파일은 **이미 써지고 formatter 까지 끝난 뒤**인데, 모델은 도구가 실패한 것으로 받습니다. 가짜 모델에게 `write` 를 시켰을 때 모델이 받은 도구 결과는 던진 메시지(`THROWN-IN-AFTER`) 하나뿐이었고, 화면에는 `✗ Write a.json failed` 로 나왔지만 파일은 정렬된 상태로 디스크에 있었습니다. 모델은 쓰기가 실패한 줄 알고 같은 일을 다시 시도할 수 있습니다. 그래서 이 플러그인은 after 훅에서 절대 throw 하지 않습니다. `check.py` 가 이 동작을 고정합니다.
- **formatter 는 모델이 쓴 내용과 디스크 내용을 달라지게 합니다.** 모델에게는 알려지지 않으므로, 모델이 방금 쓴 문장을 기억해 다음 `edit` 의 `oldString` 으로 쓰면 맞지 않을 수 있습니다. `edit` 는 매번 파일을 다시 읽으니 대부분은 문제 없지만, 포맷 규칙이 크게 바꾸는 파일 형식에서는 알아 두세요.
- **화면과 모델이 보는 것이 다릅니다.** `write` 는 화면에도 `[린트 결과]` 가 나오지만 `edit` 는 diff 만 나옵니다. 모델이 무엇을 받았는지는 화면이 아니라 가짜 모델 서버가 받은 요청(`check.py` 의 `scripted_run`)으로 확인하세요.
- 이 플러그인은 `write`/`edit` 만 봅니다. 다른 도구(예: `apply_patch`)나 `bash` 로 고친 파일은 검사하지 않습니다. 가짜 모델이 받은 1.19.5 의 도구 목록에는 `apply_patch` 가 없었고, 다른 모델에서의 목록은 확인하지 못했습니다.
- 검사기가 `python`/`python3` 를 찾지 못하면 `FAIL ... ENOENT` 로 기록되고 아무것도 붙지 않습니다. 플러그인이 쓰는 파이썬은 `P9_PYTHON` 으로 지정할 수 있습니다. 시간 제한은 `P9_TIMEOUT_MS` (기본 10000).
- **export 는 플러그인 함수만 하세요.** 숫자·문자열·객체 같은 함수가 아닌 값(`export const X = 1`)을 export 하면 opencode 가 **파일 전체를 건너뜁니다.** 평소 실행에는 아무 출력도 없고 `opencode --print-logs` 에만 `Plugin export is not a function` 오류가 보입니다. 그래서 `MAX_APPENDED` 같은 상수와 `run()` 은 export 하지 않고, 테스트는 플러그인을 불러와 훅을 호출합니다. `.opencode/plugins/` 안의 모든 `.js` 가 플러그인으로 로드되므로 테스트와 스크립트는 그 폴더 밖에 둡니다.
- `node` 가 없으면 `check.py` 가 경고(WARN)를 내고 단위 테스트를 건너뜁니다. opencode 실행에는 Node 가 필요 없습니다.
- **Windows 에서의 확인**: 네이티브 Windows(Windows Python 3.12, Windows 용 opencode 1.19.5, bash 도구는 PowerShell 5.1)에서 `check.py` 19건과 단위 테스트(24건)가 통과했습니다. 실제 모델과 PowerShell 7 은 **미검증**입니다.
