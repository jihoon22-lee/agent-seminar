# P11 도구 결과를 모델에게 가기 전에 가공하기 (output-filter)

> 구성: 플러그인(JS) `tool.execute.after` | 난이도: ★★★ | 필요: opencode 1.19.5, Python 3.10+ (MCP 예시 서버와 check.py), Node (단위 테스트에만) | 슬라이드: 플러그인 — 도구 결과 가공

## 무엇을 보여 주나

`tool.execute.after` 훅은 도구가 실행된 **뒤, 결과가 모델에게 가기 전에** 불립니다. 훅이 `output.output` 을 바꾸면 모델은 바뀐 글자를 받습니다. 이 예제는 그 성질로 두 가지를 합니다.

1. **비밀처럼 보이는 값을 가립니다.** 이름에 `TOKEN`/`SECRET`/`PASSWORD`/`API_KEY` 등이 들어간 `key=value`·`key: value`·`"key": "value"`, `--token 값` 옵션, `Authorization: Bearer 값` 을 `***` 로 바꿉니다.
2. **아주 긴 출력을 줄입니다.** 100줄을 넘으면 앞 40줄 + `... (N줄 생략) ...` + 뒤 40줄만 남깁니다(bash 와 MCP 도구).

예제의 값은 모두 눈에 띄는 가짜(`demo-secret-value-123`)입니다. 이 예제의 중요한 부분은 규칙 자체보다, **어느 도구의 결과를 바꿀 수 있고, 화면과 저장소에는 무엇이 남는지**를 직접 확인한 아래 표입니다.

## 실무에서는

- `cat .env`, `env`, `docker inspect`, 설정 파일 읽기처럼 도구 결과에 비밀이 섞이기 쉬운 작업에서, 비밀이 **모델 공급자에게 전송되는 요청**과 이후 모든 턴의 맥락에 들어가지 않게 합니다.
- 빌드·테스트 로그는 수천 줄이 한 번에 맥락에 들어가기도 합니다. 앞뒤만 남기면 비용과 맥락 소모가 줄어듭니다(실패 원인은 보통 끝부분에 있습니다).

## 실측: 무엇이 가려지고 무엇이 남는가 (opencode 1.19.5, Linux, 가짜 모델)

가짜 모델이 `cat sample/app.env`(bash), `read`, MCP 도구, `edit`, 긴 출력 bash 를 차례로 실행합니다. 훅은 도구마다 아래 모양의 `output` 을 받았습니다.

| 도구 | 훅이 받는 `output` | 바꾸면 모델이 받는 결과 | 화면(`opencode run`) | `metadata` 에 있는 다른 사본 |
|---|---|---|---|---|
| `bash` | `{title, output, metadata{output, exit, truncated}, attachments}` | `output.output` 을 바꾸면 **바뀐 글자를 받음** | `$ 명령` 아래 출력이 **가려진 글자**로 나옴 | `metadata.output` (원본 사본) |
| `read` | `{title, output, metadata{preview, truncated, loaded, display}, attachments}` | 바뀜 (`<content>` 안의 줄 번호는 그대로) | 파일 내용은 화면에 안 나옴 (`→ Read 파일명`) | `metadata.preview` (원본 사본) |
| `grep` | `{title, output, metadata{matches, truncated}, attachments}` | 바뀜 | 개수만 나옴 (`✱ Grep … 1 match`) | `matches` 는 개수라 비밀 없음 |
| `edit` | `{title, output, metadata{diff, filediff, …}, attachments}` | `output` 은 `Edit applied successfully.` 뿐이라 비밀 없음 | **diff 를 `metadata` 에서 그려서 파일 내용이 나옴** | `metadata.diff`, `metadata.filediff.patch` (원본 사본) |
| **MCP 도구** | **`{content: [...]}`, 서버가 `structuredContent` 를 주면 `structuredContent` 객체도 같이.** `output`, `title`, `metadata` 는 없음. `content` 항목은 서버가 정하는 대로 `{type:"text", text}`, `{type:"resource", resource:{uri, text}}` 등 | `content` 항목의 문자열을 바꾸면 **바뀐 글자를 받음** | `⚙ 도구이름` 만 나옴 | 없음 (대신 `structuredContent` 객체가 `output` 에 같이 옴. 아래 설명) |

MCP 결과는 서버마다 모양이 다릅니다. 이 예제의 `mcp_server.py` 가 네 가지 모양을 돌려주는 도구를 갖고 있고(`check.py` 가 모두 실행), 탐침 플러그인이 필터 훅을 부른 직후의 `output` 을 파일에 적게 해서 실제로 확인했습니다(플러그인이 불리는 순서는 OS 마다 달라서, 순서에 기대지 않도록 탐침이 필터를 직접 부릅니다).

| MCP 도구 | 서버가 보낸 결과 | 훅의 `output` | 모델이 받은 결과 |
|---|---|---|---|
| `cfg_show_config` | `content:[{type:"text"}]` | 같은 모양 | `content` 의 text |
| `cfg_show_resource` | `content:[{type:"resource", resource:{uri, mimeType, text}}]` | 같은 모양 (**text 는 `content[].text` 가 아니라 `content[].resource.text`**) | `resource.text` |
| `cfg_show_structured` | `content:[{type:"text"}]` + `structuredContent:{…}` | `content` 와 **`structuredContent` 객체가 함께** | `content` 의 text (객체는 모델에게 가지 않음) |
| `cfg_show_structured_only` | `content:[]` + `structuredContent:{…}` | opencode 가 `structuredContent` 를 JSON 문자열로 바꿔 `content:[{type:"text"}]` 에 **미리 넣어 줌** + `structuredContent` 객체도 그대로 | 그 JSON 문자열 |

- 이 플러그인의 이전 버전은 `type:"text"` 항목만 가렸습니다. 그래서 `resource` 항목에 든 `DB_PASSWORD=demo-secret-value-123` 은 **모델에게 가려지지 않은 채 갔습니다**(실제 opencode 실행에서 확인: 모델이 받은 결과가 원문 그대로). `structuredContent` 객체도 가려지지 않은 채 훅의 `output` 에 남아 있었습니다(모델에게 가는 text 쪽은 가려져 있었음).
- 지금은 MCP 결과의 **모든 항목의 모든 문자열을 재귀적으로** 가립니다. `text` 와 `resource.text` 는 문장 규칙으로 가린 뒤 줄이고, 나머지 문자열(`uri`, `description`, `_meta`, `structuredContent` 안의 값 …)은 가리기만 합니다. JSON 객체는 문장 규칙(`이름=값`)으로 잡히지 않으므로 **키 이름**이 `TOKEN|SECRET|PASSWORD|…` 를 포함하고 값이 4자 이상의 문자열(`$`·`<`·`{`·`%`·`(`·`*` 로 시작하지 않는)이면 값을 `***` 로 바꿉니다(`{"DB_PASSWORD":"…"}` → `{"DB_PASSWORD":"***"}`). 숫자는 건드리지 않습니다(`"max_tokens": 1024` 그대로).
- 못 가리는 것: 이미지·오디오의 base64 `data` 와 `resource.blob` 은 들여다보지 않습니다(바이너리를 정규식으로 훑으면 깨질 수 있어서). base64 로 인코딩된 비밀은 어디서도 못 가립니다.

`glob`, `webfetch`, `task`, 이미지 결과(`attachments`)는 확인하지 못했습니다(**미검증**). MCP 도구는 `output.output` 이 없으므로 `output.output` 만 바꾸는 플러그인은 MCP 결과를 **전혀 가리지 못합니다.** 이 플러그인은 `content` 와 `structuredContent` 를 처리합니다.

세션 저장소(sqlite, `XDG_DATA_HOME/opencode/opencode.db`)는 `part` 테이블과 `event` 테이블에서 확인했습니다.

| 설정 | 모델이 받음 | 화면 | `part`(저장된 도구 기록) | `event` 테이블 |
|---|---|---|---|---|
| 플러그인 없음 (대조군) | 원본 | 원본 | 원본 | 원본 |
| 플러그인 켬, **metadata 도 가림 (기본)** | 가려짐 | 가려짐 | 가려짐 | **`running` 상태 기록(bash 출력 스트림, edit diff)에 원본이 남음** |
| 플러그인 켬, `OUTPUT_FILTER_METADATA=0` | 가려짐 | bash 는 가려짐, **edit diff 는 원본** | `state.output` 은 가려짐, **`state.metadata` 에 원본** | 위와 같음 |

- `event` 테이블에 남는 것은 도구가 **실행 중일 때** 기록되는 `running` 상태의 metadata(bash 의 출력 스트림, edit 의 diff)입니다. 이것은 훅이 불리기 전에 이미 기록돼서 훅으로 가릴 수 없었습니다. 이 동작은 `check.py` 가 고정합니다(`{("bash","running"), ("edit","running")}`).
- opencode 는 bash 출력이 2000줄/50KB 를 넘으면 **훅이 불리기 전에** 스스로 잘라 앞부분을 버리고 `...output truncated...  Full output saved to: <경로>` 를 붙인 결과를 훅에 넘깁니다(대조군에서 3000줄 → 마지막 약 2000줄 확인). 이때 **전체 원본은 `data/opencode/tool-output/tool_…` 파일에 가려지지 않은 채 저장**됩니다(가짜 비밀이 그 파일에 들어 있는 것을 확인). 모델은 그 경로를 알게 되지만, 그 파일을 `read` 나 `cat` 으로 다시 읽으면 결과는 또 훅을 통과해 가려집니다.
- 이 플러그인은 `metadata` 의 사본도 같은 규칙으로 가립니다(`maskDeep`). 단 줄이기는 모델에게 가는 `output` 에만 적용하고 `metadata.output` 은 줄이지 않습니다(저장소에는 500줄이 그대로 남음).

### 이 플러그인이 보호하는 것 / 보호하지 않는 것

| 보호함 | 보호하지 못함 |
|---|---|
| **모델 맥락과 모델 공급자에게 전송되는 요청**에 들어가는 도구 결과 (이후 모든 턴 포함) | 명령은 **이미 실행됐습니다.** `cat .env` 가 읽은 사실, 외부로 보내는 명령(`curl`)의 효과는 되돌릴 수 없습니다 |
| 화면에 보이는 bash 출력, 저장된 `part` 기록 (기본 설정) | 파일은 **디스크에 그대로** 있습니다. 가려진 건 모델이 보는 글자뿐입니다 |
| | 모델이 **직접 쓴** 명령·인자에 든 비밀 (예: `curl -H "Authorization: Bearer …"` 를 모델이 타이핑). `tool.execute.after` 는 입력(`args`)을 바꾸지 않고, 저장된 `input` 에도 남습니다 |
| | `event` 테이블의 `running` 기록, `tool-output/` 의 전체 사본 |
| | 사용자가 프롬프트에 직접 붙여 넣은 비밀, 정규식에 안 걸리는 모양의 비밀 |

## 파일 구성

```
p11-output-filter/
├── README.md
├── opencode.json                      # MCP 서버 cfg 등록 (MCP 도구 결과 확인용)
├── mcp_server.py                      # 가짜 비밀을 돌려주는 아주 작은 MCP 서버 (도구 4개: 결과 모양이 다름, 표준 라이브러리만)
├── sample/app.env                     # 가짜 비밀이 든 파일 (demo-secret-value-123)
├── fake_llm.py                        # 검증용 가짜 LLM (표준 라이브러리만, 복사본)
├── check.py                           # 자동 검증 (단위 테스트 + 가짜 모델 4가지 설정 + --model 검사)
├── .opencode/plugins/output-filter.js # 플러그인 본체
├── tests/filter.test.mjs              # 훅을 직접 호출하는 단위 테스트 (139건, node)
└── logs/                              # 실행하면 생김: output-filter.log (도구별 가린 개수, 줄인 크기. 값은 기록하지 않음)
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. (모델 설정이 없다면 무료 모델 `-m opencode/big-pickle` 을 붙이세요.) 실제 모델로는 이번에 돌리지 않아 **미검증**입니다.

1. 먼저 모델 없이 마스킹과 줄이기를 시험합니다.

   PowerShell:
   ```powershell
   cd examples\03-plugins\p11-output-filter
   node tests\filter.test.mjs
   ```
   Linux bash:
   ```bash
   cd examples/03-plugins/p11-output-filter
   node tests/filter.test.mjs
   ```
   `output-filter: 139 checks, 0 failed` 가 나오면 정상입니다.

2. opencode 를 실행합니다. 처음 실행하면 opencode 가 `.opencode/` 안에 `@opencode-ai/plugin` 을 npm 으로 설치하려고 합니다. 인터넷이 막혀 있고 패키지 미러도 없으면 첫 시작이 70초쯤 멈췄다가 계속 진행됩니다. 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 아주 처음, 새 환경에서의 첫 시작은 약 130초까지 걸렸습니다(패킷을 조용히 버리는 레지스트리면 200초를 넘을 수도 있습니다). 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다. (이 단계는 패키지 미러가 필요할 수 있습니다.)

   ```
   opencode
   ```

3. `bash 도구로 cat sample/app.env 를 실행하고 DB_PASSWORD 값이 뭔지 알려 줘.` → 모델은 `DB_PASSWORD=***` 만 봅니다. 값을 모른다고 답해야 정상입니다. 비교하려면 `.opencode/plugins/output-filter.js` 를 잠시 다른 폴더로 옮기고 다시 실행해 보세요.

4. 기록 확인:

   PowerShell: `Get-Content -Encoding UTF8 logs\output-filter.log`
   Linux bash: `cat logs/output-filter.log`

5. 자동 검증: `python check.py` / `python check.py --model` (Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요). 가짜 모델 검사는 예제 폴더를 임시 폴더로 복사해서 실행하므로 `sample/app.env` 는 바뀌지 않습니다.

## 기대 결과

아래 출력은 `check.py` 가 쓰는 **가짜 LLM** 으로 실제 `opencode 1.19.5`(Linux)를 실행해 얻은 것입니다. 실제 모델은 **미검증**입니다.

(이 아래 화면과 도구 결과는 `check.py` 의 첫 번째 실행(`CHECK_VERBOSE=1 python3 check.py` 의 `--- A: 화면 ---`, `--- A: 모델이 받은 도구 결과 ---`)에서 가져온 것이고, 뒤쪽에 MCP 도구 세 개(`cfg_show_resource`, `cfg_show_structured`, `cfg_show_structured_only`)가 더 실행됩니다. 길어서 그 세 개는 아래에 따로 적었습니다.)

화면 (`cat sample/app.env` → read → MCP → edit → 500줄 bash → 3000줄 bash → 가려진 글자로 edit):

```
$ cat sample/app.env
APP_NAME=demo-app
DB_PASSWORD=***
API_KEY=***
other=1

→ Read sample/app.env
⚙ cfg_show_config Unknown

← Edit sample/app.env
Index: .../sample/app.env
@@ -1,4 +1,4 @@
 APP_NAME=demo-app
 DB_PASSWORD=***
 API_KEY=***
-other=1
+other=2

$ python -c "for i in range(1,501): print('line', i)"
... (420줄 생략) ...

$ python -c "print('API_KEY=' + 'demo-secret-' + 'value-123'); [print('line', i) for i in range(1,3001)]"
...output truncated...

Full output saved to: .../data/opencode/tool-output/tool_…

... (1923줄 생략) ...

✗ Edit sample/app.env failed
Error: Could not find oldString in the file. It must match exactly, including whitespace, indentation, and line endings.
⚙ cfg_show_resource Unknown
⚙ cfg_show_structured Unknown
⚙ cfg_show_structured_only Unknown
```

(화면에서 `line …` 로 이어지는 나머지 줄들은 길어서 뺐습니다. 3000줄 출력은 opencode 가 먼저 마지막 약 2000줄만 남겼고(`...output truncated...`), 플러그인이 그것을 다시 앞 40줄 + 뒤 40줄로 줄였습니다.)

모델이 마지막 요청에서 받은 도구 결과:

```
APP_NAME=demo-app
DB_PASSWORD=***
API_KEY=***
other=1
---
<path>…/sample/app.env</path>
<type>file</type>
<content>
1: APP_NAME=demo-app
2: DB_PASSWORD=***
3: API_KEY=***
4: other=1
...
---
DB_PASSWORD=***
mode=dev                                   <- MCP 도구 (text)
---
Edit applied successfully.
---
(... 500줄·3000줄 bash, 가려진 글자로 한 edit 의 실패 결과 ...)
---
DB_PASSWORD=***                            <- MCP 도구 (resource)
---
DB_PASSWORD=***
mode=dev                                   <- MCP 도구 (text + structuredContent)
---
{"DB_PASSWORD":"***","mode":"dev"}         <- MCP 도구 (structuredContent 만)
```

- 500줄 출력은 모델에게 81줄(앞 40 + 표시 1 + 뒤 40)로 갔습니다(원본 약 4.4KB → 800자 미만).
- 마지막 `edit` 는 모델이 가려진 글자(`API_KEY=***`)를 `oldString` 으로 썼기 때문에 실패했습니다. 모델은 원문을 모르니 이런 편집을 할 수 없습니다(아래 주의).

`logs/output-filter.log` (값은 기록하지 않고 개수와 줄인 크기만):

```
tool=bash masked=4
tool=read masked=6
tool=cfg_show_config masked=1
tool=edit masked=4
tool=bash masked=0 shortened=500줄 -> 81줄
tool=bash masked=1 shortened=2003줄 -> 81줄
tool=cfg_show_resource masked=1
tool=cfg_show_structured masked=2
tool=cfg_show_structured_only masked=2
```

(`masked` 는 `output`, `metadata`, `title` 안에서 치환한 횟수의 합입니다. 마지막 줄의 `masked=1` 은 opencode 가 잘라내 버린 첫 줄의 가짜 비밀이 `metadata.output` 사본에만 있어서 센 것입니다.)

```
$ node tests/filter.test.mjs
output-filter: 139 checks, 0 failed
$ python3 check.py
== 34 checks, 0 failed, 0 warnings
```

## 동작 원리

1. `tool.execute.after(input, output)` 에서 다음을 처리합니다. `output.output`(문자열)이 있으면 마스킹 후(bash 면) 줄이기, `output.content` 배열이 있으면(MCP) 모든 항목의 모든 문자열을 재귀적으로 가리고(`text`·`resource.text` 는 줄이기까지) `structuredContent` 등 다른 키도 가림, `output.title` 마스킹, `output.metadata` 안의 모든 문자열 마스킹(`OUTPUT_FILTER_METADATA=0` 이면 건너뜀).
2. **마스킹이 줄이기보다 먼저입니다.** 비밀이 생략 구간과 보존 구간의 경계에 걸쳐 일부만 남는 일을 막으려는 것입니다.
3. 마스킹 규칙(`RULES`)은 정규식 4개입니다.
   - `Authorization: Bearer|Basic|Token 값` / `"Authorization": "값"`
   - 단독 `Bearer 값`(8자 이상)
   - 이름에 `TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|ACCESS_KEY|PRIVATE_KEY|CREDENTIAL` 이 들어간 `이름=값`, `이름: 값`, `"이름": "값"`
   - `--token 값`, `--password=값`, `--api-key 값`

   **값이 어디서 끝나는가 (`VALUE`).**

   | 값의 모양 | 가리는 범위 | 예 |
   |---|---|---|
   | `"…"` 큰따옴표 (`\"` 이스케이프 허용) | 닫는 따옴표까지 전부, 공백 포함. 따옴표는 남김 | `DB_PASSWORD="correct horse battery"` → `DB_PASSWORD="***"` |
   | `'…'` 작은따옴표 | 닫는 따옴표까지 전부 | `DB_PASSWORD='pw with spaces 123'` → `DB_PASSWORD='***'` |
   | 여는 따옴표만 있고 닫는 따옴표가 줄 안에 없음 | 그 줄 끝까지 (다음 줄은 건드리지 않음) | `DB_PASSWORD="correct horse` → `DB_PASSWORD="***` |
   | 따옴표 없음 | **공백, 따옴표, `;` 에서 끝.** 쉼표는 바로 뒤에 공백·따옴표·`;` 가 오면 거기서 끝, 아니면 값의 일부 | `API_KEY=abc,defghijkl` → `API_KEY=***` / `f(password: str, x)` 는 그대로 |

   값은 어느 경우든 4글자 이상일 때만 봅니다(`PASSWORD="ab"` 는 그대로). 짧은 따옴표 값 뒤에 글자가 이어져도 그것을 값으로 오해하지 않습니다(`PASSWORD="ab" and more` 그대로).

   값이 4자 미만이거나 `$`, `<`, `{`, `%`, `(` , `*` 로 시작하면(환경변수 참조, 자리표시, 템플릿, 이미 가려진 값) 건너뜁니다. 그래서 `password = $PASSWORD` 와 `token count: 12` 는 그대로, `API_KEY=***` 에 다시 적용해도 같은 결과(멱등)입니다. 영어 단어 `Basic information` 은 `Authorization:` 뒤에서만 인식하므로 그대로 둡니다.
4. 줄이기는 `bash` 와 MCP 도구에만 합니다. `read` 와 `grep` 은 자체 쪽 나누기·개수 제한이 있고, 중간을 자르면 모델이 파일을 오해할 수 있어서 제외했습니다. 줄 수가 적어도 글자가 2만자를 넘으면(한 줄짜리 거대 출력) `... (N자 생략) ...` 로 글자 단위로 자릅니다. 기준은 `OUTPUT_FILTER_MAX_LINES`(100), `OUTPUT_FILTER_HEAD`(40), `OUTPUT_FILTER_TAIL`(40), `OUTPUT_FILTER_MAX_CHARS`(20000) 입니다.
5. 필터 자체가 실패하면 결과를 그대로 두고 `ERROR` 만 기록합니다(fail-open). 비밀 필터가 오류로 에이전트를 멈추게 하는 쪽보다 낫다고 판단한 선택이고, 엄격하게 하려면 `catch` 에서 `output.output = "[필터 오류로 결과를 숨김]"` 처럼 바꾸세요.

## 직접 바꿔 보기

1. `RULES` 에 `://사용자:비밀번호@호스트` 형태의 접속 문자열을 가리는 규칙을 하나 추가하고 `tests/filter.test.mjs` 에 사례를 넣어 보세요. (비밀번호 자리에는 `pw-demo` 같은 눈에 띄는 가짜 값을 쓰세요.)
2. `OUTPUT_FILTER_MAX_LINES=20 OUTPUT_FILTER_HEAD=5 OUTPUT_FILTER_TAIL=5` 로 실행해 `ls -R` 같은 출력이 어떻게 보이는지 확인하세요.
3. `shortenIt` 에 `grep` 을 추가하면 단위 테스트의 어떤 사례가 깨지는지 보고, 왜 `read`/`grep` 을 제외했는지 생각해 보세요.
4. `OUTPUT_FILTER_METADATA=0` 으로 실행하고 `edit` 를 시켜 화면 diff 에 원본이 나타나는 것을 직접 확인하세요.

## 주의할 점 / 문제 해결

- **이것은 모델에게 가는 글자를 가리는 것입니다.** 명령은 이미 실행됐고 파일은 그대로입니다. 비밀 파일을 아예 못 읽게 하려면 `tool.execute.before` 로 막는 [P1](../p1-env-guard/README.md) 이 맞고, 둘은 함께 쓸 수 있습니다.
- **모델이 가려진 글자로 파일을 고치면 데이터가 깨질 수 있습니다.** 모델은 `API_KEY=***` 만 알고 있으므로 `edit` 의 `oldString` 이 맞지 않아 실패하는 것이 다행인 경우이고(위 기대 결과의 마지막 `edit`), `write` 로 파일 전체를 다시 쓰면 `***` 가 실제 파일에 들어갑니다(모델이 가려진 내용을 그대로 `write` 하면 그 내용이 파일에 쓰이는 것은 도구가 원래 하는 일이라 따로 시험하지 않았습니다). 비밀이 든 파일은 `write` 로 통째로 다시 쓰지 않게 하세요.
- **오탐이 있습니다.** 이름에 `TOKEN` 이 들어가면 값이 비밀이 아니어도 가립니다(`max_tokens=1024` → `max_tokens=***`). 소스 코드의 `def login(password: str):` 처럼 값 뒤에 `)` 가 바로 붙은 4자 이상 토큰도 가립니다. 단위 테스트가 이 두 가지를 "알려진 한계"로 고정합니다. 코드를 읽는 작업이 많다면 규칙을 좁히세요.
- **미탐도 있습니다.** 정확히 이렇습니다(단위 테스트가 "한계"로 고정).
  - 이름 없이 값만 출력된 토큰은(이 예제는 실제 토큰 모양을 쓰지 않으므로 그런 모양의 규칙도 넣지 않았습니다) 가리지 못합니다. 이름이 `TOKEN` 등을 포함하지 않는 `key=값`(예: `AUTH=값`), 줄바꿈으로 갈라진 값, base64 로 인코딩된 값도 못 가립니다.
  - **따옴표 없는 값에 공백이 있으면 첫 단어만 가립니다.** `password: correct horse battery` → `password: *** horse battery`. 공백이 든 값은 따옴표로 감싸야 끝까지 가려집니다.
  - **값이 4글자 미만이거나, 첫 조각이 4글자 미만**이면 가리지 않습니다. `PASSWORD=ab;cdefgh`(`;` 에서 끝나고 `ab` 가 짧음)와 `curl -d 'password=abc def'` 는 그대로입니다.
  - 따옴표 값 안에 같은 종류 따옴표가 이스케이프 없이 들어 있으면 거기서 끝납니다(큰따옴표는 `\"` 이스케이프를 알지만 작은따옴표는 이스케이프를 모릅니다).
  - 이미지·오디오의 base64 `data`, `resource.blob` 은 들여다보지 않습니다. JSON 객체에서 숫자 값(`"password": 12345678`)은 가리지 않습니다.
- `tool.execute.after` 는 도구가 **끝난 뒤** 불립니다. 입력(`args`)은 바꾸지 못하므로, 모델이 명령에 직접 쓴 비밀은 이 훅으로 가릴 수 없습니다.
- opencode 의 내장 잘라내기(2000줄/50KB)가 먼저 적용됩니다. 그 결과의 첫 줄 `...output truncated...` 와 `Full output saved to:` 안내는 이 플러그인의 "앞 40줄"에 포함되어 모델에게 남습니다.
- **export 는 플러그인 함수만 하세요.** 숫자·문자열·객체 같은 함수가 아닌 값(`export const X = 1`)을 export 하면 opencode 가 **파일 전체를 건너뜁니다.** 평소 실행에는 아무 출력도 없고 `opencode --print-logs` 에만 `Plugin export is not a function` 오류가 보입니다. 보조 함수를 export 하면 그 함수까지 플러그인으로 호출됩니다. 그래서 `RULES`, `maskText`, `shorten` 은 export 하지 않고, 테스트는 훅을 통해서만 시험합니다. `.opencode/plugins/` 안의 모든 `.js` 가 플러그인으로 로드되므로 테스트와 MCP 서버 스크립트는 그 폴더 밖에 둡니다.
- MCP 서버(`opencode.json` 의 `mcp.cfg`)는 `python` 이 PATH 에 있어야 합니다. Linux 에서 `python` 명령이 없으면 `opencode.json` 의 `python` 을 `python3` 으로 바꾸세요(`opencode mcp list` 로 연결 확인). 플러그인 자체는 Python 이 필요 없습니다.
- `node` 가 없으면 `check.py` 가 경고(WARN)를 내고 단위 테스트를 건너뜁니다. opencode 실행에는 Node 가 필요 없습니다.
- **Windows 에서의 확인**: 네이티브 Windows(Windows Python 3.12, Windows 용 opencode 1.19.5, bash 도구는 PowerShell 5.1)에서 `check.py` 34건과 단위 테스트(139건)가 통과했습니다. 실제 모델과 PowerShell 7 은 **미검증**입니다.
