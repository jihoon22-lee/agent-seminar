# S5a description 한 줄이 스킬 사용 여부를 가른다

> 구성: 같은 스킬을 description 만 달리한 프로젝트 2개 | 난이도: ★☆☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: 스킬 (description 쓰는 법)

## 무엇을 보여 주나

스킬 본문은 처음부터 모델에게 보이지 않습니다. 모델은 **이름 + description + 파일 위치**만 보고 "이 스킬을 열어 볼까?"를 결정하고, 열기로 한 순간에야 본문을 읽습니다.
이 예제는 본문이 **글자 하나까지 똑같은** `team-glossary` 스킬을 막연한 description(`variant-bad`)과 구체적인 description(`variant-good`) 두 가지로 두고, 같은 질문에 실제 모델이 스킬을 여는 비율이 어떻게 달라지는지 측정합니다. 모델 출력은 매번 달라지므로 "3번 중 몇 번"으로 정직하게 보여 줍니다.

## 실무에서는

- 스킬이 늘어나면(10개, 20개) 모델이 가진 단서는 각 스킬의 description 한 줄뿐입니다. 잘 만든 스킬이 "안 불려서" 쓸모없어지는 가장 흔한 이유가 description 입니다.
- 팀 용어, 팀 규칙 같은 **모델이 원래 모르는 지식**일수록 스킬이 안 열리면 모델이 그럴듯한 거짓 답을 만들어 냅니다. 열렸는지를 눈으로 확인하는 습관이 필요합니다 (`→ Skill "…"` 표식).
- 스킬을 고친 뒤에는 "한 번 돌려 보니 되더라"가 아니라 같은 질문을 여러 번 돌려 비율로 확인합니다. 그리고 관련 없는 질문(대조군)에서 열리지 않는지도 같이 봅니다.

## 파일 구성

```
s5a-description-good-bad/
  README.md
  variant-bad/.opencode/skills/team-glossary/SKILL.md    description: "팀 업무에 도움을 줍니다."
  variant-good/.opencode/skills/team-glossary/SKILL.md   description: 무엇 + 언제 + 한국어 트리거 말
  show_prompt.py     두 변형에서 모델이 처음부터 받는 스킬 항목을 나란히 출력 (모델·인터넷 불필요)
  compare.py         같은 질문을 두 변형에 여러 번 보내 스킬이 열린 비율을 셈 (모델 호출)
  mock_llm.py        127.0.0.1 에서 도는 가짜 모델 서버 (opencode 가 보내는 요청을 기록)
  lab.py             임시 샌드박스를 만드는 공용 도우미
  check.py           자동 검증
```

두 변형은 **형제 폴더**입니다. 각자 자기 `.opencode/` 를 갖고, 서로의 스킬은 보이지 않습니다. 스킬 본문(`team-glossary` 는 가상의 팀 용어 5개: 블루문, 팔콘, RFC-lite, 그린데이, 핫포테이토)은 두 파일에서 완전히 같습니다. 모델이 원래 알 수 없는 용어를 골랐기 때문에, 스킬을 열지 않으면 답을 지어내거나 모른다고 해야 합니다.

**git 저장소를 따로 만들지 않습니다.** opencode 는 프로젝트 스킬을 "실행한 폴더에서 git 루트까지 **위로** 올라가며" 찾습니다. 옆 폴더는 보지 않으므로 형제 폴더끼리는 저절로 분리되고, 변형 폴더마다 `git init` 할 필요가 없습니다(저장소 안에 중첩 저장소를 만들면 오히려 서브모듈처럼 취급되어 곤란합니다). 대신 **상위 폴더에 `.opencode/skills/` 를 두면 두 변형이 모두 그 스킬을 물려받아** 비교가 오염됩니다. 그래서 `examples/` 아래 상위 폴더는 비워 둡니다. check.py 가 이 분리를 검사합니다.

> `.opencode/` 가 있는 폴더에서 처음 opencode 를 실행하면 `@opencode-ai/plugin` 이 npm 에서 `.opencode/` 안에 자동 설치됩니다(`package.json`, `node_modules/` 생성, git 제외). 레지스트리에 접근할 수 없으면 첫 실행이 약 70초 멈췄다가 계속됩니다. 레지스트리에 닿지 않으면 첫 실행만이 아니라 **시작할 때마다** 이렇게 멈춥니다. 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있습니다.

## 따라 하기

Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요. 평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 무료 모델 `-m opencode/big-pickle` 을 붙이세요.

### 1. 모델이 처음부터 받는 것 보기 (모델 불필요)

PowerShell:

```powershell
cd examples\01-skills\s5a-description-good-bad
python show_prompt.py
cd variant-bad;  opencode debug skill; cd ..
cd variant-good; opencode debug skill; cd ..
```

Linux bash:

```bash
cd examples/01-skills/s5a-description-good-bad
python3 show_prompt.py
(cd variant-bad && opencode debug skill)
(cd variant-good && opencode debug skill)
```

`opencode debug skill` 은 발견된 스킬의 이름, description, 위치, **본문(content)** 을 JSON 으로 보여 줍니다. 본문까지 나오지만 이것은 "opencode 가 읽은 것"이고 "모델이 받는 것"이 아닙니다. 모델이 받는 것은 `show_prompt.py` 가 보여 주는 `<available_skills>` 항목(이름·description·위치)이 전부입니다.

### 2. 직접 질문해 보기 (TUI)

1. `variant-bad` 폴더에서 `opencode` 를 실행하고 `우리 팀에서 쓰는 '블루문'이 정확히 뭐야?` 를 입력합니다. 대화 중에 `→ Skill "team-glossary"` 줄이 나오는지 보세요.
2. 종료하고 `variant-good` 폴더에서 같은 질문을 합니다.
3. 스킬이 열리면 답에 "분기 마지막 주 금요일의 코드 동결"이 들어갑니다. 열리지 않으면 모델이 지어낸 답이 나옵니다.

### 3. 비율 재기 (실제 모델 24번 호출, 수 분~수십 분)

PowerShell:

```powershell
python compare.py                                  # 프롬프트 4개 x 변형 2개 x 3회
python compare.py --runs 5 --prompts 1,2           # 일부만, 더 많이
python compare.py -m opencode/big-pickle           # 모델 지정 (기본값이 이 무료 모델)
```

Linux bash:

```bash
python3 compare.py
python3 compare.py --runs 5 --prompts 1,2
```

`compare.py` 는 스킬 폴더를 `proj-a`/`proj-b` 라는 중립적인 이름으로 복사해서 실행합니다. 모델이 `<location>` 경로의 `variant-good` 같은 폴더 이름을 힌트로 쓰지 못하게 하려는 것입니다. 스킬이 열렸는지는 모델의 말이 아니라 opencode 가 찍는 `→ Skill "team-glossary"` 표식으로 판정합니다.

### 4. 자동 검증

```bash
python3 ../../../tools/run_checks.py s5a            # 모델 없음 (가짜 모델 서버 사용)
python3 ../../../tools/run_checks.py s5a --model    # 실제 모델 2회 추가
```

## 기대 결과

`python show_prompt.py` (모델 호출 없이 매번 같은 결과):

```
===== variant-bad: 모델의 system 프롬프트 속 team-glossary 항목
<skill>
    <name>team-glossary</name>
    <description>팀 업무에 도움을 줍니다.</description>
    <location><예제 폴더>/variant-bad/.opencode/skills/team-glossary/SKILL.md</location>
  </skill>
  → 본문('TEAM-GLOSSARY-BODY')이 system 프롬프트에 들어 있는가: False

===== variant-good: 모델의 system 프롬프트 속 team-glossary 항목
<skill>
    <name>team-glossary</name>
    <description>팀 내부 용어·약어·코드네임(블루문, 팔콘, RFC-lite 등)의 뜻을 담은 사전. 사용자가 "팀 용어", "약어", "~가 뭐야", "무슨 뜻이야"처럼 이 팀에서만 쓰는 말의 의미를 물을 때, 또는 신규 팀원용 용어 정리를 요청할 때 사용한다.</description>
    <location><예제 폴더>/variant-good/.opencode/skills/team-glossary/SKILL.md</location>
  </skill>
  → 본문('TEAM-GLOSSARY-BODY')이 system 프롬프트에 들어 있는가: False
```

`opencode debug skill` (variant-good 폴더에서, `content` 는 길어서 줄임). 같은 이름의 내장 스킬 `customize-opencode` 도 항상 함께 나옵니다.

```json
{
  "name": "team-glossary",
  "description": "팀 내부 용어·약어·코드네임(블루문, 팔콘, RFC-lite 등)의 뜻을 담은 사전. 사용자가 \"팀 용어\", \"약어\", \"~가 뭐야\", \"무슨 뜻이야\"처럼 이 팀에서만 쓰는 말의 의미를 물을 때, 또는 신규 팀원용 용어 정리를 요청할 때 사용한다.",
  "location": "<예제 폴더>/variant-good/.opencode/skills/team-glossary/SKILL.md",
  "content": "\n# 팀 용어 사전 (TEAM-GLOSSARY-BODY)\n\n이 팀에서만 쓰는 용어입니다. 질문에 답할 때는  …"
}
```

### 실제 모델로 잰 비율

**이 저장소를 만들 때는 측정하지 못했습니다 (미검증).** 측정 시도 때 무료 모델(`opencode/big-pickle`)이 `Free usage limit reached` 오류를 내며 재시도만 반복했고(`opencode run` 이 종료되지 않음), 단순한 한 단어 프롬프트도 240초 안에 끝나지 않았습니다. 그래서 "bad 는 몇 번 중 몇 번, good 은 몇 번 중 몇 번" 같은 숫자를 이 문서에 적지 않습니다. 모델이 정상일 때 `python compare.py` 를 실행하면 아래 모양의 표가 나옵니다 (숫자는 예시가 아니라 형식입니다).

```
== 결과 (모델 …, 칸마다 3회) : 스킬이 열린 횟수 / 실행 횟수
프롬프트          variant-bad           variant-good
1 뭐야          ?/3                   ?/3
2 약어          ?/3                   ?/3
3 팀 용어        ?/3                   ?/3
4 대조군         ?/3                   ?/3
```

**모델 없이 결정적으로 확인된 것**은 위 `show_prompt.py` 출력입니다. 두 변형이 모델에게 보내는 요청은 description 한 줄만 다르고, 본문은 어느 쪽에도 들어 있지 않습니다. `check.py` 가 이를 매번 검사합니다.

## 동작 원리

1. 시작할 때 opencode 가 스킬 폴더를 훑어 각 `SKILL.md` 의 frontmatter(`name`, `description`)와 본문을 읽습니다 (`opencode debug skill`).
2. 모델에게 보내는 요청의 system 프롬프트에는 스킬마다 `<name>`, `<description>`, `<location>` 만 들어갑니다. 본문은 없습니다. 같은 요청에는 `skill` 도구도 들어 있습니다.
3. 모델은 질문과 각 description 을 견주어 `skill` 도구를 `name` 으로 호출할지 정합니다. 호출하면 그 결과로 본문이 대화에 들어오고 화면에는 `→ Skill "이름"` 이 찍힙니다. 호출하지 않으면 본문은 끝까지 모델에게 보이지 않습니다.
4. `description` 이 아예 없는 스킬은 이 목록에서 빠집니다 (S5b 참고).

그래서 모델의 판단 재료는 **이름, description, 위치 경로** 세 가지입니다. "description 만"이라고 줄여 말하지만, 위치 경로에 들어 있는 폴더 이름도 모델에게 보인다는 점은 기억하세요.

## description 쓰기 체크리스트

1. **무엇 + 언제를 한 쌍으로.** "팀 용어 사전이다" (무엇) + "사용자가 …을 물을 때 사용한다" (언제). 무엇만 있으면 모델은 지금이 그때인지 알 수 없습니다.
2. **사용자가 실제로 칠 말을 그대로 넣기.** 한국어로 물을 사용자를 위해 `"팀 용어"`, `"약어"`, `"~가 뭐야"`, `"무슨 뜻이야"` 처럼 따옴표 붙은 표현을 적습니다. 영어 description 하나로는 한국어 질문과 잘 만나지 못할 수 있습니다.
3. **고유한 단어를 직접 적기.** 코드네임, 파일 이름, 명령어(`블루문`, `팔콘`, `RFC-lite`)를 예로 넣으면 질문에 같은 단어가 나왔을 때 연결됩니다.
4. **범위를 좁히는 말도 쓰기.** "이 팀에서만 쓰는 말", "일반 개념 설명에는 쓰지 않는다"처럼 쓰면 관련 없는 질문에서 열리는 일(과잉 사용)을 줄입니다. 스킬이 많을수록 중요합니다.
5. **본문에만 쓰지 않기.** "이럴 때 쓴다"를 본문에만 적으면 소용없습니다. 본문은 열린 뒤에야 보입니다.
6. **이름도 단서입니다.** `helper`, `utils` 보다 `team-glossary`. 이름과 description 이 서로 같은 방향을 가리키게 하세요.
7. **한두 문장으로.** 이 예제의 good 은 약 190자입니다. 길게 늘어놓는다고 더 잘 열리는 것은 아닙니다 (이 예제는 길이의 영향을 따로 시험하지 않았습니다).
8. **고치면 반드시 다시 재기.** 같은 질문을 3~5번, 그리고 관련 없는 질문(대조군) 한 개를 같이 돌려서 비율을 봅니다. 한 번 성공했다고 끝내지 마세요.
9. **그래도 안 열리면.** 사용자가 `team-glossary 스킬로 …` 처럼 이름을 직접 말하면 열립니다. 항상 열려야 하는 규칙이라면 스킬 대신 `AGENTS.md`/`instructions` 에 넣는 편이 맞습니다.

## 직접 바꿔 보기

1. `variant-bad` 의 description 을 한 단계씩 고쳐 보세요. 예) 먼저 "팀 용어 사전입니다."(무엇만) → 그다음 "팀 용어를 물을 때 사용합니다."(언제만). 어느 단계에서 열리기 시작하는지 `compare.py --variants variant-bad --runs 5` 로 재 보세요.
2. `variant-good` 의 description 에서 `블루문, 팔콘, RFC-lite` 예시를 지우면 3번 질문(`팀 용어 3개 정리해 줘`)과 1·2번 질문의 열림 비율이 어떻게 달라지는지 보세요.
3. 대조군 질문(4번)을 `"약어 정리 방법 알려줘"` 처럼 좀 더 헷갈리는 질문으로 바꿔서 good description 이 과잉으로 열리는지 확인해 보세요.

## 주의할 점 / 문제 해결

- **결과는 모델과 시점에 따라 다릅니다.** 같은 모델도 날마다 다르게 나올 수 있으므로, 숫자 하나보다 여러 번 돌린 비율을 보세요. 이 문서는 "good 이 bad 보다 더 자주 열린다"는 결과를 보장하지 않습니다. 직접 재 보고 판단하세요.
- **무료 모델은 속도·쿼터 제한이 있습니다.** 쿼터가 바닥나면 `opencode run` 이 끝나지 않고 재시도만 합니다. `compare.py` 는 시간 초과나 쿼터 오류를 `n/a` 로 세고 비율 계산에서 뺍니다. 24번 호출이라 오래 걸리므로 먼저 `--runs 1 --prompts 1` 로 동작을 확인하세요.
- **스크립트에서 `opencode run` 을 띄울 때 `PWD`.** `opencode run` 은 프로세스의 현재 폴더가 아니라 환경변수 `PWD` 를 작업 폴더로 삼는 것으로 관찰됩니다(Linux). Python 의 `subprocess.run(cwd=...)` 만 쓰면 부모 폴더의 스킬이 보입니다. `lab.py` 가 `PWD` 도 함께 맞춥니다.
- **description 을 고친 뒤에는 opencode 를 다시 시작하세요.** 스킬은 시작할 때 한 번 읽습니다.
- **YAML 함정.** description 에 `: `(콜론+공백)이나 ` #` 이 들어가면 YAML 로 잘못 해석될 수 있습니다. 필요하면 큰따옴표로 감싸세요. 이 예제의 good description 은 `"팀 용어"` 처럼 큰따옴표가 중간에 있지만 일반 문자열로 잘 읽힙니다 (`debug skill` 로 확인).
