# C7 OpenAI 호환 주소로 모델 연결하기

> 구성: opencode.json + 모의 서버 1개 | 난이도: ★☆☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: 설정 (모델 제공자)

## 무엇을 보여 주나

opencode 를 처음 쓸 때 가장 먼저 하는 일은 **모델이 있는 주소를 알려 주는 것**입니다. `opencode.json` 의 `provider` 에 `@ai-sdk/openai-compatible` 를 쓰는 항목을 하나 만들고, 주소(`baseURL`)와 키(`apiKey`)는 환경변수에서 읽게 합니다. OpenAI 호환 API(`/chat/completions`)를 제공하는 서비스라면 주소와 키만 바꿔서 같은 모양으로 연결됩니다.

**`model_server.py` 는 진짜 모델이 아니라 모의 서버입니다.** 어떤 질문에도 같은 고정 문장을 돌려주고, 요청이 어떻게 도착했는지(경로, Authorization 헤더가 맞는지, 모델 이름)만 기록합니다. 실제 서비스를 쓰려면 `LLM_BASE_URL` 과 `LLM_API_KEY` 를 그 서비스의 값으로 바꾸기만 하면 됩니다.

이 예제가 직접 확인한 것:

- `opencode models` 에 내 모델이 나온다
- `-m` 없이 `opencode run "..."` 이 기본 `model` 로 응답한다
- 서버가 `Authorization: Bearer <환경변수 값>` 을 받는다
- 환경변수가 비었을 때 사용자 화면에 무엇이 보이는지, 어떻게 원인을 찾는지
- `@ai-sdk/openai-compatible` 를 내려받지 않는다 (인터넷·패키지 미러 없이 동작)

## 실무에서는

- 게이트웨이든 직접 띄운 서버든 "OpenAI 호환"이라고 소개된 서비스는 이 모양으로 연결합니다. 저장소에 커밋하는 `opencode.json` 에는 `{env:...}` 만 적고, 주소와 키는 각자의 셸 환경에서 줍니다.
- 모델마다 `limit.context`(입력 한도)와 `limit.output`(출력 한도)을 적어 두면 opencode 가 그 한도를 참고합니다(이 예제에서 한도에 따른 동작은 시험하지 않았습니다). 서비스 문서의 값을 그대로 옮기세요.
- 연결이 안 될 때 "서버 문제인지 설정 문제인지"를 가르는 데 이 예제의 모의 서버와 아래 진단 순서가 그대로 쓰입니다.

## 파일 구성

```
c7-provider-openai-compatible/
  README.md
  opencode.json      provider "demo-endpoint": baseURL/apiKey 를 {env:} 로, 모델 2개(limit 포함), 기본 model
  model_server.py    모의 서버 (진짜 모델 아님). 고정 답변 + 요청 기록(stderr 와 logs/model_server.log)
  check.py           자동 검증
  logs/              model_server.py 가 만드는 기록 폴더 (git 에 올라가지 않음)
```

`opencode.json` 의 핵심:

```json
{
  "provider": {
    "demo-endpoint": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "데모 엔드포인트",
      "options": {
        "baseURL": "{env:LLM_BASE_URL}",
        "apiKey": "{env:LLM_API_KEY}"
      },
      "models": {
        "demo-chat":  { "name": "Demo Chat",  "limit": { "context": 32768, "output": 4096 } },
        "demo-small": { "name": "Demo Small", "limit": { "context": 8192,  "output": 2048 } }
      }
    }
  },
  "model": "demo-endpoint/demo-chat"
}
```

| 키 | 의미 |
|---|---|
| `provider.demo-endpoint` | provider 이름. 모델은 `demo-endpoint/모델이름` 으로 부른다 |
| `npm` | OpenAI 호환 API 를 말하는 어댑터. 실제 서비스에서도 같은 값 |
| `options.baseURL` | `/chat/completions` 바로 앞까지의 주소 (보통 `.../v1`) |
| `options.apiKey` | `Authorization: Bearer <값>` 으로 보내진다 |
| `models.<id>` | `id` 가 서버로 가는 `model` 값. `name` 은 화면 표시용 |
| `model` | `-m` 을 안 줬을 때 쓰는 기본 모델 |

## 따라 하기

터미널 두 개를 씁니다. 첫 번째는 모의 서버, 두 번째는 opencode 입니다.

1. **터미널 1: 모의 서버를 띄웁니다.**

   PowerShell:
   ```powershell
   cd examples\00-config\c7-provider-openai-compatible
   python model_server.py
   ```
   Linux bash (`python` 이 없으면 `python3`):
   ```bash
   cd examples/00-config/c7-provider-openai-compatible
   python3 model_server.py
   ```
   `모의 서버: http://127.0.0.1:8799/v1` 이 출력되면 준비된 것입니다. 포트가 이미 쓰이고 있으면 `--port 8800` 처럼 바꾸고 아래 주소도 맞추세요. (이 포트는 이 단계의 수동 실습용이고, `check.py` 는 빈 포트를 알아서 잡습니다.)

2. **터미널 2: 환경변수를 정하고 모델 목록을 봅니다.**

   PowerShell:
   ```powershell
   cd examples\00-config\c7-provider-openai-compatible
   $env:LLM_BASE_URL = "http://127.0.0.1:8799/v1"
   $env:LLM_API_KEY = "demo-token-123"
   opencode models demo-endpoint
   ```
   Linux bash:
   ```bash
   cd examples/00-config/c7-provider-openai-compatible
   export LLM_BASE_URL="http://127.0.0.1:8799/v1"
   export LLM_API_KEY="demo-token-123"
   opencode models demo-endpoint
   ```
   `demo-endpoint/demo-chat` 과 `demo-endpoint/demo-small` 두 줄이 나옵니다.

3. **`-m` 없이 질문합니다.** 기본 `model` 이 쓰입니다.

   ```
   opencode run "안녕"
   ```
   모의 서버의 고정 답변이 나오고 헤더에 `> build · demo-chat` 이 찍힙니다. 터미널 1 에는 요청 기록이 올라옵니다(아래 기대 결과).

4. **설정이 어떻게 해석됐는지 봅니다.**

   ```
   opencode debug config
   ```
   `provider.demo-endpoint.options` 의 `baseURL` 은 환경변수 값으로 바뀌어 보이고, `apiKey` 는 `***` 로 가려집니다.

5. **일부러 깨뜨려 봅니다.** 터미널 1 의 서버를 `Ctrl+C` 로 끄고 `python model_server.py --strict`(키가 다르면 진짜 서비스처럼 401)로 다시 띄운 뒤, 터미널 2 에서:

   PowerShell:
   ```powershell
   $env:LLM_API_KEY = "wrong-key"; opencode run "안녕"      # 키가 틀림
   Remove-Item Env:LLM_API_KEY;    opencode run "안녕"      # 키 환경변수가 없음
   $env:LLM_API_KEY = "demo-token-123"
   Remove-Item Env:LLM_BASE_URL;   opencode run "안녕"      # 주소 환경변수가 없음
   ```
   Linux bash:
   ```bash
   LLM_API_KEY=wrong-key opencode run "안녕"                 # 키가 틀림
   env -u LLM_API_KEY opencode run "안녕"                    # 키 환경변수가 없음
   env -u LLM_BASE_URL opencode run "안녕"                   # 주소 환경변수가 없음
   ```
   각각 무엇이 보이는지는 아래 "기대 결과"와 비교하세요. 끝나면 서버를 `Ctrl+C` 로 끕니다. 기록은 `logs/model_server.log` 에도 남아 있습니다 (PowerShell 에서 보려면 `Get-Content -Encoding UTF8 logs\model_server.log`).

## 기대 결과

아래는 모두 opencode 1.19.5, Linux 에서 직접 실행한 출력입니다.

**모델 목록과 첫 응답**

```
$ opencode models demo-endpoint
demo-endpoint/demo-chat
demo-endpoint/demo-small

$ opencode run "안녕"
[모의 서버] 이 문장은 model_server.py 가 돌려주는 고정 답변입니다. 실제 모델이 아닙니다.

> build · demo-chat
```

**서버가 받은 요청** (터미널 1 과 `logs/model_server.log`. 한 번의 `run` 에 두 줄이 생깁니다. `tools=0` 은 세션 제목을 만드는 보조 요청, `tools=10` 이 본 요청입니다.)

```
2026-11-17T16:39:39 POST /v1/chat/completions auth=match model=demo-chat stream=True tools=0
2026-11-17T16:39:40 POST /v1/chat/completions auth=match model=demo-chat stream=True tools=10
```

`auth=match` 는 서버가 받은 `Authorization` 이 `Bearer demo-token-123` 과 같다는 뜻입니다. 서버는 키 값을 기록하지 않습니다. `-m demo-endpoint/demo-small` 로 바꾸면 `model=demo-small` 이 찍힙니다.

**환경변수 문제의 모습**

| 상황 | 사용자 화면 | 서버 기록 |
|---|---|---|
| 키가 틀림 | `Error: Incorrect API key provided` (서버가 준 메시지 그대로, 종료 코드 1) | `auth=mismatch` |
| `LLM_API_KEY` 없음 | 위와 **똑같은** 메시지 | `auth=missing` (헤더가 아예 없음) |
| `LLM_BASE_URL` 없음 | `Error: Invalid URL` (종료 코드 1). 서버에는 요청이 오지 않음 | 없음 |
| 서버가 꺼져 있음 | `Error: Cannot connect to API: ECONNREFUSED: ...` | 없음 |
| `baseURL` 에서 `/v1` 을 뺌 | 모의 서버는 받아 주지만 | `POST /chat/completions` (경로에 `/v1` 이 없음) |

- 키 환경변수가 없으면 오류 없이 **빈 문자열**이 되고, 그러면 opencode 는 Authorization 헤더를 아예 보내지 않습니다. 서버가 401 을 주면 "키가 틀림"과 화면이 구분되지 않습니다. 서버 로그(`auth=missing` 과 `auth=mismatch`)로만 가를 수 있습니다.
- 서버가 꺼져 있을 때는 오류가 나오기까지 **약 68초**가 걸렸습니다(재시도 때문으로 짐작되지만 원인은 확인하지 않았습니다). 멈춘 것처럼 보여도 기다리면 위 메시지가 나옵니다.

**`--print-logs` 로 원인 찾기** (주소 환경변수가 없을 때)

```
$ opencode run --print-logs --log-level ERROR "안녕"
timestamp=... level=ERROR ... message="stream error" providerID=demo-endpoint modelID=demo-chat ... error.error="TypeError: Invalid URL"
...
Error: Invalid URL
```

어느 provider·모델에서 났는지(`providerID=demo-endpoint modelID=demo-chat`)까지 나옵니다. 키가 틀린 경우에는 `error.error="AI_APICallError: Incorrect API key provided"` 가 나옵니다.

**`opencode debug config` 가 보여 주는 것**

```json
"options": { "baseURL": "http://127.0.0.1:8799/v1", "apiKey": "***" }
```

- `baseURL` 은 가려지지 않습니다. 환경변수가 없으면 `"baseURL": ""` 로 보여서 바로 알아챌 수 있습니다.
- `apiKey` 는 **값이 있든 없든 `***`** 입니다. 가림은 키 이름 기반이라서, 이 출력으로는 키가 설정됐는지 알 수 없습니다. (C2 참고)

**첫 실행과 패키지 내려받기**

`@ai-sdk/openai-compatible` 은 opencode 1.19.5 에 들어 있어서 내려받지 않았습니다. 확인한 방법: (a) 새 캐시와 레지스트리 주소를 막은 환경(`NPM_CONFIG_REGISTRY`, `BUN_CONFIG_REGISTRY` 를 닫힌 포트로)에서도 첫 `run` 이 성공했고, (b) 네트워크 없는 네임스페이스(`unshare -rn`, 루프백만 켬)에서도 첫 `run` 약 6초, 두 번째 약 4초로 성공했으며, (c) 실행 뒤 캐시·데이터 폴더에 `@ai-sdk` 패키지가 생기지 않았습니다. 그래서 이 예제에는 "패키지 미러가 필요한 단계"가 없습니다. (다른 `npm` 값, 예를 들어 다른 어댑터를 쓰면 어떨지는 확인하지 않았습니다. 미검증)

## 동작 원리

1. 설정을 읽을 때 `{env:NAME}` 이 환경변수 값으로 바뀝니다. 없는 환경변수는 **오류 없이 빈 문자열**이 됩니다 ([C2](../c2-variables/README.md)).
2. `provider` 항목의 `npm` 이 어떤 어댑터로 말할지 정합니다. `@ai-sdk/openai-compatible` 이면 요청은 `POST {baseURL}/chat/completions` 이고, 본문의 `model` 은 `models` 의 키(`demo-chat`)입니다.
3. `apiKey` 가 비어 있지 않으면 `Authorization: Bearer <apiKey>` 헤더가 붙습니다. 비어 있으면 헤더가 붙지 않습니다.
4. `opencode models` 는 설정에 적힌 모델을 보여 줄 뿐 서버에 접속하지 않습니다. 환경변수가 없어도 목록에는 나옵니다. **연결은 실제로 한 번 질문해 봐야 압니다.**
5. 한 번의 `run` 은 모델 요청을 둘 보냅니다. 세션 제목을 만드는 요청(도구 없음)과 본 요청(도구 목록 포함)입니다.
6. `limit.context`, `limit.output` 은 모델의 입력·출력 한도를 알려 주는 값입니다. 이 값에 따른 동작은 이 예제에서 시험하지 않았습니다(미검증).

## 직접 바꿔 보기

1. `--strict` 로 서버를 띄운 채 `LLM_API_KEY` 를 틀리게/없게 바꿔 보고, 화면이 같고 서버 기록만 `mismatch` / `missing` 으로 다르다는 것을 확인하세요.
2. `LLM_BASE_URL` 을 `http://127.0.0.1:8799`(`/v1` 없음)로 바꿔 서버 기록의 경로가 달라지는지 보세요.
3. `opencode.json` 의 모델에 `demo-big` 을 추가하고 `opencode models demo-endpoint` 로 목록이 늘어나는지 보세요.
4. 진짜 OpenAI 호환 서비스가 있다면 `LLM_BASE_URL` 과 `LLM_API_KEY` 만 그 값으로 바꾸고 `models` 의 `demo-chat` 을 그 서비스의 모델 이름으로 바꿔 보세요.

## 주의할 점

- 키를 `opencode.json` 에 직접 적지 마세요. 저장소에 올라갑니다. 환경변수나 [C2](../c2-variables/README.md) 의 `{file:}` 를 쓰세요.
- 화면 공유 전 `opencode debug config` 출력의 가려진 부분을 믿지 마세요. 이름이 `apiKey` 일 때만 가려집니다.
- "연결이 안 된다"의 진단 순서: ① `opencode debug config` 에서 `baseURL` 이 비어 있지 않은지 → ② `opencode run --print-logs --log-level ERROR "안녕"` 으로 어느 단계에서 났는지 → ③ 서버 쪽 기록에 요청이 왔는지, `Authorization` 이 있는지.
- 모의 서버는 `/chat/completions` 의 일반 답변과 스트리밍만 흉내 냅니다. 도구 호출을 시키는 실습은 가짜 LLM 이 있는 다른 예제([C5](../c5-permissions/README.md))를 쓰세요.
- 포트 8799 는 수동 실습용 기본값입니다. 이미 쓰고 있다면 `--port` 로 바꾸세요.
- Linux 에서 `python` 명령이 없으면 `python3` 로 바꾸세요. 이 예제의 `opencode.json` 은 실행 명령을 쓰지 않아 그대로 둡니다.
