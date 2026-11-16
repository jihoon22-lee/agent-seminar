# S2c ADR 스킬: 템플릿과 예시를 곁들인 스킬

> 구성: SKILL.md + templates/ + examples/ | 난이도: ★★☆ | 필요: opencode 1.19.5, Python 3.10+, git | 슬라이드: 스킬 — 템플릿·예시 파일 동봉

## 무엇을 보여 주나

스킬 폴더에는 `SKILL.md` 말고도 **템플릿**(빈 양식)과 **예시**(잘 쓴 완성본)를 함께 넣을 수 있다. 에이전트는 템플릿으로 구조를 맞추고, 예시로 문체와 상세 수준을 가늠한다.
이 예제는 "메시지 큐로 Kafka 대신 RabbitMQ를 쓰기로 한 결정"을 ADR(Architecture Decision Record, 아키텍처 결정 기록)로 남기고, 기존 파일 번호를 보고 다음 번호(`0002`)로 `docs/adr/0002-<slug>.md`를 만든다.

## 실무에서는

- **결정의 이유가 사라지는 문제**: 반 년 뒤 "왜 Kafka가 아니라 RabbitMQ였지?"를 아는 사람이 팀을 떠나 있다. ADR은 채팅과 회의록에 흩어지는 결정을 저장소 안의 한 파일로 남긴다.
- **회의 직후 기록**: 회의에서 정한 내용을 한두 문장으로 불러 주면 에이전트가 맥락, 대안, 결과가 있는 문서 형태로 정리한다. 사람은 `확인 필요`와 사실 관계만 고친다.
- **신규 팀원 온보딩**: `docs/adr/`를 번호순으로 읽으면 시스템이 왜 지금 모양인지 이해된다.
- **번호 규칙을 사람이 외우지 않아도 된다**: "다음 번호가 몇이었지?"를 에이전트가 폴더를 보고 정한다. 동시에 두 사람이 쓰면 번호가 겹칠 수 있으므로 PR에서 병합 전에 확인하는 습관은 그대로 필요하다.
- **PR에 ADR을 같이 올리기**: 아키텍처를 바꾸는 PR에는 ADR 파일이 함께 있어야 한다는 규칙을 팀이 정하면, 리뷰어가 코드와 이유를 한 번에 본다.

## 파일 구성

```
s2c-adr/
├── README.md
├── check.py                                           자동 검증
├── prepare.py                                         ADR 하나가 이미 있는 프로젝트 sandbox/ 생성
├── .gitignore                                         docs/adr/ 제외 (이 폴더에서 바로 실행했을 때 생기는 생성물)
└── .opencode/skills/adr/
    ├── SKILL.md                                       절차: 번호 정하기 → 템플릿 읽기 → (조건부) 예시 읽기 → 쓰기
    ├── templates/adr-template.md                      빈 양식 (맥락 / 결정 / 대안 / 결과)
    └── examples/0001-use-postgresql-for-order-store.md  잘 쓴 ADR 예시 (같은 문체로 쓰게 하는 기준)
```

`prepare.py`가 만드는 `sandbox/`(git에는 올라가지 않음):

```
sandbox/
├── docs/adr/0001-use-postgresql-for-order-store.md    이미 있는 ADR (스킬의 예시와 같은 파일)
├── .opencode/                                         스킬 복사본
└── README.md
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 `-m opencode/big-pickle`(무료 모델)을 붙이세요.

1. 샘플 프로젝트를 만든다.

   PowerShell:
   ```powershell
   cd examples\01-skills\s2c-adr
   python prepare.py
   cd sandbox
   ```

   Linux bash (`python` 명령이 없으면 `python3`로 바꾸세요):
   ```bash
   cd examples/01-skills/s2c-adr
   python3 prepare.py
   cd sandbox
   ```

2. opencode를 실행하고 요청한다.

   ```
   opencode
   ```

   ```
   메시지 큐로 Kafka 대신 RabbitMQ를 쓰기로 한 결정을 ADR로 남겨줘
   ```

   한 번에 실행하려면 `opencode run "메시지 큐로 Kafka 대신 RabbitMQ를 쓰기로 한 결정을 ADR로 남겨줘"` (무료 모델: `opencode run -m opencode/big-pickle --auto "..."`).

3. 결과를 확인한다.

   PowerShell: `Get-ChildItem docs\adr` 후 `Get-Content docs\adr\0002-*.md`
   Linux bash: `ls docs/adr` 후 `cat docs/adr/0002-*.md`

## 기대 결과

**실제 모델 실행 결과는 이 문서에 싣지 못했다.** 모델 확인을 시도했을 때 무료 모델 응답이 오지 않았다(과부하, 이후 사용량 소진). 그래서 `docs/adr/0002-<slug>.md`가 실제로 만들어지는지, 번호를 `0002`로 정하는지는 **미검증**이다. `python check.py --model`이 다음을 확인하도록 작성되어 있다: 스킬 로드, `0002-<영문 slug>.md` 생성, 제목 줄 `# 0002. `, 네 섹션, RabbitMQ와 Kafka 언급, `상태: Accepted`와 날짜 형식, "나쁜 점" 비어 있지 않음, 기존 `0001` 불변, `adr-template.md` 읽기 기록.

모델 없이 확인된 것(`python check.py`, Linux와 Windows에서 통과)은 다음과 같다.

- `prepare.py`가 만든 `sandbox/docs/adr/`에 `0001-use-postgresql-for-order-store.md`가 하나 있다(다음 번호 `0002`의 근거).
- 가짜 LLM 서버로 본 모델 요청: 시스템 프롬프트에는 이름과 description만 있고, `skill` 도구 결과에 본문과 `templates/adr-template.md`, `examples/0001-...md`의 경로 목록이 들어온다. 템플릿을 `read`하면 그 내용(`## 맥락` 등)이 전달된다.
- 시스템 프롬프트의 환경 정보에 `Today's date`가 있어서, 모델이 날짜를 얻으려고 셸 명령을 실행할 필요가 없다.

## 동작 원리

1. **선택**: description에 "ADR로 남겨줘", "결정을 기록해줘" 같은 문구가 있어 요청과 맞고, 모델이 스킬을 불러온다(`→ Skill "adr"`).
2. **번호 정하기**: 본문 1단계가 "`docs/adr/`의 파일 이름을 나열하고 가장 큰 번호에 1을 더하라"고 한다. 모델이 폴더를 읽고 `0001`을 확인한 뒤 `0002`를 쓴다. 번호 규칙을 코드로 구현하지 않고 **문장으로 지시**한 것이다. 더 엄격해야 하면 이 부분을 스크립트로 바꾸는 방법도 있다(스크립트를 쓰는 스킬 예제 참고).
3. **템플릿 읽기**: 본문 2단계가 `templates/adr-template.md`를 읽으라고 한다. 모델이 `Read`로 파일을 열고(`→ Read .../adr-template.md`) 구조(맥락 / 결정 / 대안 / 결과)를 그대로 따른다.
4. **예시는 조건부로**: 3단계는 "처음 쓰는 ADR이거나 상세 수준이 가늠되지 않을 때만 예시를 읽어라"고 한다. `sandbox/`에는 이미 ADR이 있으므로 예시 파일을 읽지 않아도 된다. 프로젝트에 ADR이 하나도 없는 새 저장소라면 예시를 읽도록 지시되어 있다(이 경우는 실행해 보지 않았다).
5. **사실 지어내지 않기**: 본문의 내용 규칙 때문에, 프롬프트에 없는 트래픽 수치나 일정은 `확인 필요`로 남는다.

### 템플릿과 예시는 무엇이 다른가

- **템플릿**은 *구조*를 정한다. 어떤 절이 어떤 순서로 있는가.
- **예시**는 *수준*을 정한다. 맥락을 몇 줄로 쓰는가, 대안 표를 어떻게 채우는가, 나쁜 점을 얼마나 솔직하게 적는가.
- 둘 다 `SKILL.md` 본문이 아니라 별도 파일이라, 쓰는 순간에만 대화에 올라온다.

## 직접 바꿔 보기

- `templates/adr-template.md`에 `## 위험` 절을 추가하고 `prepare.py`를 다시 실행한 뒤(스킬이 sandbox로 복사된다) 같은 요청을 해 보자. 새 ADR에 절이 생긴다.
- 한 번 더 `"로그 저장소로 Elasticsearch 대신 Loki를 쓰기로 했어. ADR로 남겨줘"`를 같은 `sandbox/`에서 요청해 보자. 번호가 `0003`이 되는지 확인한다.
- 이전 결정을 뒤집는 요청(예: "RabbitMQ 결정을 취소하고 Kafka로 가기로 했어")을 해 보자. SKILL.md의 `Superseded by` 규칙대로 이전 ADR의 상태 줄만 바뀌는지 본다.

## 주의할 점 / 문제 해결

- **생성된 ADR은 git에 올라가지 않는다.** 샘플은 `sandbox/`에서만 만들고, 이 폴더에서 바로 실행했을 때를 대비해 `.gitignore`가 `docs/adr/`를 제외한다. 실제 프로젝트에서는 ADR을 커밋해야 하므로 이 줄은 넣지 않는다.
- **번호가 겹칠 수 있다.** 두 사람이 같은 번호로 ADR을 만들었다면 병합 때 이름이 충돌한다. 한 명이 번호를 올려 파일 이름과 제목 줄(`# 0003. ...`)을 같이 바꾼다.
- **`sandbox/` 밖에서 실행하면** `docs/adr/`가 비어 있으므로 `0001`로 만든다(이 경우 `git status`에는 `.gitignore` 덕분에 보이지 않는다).
- **`.opencode/`가 있는 폴더에서 처음 실행하면** opencode가 `.opencode/` 안에 `package.json`, `node_modules/`, `.gitignore`를 자동으로 만든다(`@opencode-ai/plugin` 설치). 인터넷이나 패키지 미러에 접근할 수 없으면 첫 시작이 약 1분 이상 멈춘 것처럼 보일 수 있다.
- **모델이 내용을 채우는 방식**: 사용자가 말한 이유가 적을수록 모델은 일반적인 장단점으로 채운다. 실제 팀의 사정(트래픽, 인력, 운영 경험)을 프롬프트에 한두 문장 더 주면 훨씬 쓸모 있는 ADR이 된다.
