# X1 같은 기능, 세 가지 방법 - 스킬 vs MCP vs 플러그인

> 구성: 스킬 + MCP + 플러그인 비교 | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, (c-plugin 은 첫 실행 때 npm 레지스트리/미러) | 슬라이드: 정리 - 언제 무엇을 쓰나

## 무엇을 보여 주나

"팀 용어 조회"라는 **똑같은 기능**을 스킬 / MCP 서버 / 플러그인 도구로 각각 만들었습니다. 세 폴더는 서로 독립된 opencode 프로젝트이고
각자 `glossary.json` 사본을 갖고 있습니다. 같은 질문을 세 폴더에서 해 보고, 모델 화면에 나타나는 모양과 만드는 수고가 어떻게 다른지 비교합니다.

## 실무에서는

세 가지 확장 방법 중 무엇을 고를지 정할 때 이 표를 떠올리세요.

| | **a. 스킬** | **b. MCP 서버** | **c. 플러그인 도구** |
|---|---|---|---|
| **코드가 실행되는 곳** | 모델이 `bash` 로 부르는 **스크립트**(모델이 명령을 실행) | **별도 프로세스**(stdio) 또는 원격 서버 | **opencode 프로세스 안**(Bun) |
| **누가 호출을 결정하나** | 모델이 스킬 `description` 을 보고 **스킬을 로드**한 뒤, 본문의 절차대로 스크립트 실행 | 모델이 도구 `description` 을 보고 직접 호출 | 모델이 도구 `description` 을 보고 직접 호출 |
| **컨텍스트에 항상 있는 것** | **이름 + 설명 한 줄**(이 예제 134자). 본문(348자)은 로드될 때만 | **도구 스키마 전체**(이 예제 263자) - 도구가 많으면 비례해서 커짐 | **도구 스키마 전체**(이 예제 319자) |
| **다른 에이전트로 옮기기** | `SKILL.md` 형식은 여러 에이전트가 읽음(폴더 복사). 스크립트는 그대로 | **가장 쉬움** - 표준 프로토콜, 어떤 에이전트든 같은 서버 사용 | **불가능** - opencode 전용 |
| **만드는 수고** | **가장 낮음**: 마크다운 + 스크립트 | 중간: JSON-RPC 서버(표준 라이브러리로 약 70줄) | 낮음~중간: JS 한 파일, 단 `@opencode-ai/plugin` npm 설치 필요 |
| **어울리는 일** | 절차·규칙·"이렇게 해라" 지침, 스크립트로 해결되는 조회 | 여러 에이전트/사람이 공유하는 도구, 외부 시스템 연동 | opencode 안의 가벼운 계산·조회, opencode 내부 기능과 얽힌 일 |

> 컨텍스트 수치는 `check.py` 가 파일에서 센 **글자 수**입니다(토큰이 아님). 이 예제는 도구가 1개라서 차이가 작지만,
> MCP 서버가 도구 30개를 내놓으면 매 요청마다 30개 스키마가 따라붙는 반면 스킬 30개는 이름·설명 30줄뿐입니다.

한 줄 요약: **지침·절차는 스킬, 공유해야 하는 도구는 MCP, opencode 안의 가벼운 기능은 플러그인.**

## 파일 구성

```
x1-three-ways/
├── README.md
├── check.py
├── a-skill/                                   # 방법 a: 스킬
│   └── .opencode/skills/team-glossary/
│       ├── SKILL.md                           # 언제·어떻게 쓰는지 (description 에 한국어 트리거)
│       ├── glossary.json                      # 사전 사본
│       └── scripts/lookup.py                  # 실제 조회 코드
├── b-mcp/                                     # 방법 b: MCP
│   ├── opencode.json                          # mcp.glossary = ["python", "server.py"]
│   ├── server.py                              # stdio MCP 서버, 도구 lookup_term
│   └── glossary.json
└── c-plugin/                                  # 방법 c: 플러그인
    ├── .opencode/plugins/glossary.js          # tool() 로 team_glossary 등록
    └── glossary.json
```

용어 사전(`glossary.json`)에는 이 팀만의 값이 들어 있어서(예: 카나리 = 전체 트래픽의 5% 에 30분) 모델이 **추측으로는 맞힐 수 없습니다.**
도구/스킬을 실제로 썼는지 답에 `5%`, `30분` 이 들어 있는지로 알 수 있습니다.

## 따라 하기

> 평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 `-m opencode/big-pickle` 같은 무료 모델을 지정하세요.
> Linux 에서 `python` 명령이 없으면 `python3`로 바꾸세요. (`b-mcp/opencode.json` 의 `command` 와 `SKILL.md` 안의 명령 모두)

같은 질문을 세 폴더에서 차례로 실행합니다.

PowerShell:

```powershell
cd examples\04-combined\x1-three-ways
cd a-skill;  opencode run --auto "우리 팀 용어 사전에서 '카나리'가 무슨 뜻인지 찾아서 알려 줘."; cd ..
cd b-mcp;    opencode run --auto "우리 팀 용어 사전에서 '카나리'가 무슨 뜻인지 찾아서 알려 줘."; cd ..
cd c-plugin; opencode run --auto "우리 팀 용어 사전에서 '카나리'가 무슨 뜻인지 찾아서 알려 줘."; cd ..
```

Linux (bash):

```bash
cd examples/04-combined/x1-three-ways
(cd a-skill  && opencode run --auto "우리 팀 용어 사전에서 '카나리'가 무슨 뜻인지 찾아서 알려 줘.")
(cd b-mcp    && opencode run --auto "우리 팀 용어 사전에서 '카나리'가 무슨 뜻인지 찾아서 알려 줘.")
(cd c-plugin && opencode run --auto "우리 팀 용어 사전에서 '카나리'가 무슨 뜻인지 찾아서 알려 줘.")
```

화면 모드(`opencode`)로 실행해도 됩니다. 폴더마다 **눈에 띄는 표시**가 다릅니다.

| 폴더 | 기대하는 transcript 표시 |
|---|---|
| a-skill | `→ Skill "team-glossary"` 다음에 스크립트 실행(`$ python .opencode/skills/...lookup.py "카나리"`) |
| b-mcp | `⚙ glossary_lookup_term {"term":"카나리"}` |
| c-plugin | `⚙ team_glossary {"term":"카나리"}` |

c-plugin 은 `.opencode/plugins/` 에 플러그인이 있어서 시작할 때 `@opencode-ai/plugin` 을 npm 에서 설치하려 합니다. 레지스트리에 닿지 않으면 **시작할 때마다 약 70초** 멈추고, 완전히 새 환경의 첫 시작은 약 130초까지 걸렸습니다. a-skill 과 b-mcp 폴더에는 플러그인이 없어 이런 멈춤이 눈에 띄지 않았습니다(설치 시도는 `.opencode/` 가 있는 a-skill 에서 일어납니다). 인터넷이 막혔다면 [P6](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러) 의 "패키지 미러" 참고.

자동 검증: `python check.py` (Linux: `python3 check.py`).

## 기대 결과

`check.py` 는 스크립트된 가짜 모델(정해진 순서로 도구를 호출하는 로컬 서버)로 세 방식을 실제 opencode 에 태워 같은 답이 나오는지 봅니다. 실제 출력(Linux):

```
[PASS] [스크립트] a: 스킬 로드 -> lookup.py 실행 -> 5% / 30분
[PASS] [스크립트] b: ⚙ glossary_lookup_term -> 5% / 30분
[PASS] [스크립트] c: ⚙ team_glossary -> 5% / 30분
INFO 스킬: 상시 134자 (이름+설명), 로드되면 본문 348자 추가
INFO MCP : 상시 263자 (도구 스키마)
INFO 플러그인: 상시 319자 (도구 스키마)
```

세 방식의 조회 결과는 똑같습니다.

```
카나리: 새 버전을 전체 트래픽의 5% 에만 30분간 내보내 에러율을 지켜본 뒤 100% 로 넓히는 배포 방식.
```

실제 모델로 돌린 transcript 는 이 문서를 쓰는 시점에 무료 모델 한도가 소진되어 **확인하지 못했습니다.** `python check.py --model` 로 확인하세요.
특히 a(스킬)는 모델이 스킬을 스스로 고르는 단계가 있어서, 모델에 따라 스킬 대신 추측으로 답할 수 있습니다. 그럴 땐 질문에 "team-glossary 스킬로" 를 덧붙이세요.

## 동작 원리

- **a. 스킬**: opencode 가 시작할 때 `SKILL.md` 의 `name`/`description` 만 모델에게 알려 줍니다. 질문이 description 과 맞으면 모델이 `skill` 도구로 본문을 불러오고(`→ Skill "team-glossary"`),
  본문의 절차대로 `bash` 도구로 `lookup.py` 를 실행합니다. 코드는 모델이 부른 **셸 명령**으로 실행됩니다. 스킬 폴더 안에 데이터(`glossary.json`)를 두면 폴더째 복사해 옮길 수 있습니다.
- **b. MCP**: opencode 가 `python server.py` 를 자식 프로세스로 띄우고 stdin/stdout 으로 JSON-RPC 를 주고받습니다. 도구는 `glossary_lookup_term`(`<서버>_<도구>`)으로 모델에게 노출됩니다.
  서버는 stdout 에 MCP 메시지만 써야 합니다.
- **c. 플러그인**: `tool()` 로 정의한 도구가 opencode 프로세스 안에서 실행됩니다. 이름은 접두사 없이 `team_glossary`.

## 직접 바꿔 보기

1. `a-skill/.opencode/skills/team-glossary/SKILL.md` 의 `description` 에서 "온콜" 을 지우고 "온콜이 뭐야?" 라고 물어보세요. 스킬이 안 불리는 경우가 늘어납니다 - 스킬은 description 이 곧 트리거입니다.
2. 세 폴더의 `glossary.json` 중 하나만 고쳐 보세요. 세 방식의 답이 달라집니다(각자 사본을 갖기 때문). `check.py` 는 세 파일이 같은지 확인합니다.
3. 도구를 하나 더 만든다고 상상하고 b 와 c 에서 컨텍스트 글자 수가 얼마나 늘지 세어 보세요.

## 주의할 점 / 문제 해결

- 스킬 방식은 **모델이 스킬을 불러야** 시작됩니다. 불리지 않았다면 transcript 에 `→ Skill` 줄이 없습니다.
- Windows 의 `bash` 도구는 PowerShell 5.1 입니다. `SKILL.md` 의 명령(`python ... "<용어>"`)은 PowerShell 과 bash 양쪽에서 같게 동작하도록 단순하게 썼습니다.
- b 의 `server.py` 는 Windows 기본 인코딩(cp949) 문제를 피하려고 `sys.stdout.reconfigure(encoding="utf-8")` 로 시작합니다.
- 세 폴더 중 `.opencode/` 가 있는 곳(a, c)은 첫 실행에 npm 자동 설치가 일어납니다. b 는 프로젝트에 `.opencode/` 가 없어 프로젝트 쪽 설치는 일어나지 않습니다.
