# P7 세션 압축(compaction) 때 고정 사실 끼워 넣기

> 구성: 플러그인 1개(`.opencode/plugins/compaction-context.js`) + 고정 사실 파일 1개 + 가짜 LLM 검증 | 난이도: ★★★ | 필요: opencode 1.19.5, Python 3.10+ (check.py 용), Node 불필요 | 슬라이드: 플러그인 — 실험적 훅

> **이 예제가 쓰는 훅 두 개(`experimental.session.compacting`, `experimental.compaction.autocontinue`)는 실험적입니다.** 이름·입력·출력 모양이 다음 opencode 버전에서 바뀌거나 사라질 수 있습니다. 아래 "주의할 점"의 유지보수 방법을 꼭 읽으세요. 이 문서의 모든 모양은 opencode **1.19.5** 에서 관찰한 것입니다.

## 무엇을 보여 주나

대화가 길어지면 opencode 는 오래된 대화를 요약(compaction)으로 바꿔 컨텍스트를 비웁니다. 이때 요약 모델이 "이 프로젝트는 pnpm 을 쓴다" 같은 중요한 사실을 빼먹으면 이후 대화에서 모델이 그 사실을 잊습니다.
이 플러그인은 압축이 시작되는 순간 `.opencode/memory/project-facts.md` 의 내용을 **요약 프롬프트 끝에 덧붙여** 요약에 반드시 남도록 하고, 훅이 호출될 때마다 `logs/compaction.log` 에 기록합니다.

## 실무에서는

- 몇 시간짜리 작업 세션에서 "결제 모듈은 승인 없이 수정 금지", "배포 환경 이름은 stage/prod 뿐" 같은 **절대 잊으면 안 되는 규칙**을 압축 뒤에도 유지하고 싶을 때.
- 팀 공용 `AGENTS.md` 에 넣기엔 세션마다 다른 메모(오늘의 작업 맥락, 임시 브랜치 이름)를 압축 요약에 실어 보내고 싶을 때.
- 압축이 언제 몇 번 일어나는지 감사/디버깅 로그로 남기고 싶을 때.

## 파일 구성

```
p7-compaction-context/
├── README.md
├── .opencode/
│   ├── plugins/compaction-context.js   # 훅 2개: compacting (고정 사실 추가), autocontinue (기록만)
│   └── memory/project-facts.md         # 압축 요약에 반드시 남길 고정 사실 (직접 고쳐 보세요)
├── fake_llm.py                          # 가짜 LLM 서버 (압축 요청 본문을 기록하는 check.py 용)
├── check.py                             # 자동 검증
└── logs/compaction.log                  # (실행하면 생김, git 에 안 올라감) 훅 호출 기록
```

opencode 는 `.opencode/plugins/` 아래 `.js`/`.ts` 파일을 자동으로 불러오므로 `opencode.json` 이 필요 없습니다.
이 폴더에 처음 `.opencode/` 가 생기면 opencode 가 `@opencode-ai/plugin` 을 npm 에서 `.opencode/` 에 자동 설치합니다(`package.json`, `node_modules/` 가 생기며 git 에는 올라가지 않음).
패키지 미러가 없는 환경에서는 첫 시작이 약 70초 멈췄다가 계속됩니다. 이 플러그인은 `node:` 내장 모듈만 쓰므로 `@opencode-ai/plugin` 에 의존하지 않습니다(설치가 실패한 환경에서의 동작은 확인하지 못했습니다).

## 따라 하기

> 이 예제에는 MCP 서버가 없어서 `python` 명령은 `check.py` 에만 필요합니다. Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요.

### 1. TUI 에서 직접 압축해 보기 (평소 쓰는 모델로 실행하면 됩니다)

PowerShell:

```powershell
cd examples\03-plugins\p7-compaction-context
opencode
```

Linux bash:

```bash
cd examples/03-plugins/p7-compaction-context
opencode
```

(모델 설정이 없다면 `opencode -m opencode/big-pickle`.) TUI 에서:

1. "로그인 화면 버그를 고치려고 해. 오늘 할 일을 한 문장으로 정리해줘." 처럼 고정 사실과 무관한 대화를 두세 번 합니다.
2. `/compact` 를 입력하고 Enter. (자동완성 설명은 `Compact session`)
3. 다른 터미널에서 로그를 봅니다.

```powershell
Get-Content logs\compaction.log
```

```bash
cat logs/compaction.log
```

4. 압축이 끝난 뒤 "도구는 쓰지 말고, 요약에 남은 내용만으로 답해줘. 이 프로젝트의 패키지 매니저는?" 이라고 물어보세요. 대화에서 한 번도 말한 적 없는 `pnpm` 이 나오면 고정 사실이 요약에 실려 간 것입니다.

### 2. 모델 없이 훅만 확인

```text
python check.py            # 가짜 LLM 으로 훅 호출·입출력 모양·요약 프롬프트 내용을 확인 (약 30초)
python check.py --model    # 실제 모델이 만든 요약에 pnpm 이 들어가는지까지 (soft)
```

### 3. 서버 API 로 압축하기 (선택)

`opencode serve --port 4096` 을 띄운 뒤, 세션 id 로:

```text
POST http://127.0.0.1:4096/session/<세션id>/summarize
Content-Type: application/json
{"providerID": "<provider>", "modelID": "<model>"}
```

성공하면 `true`. `/compact` 와 같은 기능이고 `check.py` 가 이 방법을 씁니다.

## 기대 결과

`logs/compaction.log` (JSON 한 줄씩, 실제 캡처):

```text
{"at":"2026-11-16T16:22:25.194Z","event":"compacting","sessionID":"ses_e1ad55cc1ffefV7dAiCW8VsXiV","inputKeys":["sessionID"],"outputKeys":["context","prompt"],"contextBefore":0,"promptSet":false,"factsChars":240}
```

요약 모델에게 간 요청 (가짜 LLM 이 기록한 본문, `/compact` 한 번에 요청 1개, 도구 목록 없음):

```text
[system] You are a context summarization agent. You are given a conversation between a user and an agent. …
[user]   Here is the conversation so far:

         <conversation>
         [User]: 첫 질문: 이 프로젝트 소개해줘
         [Assistant]: …
         </conversation>

         Create a new anchored summary from the conversation history in the <conversation> tags above …
         <template>
         ## Objective … ## Important Details … ## Work State … ## Next Move … ## Relevant Files
         </template>

         Rules:
         - Keep every section, even when empty.
         …
         - Do not mention the summary process or that context was compacted.

         다음은 대화가 압축되어도 반드시 유지해야 하는 프로젝트 고정 사실이다. 요약의 Important Details 에 그대로 포함하라.

         # 프로젝트 고정 사실 (압축돼도 잊으면 안 되는 것)

         - 이 저장소의 패키지 매니저는 pnpm 이다. npm install 을 쓰지 않는다.
         - 결제 모듈(`src/payment/`)은 승인 없이 수정하지 않는다.
         …
```

자동 압축에서는 훅이 두 개 순서대로 불립니다:

```text
{"event":"compacting", …}
{"event":"autocontinue","inputKeys":["sessionID","agent","model","provider","message","overflow"],"overflow":false,"agent":"build","model":"echo","outputBefore":{"enabled":true}}
```

**실제 모델의 요약은 이 문서에 싣지 못했습니다.** 작성 시점에 무료 모델이 응답하지 않아(`python check.py --model` 의 모델 검사가 시간 초과로 SKIP) "요약에 `pnpm` 이 실제로 담긴다"는 마지막 고리는 **검증하지 못했습니다**. 확인된 것은 "요약 모델에게 가는 프롬프트에 고정 사실이 들어간다"까지입니다. 직접 해 보고 결과를 확인하세요(위 따라 하기 1번).

## 동작 원리

### 압축은 언제 일어나나 (1.19.5 에서 확인한 세 가지 길)

| 방법 | 설명 |
| --- | --- |
| TUI `/compact` | 슬래시 명령 목록에 `Compact session` 으로 보입니다. 입력하면 훅이 호출됩니다. |
| 서버 API `POST /session/:id/summarize` | 본문 `{"providerID","modelID"}`. 응답 `true`. |
| 자동 | 모델 응답의 토큰 사용량이 컨텍스트 한도에 가까우면 opencode 가 스스로 압축합니다. `opencode run` 만으로도 일어납니다(`check.py` 는 가짜 LLM 이 "입력 99,000 토큰 / 한도 100,000" 이라고 보고하게 해서 재현). 압축 뒤 `Continue if you have next steps…` 라는 이어하기 턴이 자동으로 한 번 더 실행됩니다. |

**안 되는 길** (모두 확인): `opencode run --command compact` 는 `Unexpected server error` 로 실패합니다(`compact` 는 서버가 아니라 TUI 가 가진 내장 명령). `opencode run "/compact"` 는 명령으로 해석되지 않고 글자 그대로 모델에게 갑니다. `POST /api/session/:id/compact`(v2 API)는 `503 Session compact is not available yet` 입니다.
비대화형으로 압축을 재현하려면 `summarize` API 나 위의 자동 압축 방법을 쓰세요.

### 훅 `experimental.session.compacting`

```js
"experimental.session.compacting": async (input, output) => { … }
```

| | 모양 (관찰) |
| --- | --- |
| `input` | `{ sessionID: string }` — 키는 이것 하나 |
| `output` | `{ context: string[], prompt?: string }` — 시작할 때 `context` 는 빈 배열, `prompt` 는 `undefined` |

- `output.context.push("…")`: 문자열이 **기본 압축 프롬프트 맨 끝에 빈 줄을 사이에 두고** 붙습니다. 요약 모델이 읽는 사용자 메시지의 마지막 부분이라 "요약의 Important Details 에 포함하라" 같은 지시를 같이 쓰는 것이 효과적입니다.
- `output.prompt = "…"`: 기본 압축 프롬프트(템플릿 포함)를 **통째로 대체**합니다. 그러면 `output.context` 에 넣은 내용은 **무시**되고, 대화 원문은 `The following is the conversation history:` 아래에 붙습니다. 요약 형식까지 바꿀 때만 쓰세요. (이 예제는 쓰지 않음. `check.py` 의 변형 플러그인으로 확인)
- 훅 안에서 **예외가 나면 압축이 통째로 실패**합니다(`summarize` 가 500, 요약 요청 자체가 안 나감). 그래서 이 플러그인은 `safe()` 로 감싸 오류를 로그에만 남깁니다.
- 반환값은 쓰이지 않습니다. `output` 을 직접 고칩니다.

### 훅 `experimental.compaction.autocontinue`

| | 모양 (관찰) |
| --- | --- |
| `input` | `{ sessionID, agent, model, provider, message, overflow }` (`model`/`provider` 는 전체 객체, `overflow` 는 컨텍스트 초과로 인한 압축이었는지) |
| `output` | `{ enabled: true }` — `false` 로 바꾸면 자동 압축 뒤 "이어하기" 턴이 만들어지지 않습니다(확인) |

이 예제는 기록만 하고 값을 바꾸지 않습니다. `check.py` 의 변형 플러그인이 `enabled = false` 로 요청 수가 4개에서 3개로 줄어드는 것을 확인합니다.

### 플러그인 파일 위치 계산

플러그인은 `import.meta.url` 로 자기 위치를 구해 `../memory/project-facts.md` 와 `../../logs/compaction.log` 를 찾습니다. opencode 를 하위 폴더에서 띄워도 같은 파일을 씁니다.

## 직접 바꿔 보기

1. `project-facts.md` 에 자기 프로젝트의 규칙을 몇 줄 쓰고 다시 `/compact` 해 보세요. 반드시 이어야 할 사실만 남기세요. 길면 요약이 길어지고 비용이 늡니다.
2. 훅에서 `output.context.push(` 대신 `output.prompt = "…"` 를 써서 요약 형식을 "한 줄 요약"으로 바꿔 보고, 이때 `project-facts.md` 가 왜 무시되는지 `logs/compaction.log` 의 `promptSet` 으로 확인하세요.
3. `autocontinue` 훅에서 `output.enabled = false` 로 바꿔 자동 압축 뒤에 모델이 스스로 이어가지 않는 것을 확인하세요.

## 주의할 점 / 문제 해결

### 실험적 훅이라는 것의 의미 (유지보수)

- 이름의 `experimental.` 접두사는 "안정 API 가 아니다" 라는 뜻입니다. opencode 업데이트 때 **경고 없이** 이름이나 `input`/`output` 모양이 바뀌거나 훅이 사라질 수 있고, 그러면 플러그인은 에러 없이 조용히 아무 일도 하지 않게 될 것으로 예상됩니다(훅이 호출되지 않을 뿐. 이 부분은 실제로 확인하지 못했습니다).
- 그래서: ① opencode 버전을 고정하고(이 문서는 1.19.5) 업그레이드할 때 `python check.py` 를 다시 돌리세요. 훅 호출 여부·입출력 키·프롬프트 내용을 모두 단언합니다. ② 플러그인에는 `logs/compaction.log` 같은 "훅이 불렸다" 증거를 남기세요. 로그가 안 늘어나면 훅이 바뀐 것입니다. ③ `output.context` 가 배열인지 같은 가정을 코드로 검사하고 `try/catch` 로 감싸세요(이 플러그인의 `safe()`). ④ 이 훅에 의존하는 기능은 "있으면 좋은 것"으로 두세요. 훅이 사라져도 압축은 계속 됩니다.
- 안정적으로 같은 효과를 내고 싶다면 `AGENTS.md`/`instructions` 에 규칙을 적는 방법이 있습니다. 압축 후에도 시스템 프롬프트로 계속 들어가므로 가장 튼튼합니다. 이 훅은 "세션마다 달라지는 메모" 용입니다.

### 그 밖에

- 첫 실행이 느리면(수십 초) `.opencode/` 에 `@opencode-ai/plugin` 을 설치하는 중일 수 있습니다. 한 번 설치되면 이후에는 빨리 시작합니다.
- `logs/compaction.log` 가 안 생기면 `/compact` 가 실제로 요약까지 갔는지(모델 오류가 없었는지), 플러그인 파일이 `.opencode/plugins/` 에 있는지 확인하세요. 설정은 시작할 때 한 번 읽으므로 플러그인을 고친 뒤에는 opencode 를 재시작해야 합니다.
- 고정 사실 파일의 비밀번호 줄은 데모용 가짜 값입니다. 실제 비밀값을 `project-facts.md` 에 쓰면 요약 모델(외부 서비스)로 전송됩니다. 쓰지 마세요.
- Windows 에서도 동일하게 동작합니다. 경로는 `path` 모듈로 만들었고 파일은 UTF-8 로 읽고 씁니다.
