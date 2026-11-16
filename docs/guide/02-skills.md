# 2. 스킬: 필요할 때 꺼내 보는 업무 매뉴얼

이 문서는 세미나 4장 "스킬"을 글로 옮긴 것입니다. 스킬이 무엇이고 어디에 두는지, 모델이 무엇을 보는지, 잘 불리는 description을 어떻게 쓰는지, `SKILL.md` 한 장에서 스크립트와 산출물까지 키워 가는 4단계, 수동 전용으로 만드는 법, 팀에 나눠 주는 법을 다룹니다.
모든 내용은 **opencode 1.19.5** 기준입니다.

관련 예제: [S1a~S1c](../../examples/01-skills/) (1단계) · [S2a~S2c](../../examples/01-skills/) (2단계) · [S3a~S3c](../../examples/01-skills/) (3단계) · [S4a~S4b](../../examples/01-skills/) (4단계) · [S5a description](../../examples/01-skills/s5a-description-good-bad/) · [S5b 수동 전용](../../examples/01-skills/s5b-manual-and-permission/) · [S5c 범위와 배포](../../examples/01-skills/s5c-scope-global-project/)

## 스킬이란

폴더 하나에 `SKILL.md`가 있으면 스킬입니다. `SKILL.md`는 머리말(`name`, `description`)과 본문으로 이루어진 Markdown 파일입니다.

```markdown
---
name: log-analysis
description: 애플리케이션 로그 파일(*.log)을 분석해 에러 급증 구간과 원인 후보를 찾는다. "로그 분석", "에러 급증", "장애 원인 찾아줘" 같은 요청에 사용한다.
---

# 로그 분석 스킬
...
```

(위 예는 [S3a](../../examples/01-skills/s3a-log-analysis/)의 머리말을 줄인 것입니다.)

스킬은 **저절로 실행되지 않습니다.** 모델이 description을 보고 "이 스킬을 열어 볼까?"를 판단하거나, 사용자가 직접 부릅니다. "세션이 끝나면 자동 실행된다"는 식의 기대는 스킬이 아니라 플러그인의 일입니다. ([4장](04-plugins.md))

## 스킬을 두는 곳

| 위치 | 범위 |
|---|---|
| `.opencode/skills/<이름>/SKILL.md` | 이 프로젝트 |
| `~/.config/opencode/skills/` (Windows: `%USERPROFILE%\.config\opencode\skills\`) | 내 PC 전체 |
| `"skills": {"paths": [...]}` | 팀 공용 폴더 |
| `"skills": {"urls": [...]}` | 정적 웹 서버 |
| `~/.claude/skills`, `~/.agents/skills` | 다른 에이전트와 공유하는 위치. 외부 스킬로 읽음 |

프로젝트 스킬은 실행한 폴더에서 git 루트까지 **위로 올라가며** 만나는 모든 `.opencode/skills/`에서 찾습니다. 모노레포에서는 패키지 층과 루트 층의 스킬이 합쳐집니다. 옆 폴더는 보지 않습니다.

opencode 1.19.5에는 `customize-opencode`라는 내장 스킬도 항상 함께 나옵니다.

## 모델이 보는 것

모델은 처음에 스킬마다 **이름, description, 위치(경로)** 만 받습니다. 시스템 프롬프트의 `<available_skills>` 블록입니다. 본문은 들어 있지 않습니다.

```
<skill>
    <name>team-glossary</name>
    <description>팀 내부 용어·약어·코드네임(블루문, 팔콘, RFC-lite 등)의 뜻을 담은 사전. ...</description>
    <location><예제 폴더>/variant-good/.opencode/skills/team-glossary/SKILL.md</location>
  </skill>
```

모델이 내장 `skill` 도구로 스킬을 열면 그제야 다음이 대화에 들어옵니다.

1. `SKILL.md` 본문
2. `Base directory for this skill: <스킬 폴더의 절대 경로>`
3. "Relative paths in this skill (e.g., scripts/, references/) are relative to this base directory."라는 안내
4. 스킬 폴더 안의 파일 목록 `<skill_files>`. **일부만 뽑은 표본**입니다.

화면에는 `→ Skill "이름"` 줄이 찍힙니다. 이 줄이 "스킬이 열렸다"는 표식입니다.

여기서 나오는 실무 규칙은 이렇습니다.

- 위치 경로도 모델에게 보입니다. 폴더 이름도 일종의 힌트이므로 `helper`보다 `team-glossary`처럼 의미 있게 짓습니다.
- 본문에는 "어떤 파일이 있다"보다 **"언제 어떤 파일을 읽어라"** 를 씁니다. 파일 목록은 표본일 뿐이고, 어느 요청에 어느 파일인지는 알려 주지 않기 때문입니다.
- `opencode debug skill`은 **opencode가 읽은 것**(이름, description, 위치, 본문)을 보여 줍니다. 모델이 받는 것은 이름, description, 위치뿐입니다. 둘을 헷갈리지 마세요. `permission.skill`로 deny한 스킬도 `debug skill`에는 나옵니다.
- 스킬은 **시작할 때 한 번** 읽습니다. 스킬 파일을 고치거나 `git pull`한 뒤에는 opencode를 다시 시작하세요.

## 잘 불리는 description 쓰기

스킬이 늘어나면(10개, 20개) 모델이 가진 단서는 각 스킬의 description 한 줄뿐입니다. 잘 만든 스킬이 "안 불려서" 쓸모없어지는 가장 흔한 이유가 description입니다. [S5a](../../examples/01-skills/s5a-description-good-bad/)는 본문이 글자 하나까지 같은 스킬을 막연한 description과 구체적인 description 두 가지로 두고 비교합니다.

| | description |
|---|---|
| bad | `팀 업무에 도움을 줍니다.` |
| good | `팀 내부 용어·약어·코드네임(블루문, 팔콘, RFC-lite 등)의 뜻을 담은 사전. 사용자가 "팀 용어", "약어", "~가 뭐야", "무슨 뜻이야"처럼 이 팀에서만 쓰는 말의 의미를 물을 때, 또는 신규 팀원용 용어 정리를 요청할 때 사용한다.` |

체크리스트입니다.

1. **무엇 + 언제를 한 쌍으로** 씁니다. "무엇"만 있으면 모델은 지금이 그때인지 알 수 없습니다.
2. **사용자가 실제로 칠 말을 따옴표로** 넣습니다. 한국어 사용자라면 한국어 표현을 적습니다. 영어 description 하나로는 한국어 질문과 잘 만나지 못할 수 있습니다. ([S3a](../../examples/01-skills/s3a-log-analysis/)는 한국어 문구에 영어 한 문장을 덧붙였습니다.)
3. **고유한 단어를 직접** 적습니다. 코드네임, 파일 이름, 명령어를 예로 넣으면 같은 단어가 질문에 나왔을 때 연결됩니다.
4. **범위를 좁히는 말**도 씁니다. "이 팀에서만 쓰는 말"처럼 쓰면 관련 없는 질문에서 열리는 과잉 사용이 줄어듭니다.
5. **본문에만 쓰지 않습니다.** "이럴 때 쓴다"를 본문에만 적으면 소용없습니다. 본문은 열린 뒤에야 보입니다.
6. **한두 문장**으로 씁니다. 길게 늘어놓는다고 더 잘 열린다는 보장은 없습니다.
7. **고치면 반드시 다시 잽니다.** 같은 질문을 3~5번, 그리고 관련 없는 질문(대조군) 한 개를 같이 돌려서 비율을 봅니다. 한 번 성공했다고 끝내지 마세요.
8. 그래도 안 열리면 사용자가 `team-glossary 스킬로 ...`처럼 이름을 직접 말하면 열립니다. **항상** 적용되어야 하는 규칙이라면 스킬 대신 `AGENTS.md`나 `instructions`에 넣는 편이 맞습니다.

YAML 함정도 있습니다. description에 `: `(콜론과 공백)이나 ` #`이 들어가면 YAML로 잘못 해석될 수 있습니다. 필요하면 큰따옴표로 감싸세요.

모델이 스킬을 열었는지는 모델의 말이 아니라 `→ Skill "이름"` 표식으로 판정합니다. 이 저장소를 만들 때는 무료 모델 한도 때문에 S5a의 실제 열림 비율을 측정하지 못했습니다(미검증). 직접 `compare.py`로 재 보세요.

## 스킬을 키워 가는 4단계

필요한 만큼만 키웁니다.

| 단계 | 구성 | 예제 | 언제 |
|---|---|---|---|
| 1 | `SKILL.md` 하나 | [S1a 커밋 메시지](../../examples/01-skills/s1a-commit-message/) · [S1b 코드 리뷰](../../examples/01-skills/s1b-code-review/) · [S1c 포스트모템](../../examples/01-skills/s1c-postmortem/) | 규칙과 절차를 글로 설명하면 충분할 때 |
| 2 | + 참고 문서, 템플릿 | [S2a 작업 기록](../../examples/01-skills/s2a-workthrough/) · [S2b API 설계](../../examples/01-skills/s2b-api-design/) · [S2c ADR](../../examples/01-skills/s2c-adr/) | 내용이 길어서 필요한 부분만 읽히고 싶을 때 |
| 3 | + 스크립트 | [S3a 로그 분석](../../examples/01-skills/s3a-log-analysis/) · [S3b 릴리스 노트](../../examples/01-skills/s3b-release-notes/) · [S3c 비밀값 검사](../../examples/01-skills/s3c-secret-scan/) | 계산, 집계, 파싱처럼 매번 같아야 하는 일 |
| 4 | + 결과물 생성 | [S4a HTML 리포트](../../examples/01-skills/s4a-html-report/) · [S4b 구조 다이어그램](../../examples/01-skills/s4b-mermaid-diagram/) | 사람이 볼 파일을 만들어야 할 때 |

### 1단계: SKILL.md 하나

규칙을 매번 프롬프트에 붙여 넣는 대신 한 번 적어 둡니다. S1a는 "커밋 메시지는 이렇게 쓴다"를 적어 두었고, 프롬프트에 스킬 이름을 쓰지 않았는데도 모델이 스킬을 골랐습니다. 번호는 프롬프트에 없었지만 본문이 "브랜치 이름에서 찾아라"고 했기 때문에 모델이 `git branch --show-current`를 실행해 `Refs: #42`를 만들었습니다. **본문의 작업 순서가 그대로 도구 호출 순서가 됩니다.** 스킬은 모델에게 일하는 순서를 가르칩니다.

S1b처럼 출력 형식(심각도 표 + 요약)까지 정해 두면 누가 시켜도 같은 모양의 결과가 나옵니다. S1c는 한 스킬이 대화형 모드와 문서 모드를 모두 지원하는 예입니다. 모드를 고르는 규칙도 `SKILL.md`에 적습니다.

규칙을 지키지 않는 출력이 나오면 어긴 출력을 보여 주며 "SKILL.md의 규칙을 다시 읽고 고쳐 줘"라고 하면 대개 고칩니다. 근본 해결은 규칙 문장을 예시와 함께 더 구체적으로 쓰는 것입니다.

### 2단계: 참고 문서와 템플릿 (점진적 공개)

본문이 길면 열 때마다 모두 대화에 올라옵니다. 쓰지 않을 내용은 별도 파일로 빼고, 본문에는 **언제 어느 파일을 읽을지**만 적습니다.

- [S2b](../../examples/01-skills/s2b-api-design/)의 `SKILL.md`는 목차(라우터)입니다. "여러 건을 돌려주는 목록·검색 API가 있다 → `references/pagination.md`"처럼 표로 적고, 규칙 자체는 `references/`의 파일에 둡니다. "참고: references/ 폴더 참조" 같은 막연한 문장은 약합니다.
- [S2a](../../examples/01-skills/s2a-workthrough/)는 실제로 매일 쓰는 스킬을 옮긴 것입니다. 빈 양식 `TEMPLATE.md`는 문서를 쓰기 직전에, 완성 예시 `EXAMPLES.md`(11.8KB)는 사용자가 예시를 원할 때만 읽게 해서, 단순한 요청에서는 컨텍스트에 올라오지 않습니다.
- [S2c](../../examples/01-skills/s2c-adr/)는 **템플릿은 구조를, 예시는 수준을 정한다**는 점을 보여 줍니다. 번호 규칙(기존 파일을 보고 다음 번호)은 코드가 아니라 문장으로 지시했습니다.

참고 문서에는 **확인 가능한 규칙**을 두세요(S2b의 `pg1_` 커서 접두사, 기본 25건/최대 100건). 결과에 그 값이 나오면 문서를 읽었다는 증거가 됩니다.

모델이 보조 파일을 읽지 않고 쓰기도 합니다. 출력은 확률적이기 때문입니다. 그럴 때는 "TEMPLATE.md를 읽고 그 양식으로 써 줘"라고 하면 됩니다. 본문이 파일 이름과 읽을 조건을 분명히 적을수록 읽는 빈도가 올라갑니다.

### 3단계: 스크립트

규칙으로 정해진 일은 코드가 훨씬 잘합니다. **결정적인 일은 스크립트가, 판단과 설명은 모델이** 맡습니다.

- S3a: 수천 줄 로그를 스크립트가 훑어 약 200줄짜리 JSON 요약으로 줄입니다. 모델은 요약만 보고 해석합니다. 로그를 모델이 직접 읽으면 토큰이 크게 들고 매번 세는 방식이 달라져 숫자가 흔들립니다.
- S3b: 커밋 분류는 스크립트가, 사용자가 읽을 한국어 문장은 모델이 씁니다.
- S3c: 비밀값 검사는 스크립트가 하고 종료 코드로 결과를 알립니다. 모델은 "진짜 키 / 오탐"을 가려 설명합니다. 출력은 값을 마스킹해서 모델의 컨텍스트에도 값이 남지 않습니다.

#### 스크립트는 어떻게 찾나: base directory

스킬이 열릴 때 함께 오는 `Base directory for this skill: <절대 경로>` 줄이 열쇠입니다. `SKILL.md`에는 "스킬 폴더 기준 `scripts/summarize_log.py`"라고 쓰고, 모델이 그 경로를 앞에 붙여 실행합니다. 그래서 **절대 경로를 `SKILL.md`에 박을 필요가 없고**, 저장소를 어디에 clone해도 동작합니다.

- 작업 디렉터리(cwd)는 프로젝트 루트 그대로입니다. 그래서 데이터와 출력 경로는 **프로젝트 기준**, 스크립트와 템플릿은 **스킬 폴더 기준**입니다.
- 스크립트가 템플릿을 자기 위치(`Path(__file__)`)에서 찾게 하면 어느 디렉터리에서 실행해도 동작합니다. ([S4a](../../examples/01-skills/s4a-html-report/))

스크립트를 만들 때의 요령입니다.

| 스크립트 쪽 | SKILL.md 쪽 |
|---|---|
| 표준 라이브러리만. 설치 단계가 없어야 누구 PC에서나 돈다 | 실행할 명령을 그대로 적는다: `python <스킬 폴더>/scripts/x.py 인자` |
| 출력은 짧게. 원문 대신 요약, 필요하면 `--sample N` | "`python`이 없으면 `python3`" 한 줄 (Linux) |
| 종료 코드로 성공, 발견, 오류를 구분 (0 / 1 / 2) | `&&`, 파이프, `$변수` 없이 **한 줄** |
| `--help`를 친절하게. 모델도 읽는다 | "하지 말 것"을 쓴다: 원본 전체 읽기, 스크립트 고치기, 숫자 지어내기 |
| 네트워크 없이 동작. 결과물에도 외부 링크를 넣지 않는다 | |

**Windows 주의.** opencode 1.19.5의 `bash` 도구는 Windows에서 Git Bash가 설치되어 있어도 **Windows PowerShell 5.1**로 실행됩니다. `&&`, `export X=1`, `$APP_ENV`, `wc`, `head`, `2>/dev/null`이 모두 안 됩니다. 한 모델이 스스로 붙인 `wc -l`이 실패한 적도 있습니다. 그래서 `SKILL.md`에는 `python <스킬 폴더>/scripts/x.py 인자` 한 줄만 시키고, 셸 문법이 필요한 일은 스크립트 안으로 옮깁니다. 경로 구분자는 `\`로 와도 `/`로 바꿔 넘기면 Python이 처리합니다. 자세한 내용은 [5. 문제 해결](05-troubleshooting.md)의 Windows 절을 보세요.

날짜처럼 OS마다 명령이 다른 것은 두 가지를 모두 적어 둡니다. ([S2c](../../examples/01-skills/s2c-adr/)는 `date +%F`와 `Get-Date -Format yyyy-MM-dd`를 모두 적었습니다.)

스킬을 건너뛰고 바로 `grep`부터 하는 모델도 있습니다. 실패하면 안 되는 데모에서는 프롬프트에 스킬 이름을 직접 넣는 편이 안전합니다.

### 4단계: 결과물 생성

스킬이 만드는 결과가 텍스트 답변만은 아닙니다. 양식과 계산을 스크립트에 고정하고, 모델은 해석만 씁니다.

- S4a: CSV를 읽어 브라우저에서 더블클릭으로 열리는 HTML 한 파일을 만듭니다. 그래프는 파이썬이 만든 인라인 SVG이고 CDN, JS 라이브러리, 웹 폰트가 없어 인터넷 없이 열립니다. stdout의 JSON 요약이 모델이 인사이트를 쓰는 근거 숫자입니다.
- S4b: 파이썬 소스를 실행하지 않고 `ast`로 읽어 import 관계를 Mermaid 순서도로 만들고, 순환 import를 찾습니다. 정적 분석이라 동적 import는 보이지 않습니다.

모델에게 HTML과 차트를 매번 새로 짜게 하면 모양이 매번 다르고 숫자도 틀릴 수 있습니다.

## 수동 전용 스킬: permission으로 막고 사람이 부르기

배포 체크리스트나 야간 정리처럼 **사람이 "지금 해"라고 했을 때만** 돌아야 하는 스킬이 있습니다. [S5b](../../examples/01-skills/s5b-manual-and-permission/)가 1.19.5에서 통하는 방법과 통하지 않는 방법을 가짜 모델로 재현합니다.

| 방법 | 1.19.5에서 |
|---|---|
| 머리말 `disable-model-invocation: true` | **효과 없음.** 에러도 경고도 없다. `metadata`의 비슷한 플래그도 마찬가지. opencode는 머리말에서 `name`과 `description`만 의미 있게 읽는 것으로 관찰됨 |
| `permission.skill` `deny` | 모델 목록에서 사라지고, 억지로 불러도 호출이 거부된다. `--auto`로도 못 뚫는다 |
| `permission.skill` `ask` | TUI는 물어본다. `opencode run`은 `--auto`일 때만 허용 |
| 사람이 직접 부르기 | TUI에서 `/skills` 선택창, 또는 `opencode run --command 이름` (deny여도 동작) |

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": { "skill": { "*": "allow", "deploy-*": "deny" } }
}
```

- 키는 스킬 이름(와일드카드 가능), 값은 `allow` / `ask` / `deny`입니다.
- **마지막으로 일치한 규칙이 이깁니다.** `"*"`를 먼저, `"deploy-*"`를 나중에 씁니다. 거꾸로 쓰면 모든 스킬이 허용되어 deny가 무효가 됩니다.
- `deny`는 에이전트 단위로도 걸 수 있습니다. 에이전트 파일의 `permission`에 `deploy-*: allow`를 쓰면 그 에이전트(예제의 `release`)에서만 모델이 쓸 수 있습니다.
- 규칙이 없으면 기본값은 허용입니다.

사람이 부르는 길입니다.

PowerShell:
```powershell
opencode run --command deploy-checklist "프로덕션" "v2.3"
```
Linux bash:
```bash
opencode run --command deploy-checklist 프로덕션 v2.3
```

`--command`로 부르면 스킬 본문과 `Base directory` 안내와 인자가 **사용자 메시지**가 됩니다. 모델은 `skill` 도구를 쓰지 않으므로 `permission`의 deny에 영향을 받지 않습니다. TUI의 `/` 자동완성에는 스킬이 나오지 않고, 내장 명령 `/skills`가 모든 스킬을 검색하는 선택창을 엽니다. deny된 스킬도 이 창에 보입니다. 이 확인은 Linux의 TUI에서만 했습니다.

주의할 점입니다.

- `deny`해도 **사람은 부를 수 있습니다.** 접근 통제 수단이 아니라 "모델의 자율 호출을 막는 장치"입니다.
- `description`을 생략한 스킬은 모델 목록에서 빠집니다. 다만 이름을 아는 모델이 `skill` 도구로 부르면 로드되므로, "목록에서 숨기기"일 뿐 안전장치는 아닙니다.
- 모델이 실제로 받는 스킬 목록은 `debug skill`이 아니라 S5b의 `show_prompt.py`로 확인하세요.
- 실제 모델로 `--command`를 실행한 결과는 확인하지 못했습니다(무료 모델 한도). 위 결과는 가짜 모델로 얻은 것입니다.

## 팀에 나눠 주기: 경로, URL, 그리고 함정

[S5c](../../examples/01-skills/s5c-scope-global-project/)가 위치별 동작을 임시 샌드박스에서 하나씩 켜 보며 확인합니다.

| 방법 | 설정 | 배포 |
|---|---|---|
| 프로젝트 | `.opencode/skills/`에 넣고 코드와 함께 커밋 | clone하면 끝 |
| 팀 공용 저장소 | 각자 clone하고 `"skills": {"paths": ["~/team-skills"]}` | `git pull`이 곧 배포 (opencode 재시작 필요) |
| 정적 웹 서버 | `"skills": {"urls": ["http://.../skills/"]}` | 서버에 `index.json`과 파일을 올림 |

`skills.paths`는 각 폴더 아래의 `**/SKILL.md`를 재귀로 찾습니다. 분류용 하위 폴더를 자유롭게 둘 수 있습니다.

### 함정 1. 같은 이름은 경쟁합니다

같은 이름의 스킬이 두 곳에 있으면 이름 단위로 하나로 합쳐지고, 로그에 `duplicate skill name` 경고가 남습니다(`opencode debug skill --print-logs`). 순서상 보통은 프로젝트가 전역을, `skills.paths`가 프로젝트를 이기지만 **보장되지 않습니다.** 파일을 읽는 작업이 동시에 돌아 가끔 결과가 뒤집힙니다. 측정에서 "전역 vs 프로젝트"는 프로젝트 승이 51/53번, "프로젝트 vs `skills.paths`"는 `skills.paths`가 8/10번 이겼습니다. 같은 이름으로 덮어쓰기를 설계하지 말고, 이름을 고유하게 지으세요(`team-`, `my-` 접두사).

### 함정 2. `skills.paths`의 상대 경로

상대 경로는 **`opencode.json`이 있는 폴더가 아니라 opencode를 실행한 폴더** 기준입니다. `project/`에서 실행하면 `../team-skills`가 맞지만 하위 폴더에서 실행하면 `skill path not found` 경고만 남기고 공용 스킬이 사라집니다. 오류로 멈추지 않아서 더 알아채기 어렵습니다. 절대 경로나 `~/`를 쓰세요. 존재하지 않는 경로는 조용히 건너뜁니다.

### 함정 3. `skills.urls`

1.19.5에서 존재하고 동작합니다(로컬 서버로 확인했고 https나 인증이 필요한 서버는 시험하지 않았습니다).

```
http://127.0.0.1:8851/skills/index.json
  {"skills":[{"name":"remote-glossary","files":["SKILL.md","examples.md"],"version":"2"}]}
http://127.0.0.1:8851/skills/remote-glossary/SKILL.md     (files에 적은 파일마다 GET)
```

- 내려받은 파일은 캐시 폴더(`<XDG_CACHE_HOME>/opencode/skills/<name>/`)에 저장되고, 스킬의 location도 그 경로입니다.
- **`version`을 안 바꾸면 서버 내용이 바뀌어도 다시 받지 않습니다.** `index.json`의 `version` 문자열을 바꿔야 합니다.
- **시작할 때마다 `index.json`을 가져오려 하고, 실패하면 캐시가 있어도 그 URL의 스킬이 통째로 사라집니다.** 서버가 꺼져 있거나 오프라인이면 쓸 수 없습니다. 오프라인이 필요하면 `skills.paths` + git 저장소 방식이 안전합니다.
- `files`에 `SKILL.md`가 없으면 `skill entry missing SKILL.md` 경고와 함께 무시됩니다.

### 다른 도구의 스킬을 가져올 때

[S2a](../../examples/01-skills/s2a-workthrough/)는 실제 스킬을 opencode용으로 옮긴 예입니다. 본문에 통째로 들어 있던 템플릿을 별도 파일로 빼고, "세션이 끝나면 자동 실행된다"는 문장을 고치고, description에 한국어 요청 문구를 덧붙였습니다. 라이선스 파일과 바꾼 내용(`NOTICE.md`)을 폴더에 남겼습니다. 남의 스킬을 가져올 때의 예의입니다.

## 개발 체크리스트

스킬을 만들 때 순서대로 확인합니다.

- [ ] 격리해서 실험하고 있는가? ([1장](01-config.md)의 격리 절) 내 전역 스킬이 섞이면 "왜 되지?"를 구분할 수 없습니다.
- [ ] `opencode debug skill`에 이름, description, location이 나오는가?
- [ ] description이 "무엇 + 언제 + 사용자가 칠 말 + 고유 단어"를 담았는가?
- [ ] 이름이 다른 곳의 스킬과 겹치지 않는가? 폴더 이름이 의미 있는가?
- [ ] 긴 내용은 `references/`, `templates/`로 빼고, 본문에 "언제 어느 파일을 읽을지"를 적었는가?
- [ ] 스크립트 호출이 `python <스킬 폴더>/scripts/x.py 인자` **한 줄**인가? `python3` 안내가 있는가?
- [ ] 스크립트가 표준 라이브러리만 쓰고, UTF-8로 입출력하며, 종료 코드와 `--help`가 있는가?
- [ ] 스크립트가 PowerShell 5.1에서도 같은 한 줄로 도는가?
- [ ] 프롬프트에 스킬 이름을 넣지 않고도 `→ Skill "이름"`이 찍히는가? 3~5번 반복해 비율을 봤는가? 관련 없는 질문에서는 안 열리는가?
- [ ] 자동으로 쓰이면 안 되는 스킬은 `permission.skill`로 막았는가? (머리말 플래그는 쓰지 않았는가?)
- [ ] 고친 뒤 opencode를 다시 시작했는가?
- [ ] 예제에 쓰는 가짜 비밀값은 `demo-token-123` 같은 누가 봐도 가짜인 값인가, 아니면 실행 시점에 조립하는가? (토큰 모양 문자열을 커밋하면 push가 거절될 수 있습니다. [S3c](../../examples/01-skills/s3c-secret-scan/))

다음: [3. MCP](03-mcp.md)
