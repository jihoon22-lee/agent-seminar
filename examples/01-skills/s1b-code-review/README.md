# S1b 팀 코드 리뷰 스킬

> 구성: SKILL.md 한 장(스크립트 없음) + 리뷰 연습용 샘플 코드 | 난이도: ★☆☆ | 필요: opencode 1.19.5, Python 3.10+ | 슬라이드: 스킬 — 체크리스트를 스킬로

## 무엇을 보여 주나

"리뷰해줘"라고만 말하면 에이전트는 그때그때 눈에 띄는 것만 지적한다. 팀의 리뷰 체크리스트(이름, 에러 처리, 보안, 테스트, 로깅)와 출력 형식(심각도 표 + 요약)을 SKILL.md에 적어 두면, 같은 코드에 대해 매번 같은 관점·같은 모양의 리뷰가 나온다.
이 예제는 `sample/orders.py`에 일부러 결함을 심어 두고, 스킬이 그것을 얼마나 빠짐없이 찾는지 보여 준다.

## 실무에서는

- **리뷰어마다 보는 관점이 다를 때**: 어떤 리뷰어는 보안을, 어떤 리뷰어는 이름만 본다. 체크리스트를 스킬로 두면 사람 리뷰 전에 에이전트가 같은 기준으로 한 번 훑어, 사람은 설계와 맥락에 집중할 수 있다.
- **PR을 올리기 전 셀프 리뷰**: 작성자가 "리뷰해줘"를 먼저 실행해 치명 등급을 미리 고친다. 리뷰 왕복이 줄어든다.
- **기준 고정과 개선**: 사고가 나면 그 원인을 체크리스트 한 줄로 추가한다(예: "로그에 토큰이 남은 적이 있다" → 로깅 항목). 문서에 적어 두고 잊히는 대신, 다음 리뷰부터 자동으로 적용된다.
- **심각도 합의**: 치명/주의/제안의 기준(머지 가능 여부)을 표로 명시하면 "이건 막아야 하나요?"라는 논쟁이 줄어든다.

## 파일 구성

```
s1b-code-review/
├── README.md
├── check.py                                  자동 검증 (결함 재현, 스킬 발견, 선택적으로 모델 실행)
├── fake_llm.py                               가짜 LLM 서버. check.py 가 모델 없이 opencode 의 요청을 기록·재현하는 데 씀
├── sample/orders.py                          리뷰 대상: 결함 6개가 심어진 주문 모듈
└── .opencode/skills/code-review/
    └── SKILL.md                              체크리스트 + 심각도 기준 + 출력 형식
```

## 따라 하기

평소 쓰는 모델로 실행하면 됩니다. 모델 설정이 없다면 `-m opencode/big-pickle`(무료 모델)을 붙이세요.

1. 이 예제 폴더로 이동한다.

   PowerShell:
   ```powershell
   cd examples\01-skills\s1b-code-review
   opencode debug skill
   ```

   Linux bash:
   ```bash
   cd examples/01-skills/s1b-code-review
   opencode debug skill
   ```

   `code-review`가 목록에 보이면 된다.

2. opencode를 실행하고 입력한다.

   ```
   opencode
   ```

   ```
   sample/orders.py 리뷰해줘
   ```

   한 번에 실행하려면 `opencode run "sample/orders.py 리뷰해줘"` (무료 모델: `opencode run -m opencode/big-pickle --auto "sample/orders.py 리뷰해줘"`).

3. 아래 "정답지"와 비교한다.

### 정답지: `sample/orders.py`에 심어 둔 결함

| # | 위치 | 영역 | 등급 | 결함 |
| --- | --- | --- | --- | --- |
| 1 | `get_orders` (11행) | 보안 | 치명 | SQL을 f-string으로 조립한다. `customer`에 `x' OR '1'='1`을 넣으면 모든 고객의 주문이 조회된다(SQL 인젝션). |
| 2 | 상단 `PAYMENT_API_KEY` (5행) | 보안 | 치명 | 결제 API 키가 소스에 하드코딩되어 있다(예제 값은 가짜다). |
| 3 | `export_receipt` (15~18행) | 보안 | 치명 | `filename`에 `../escaped.txt`를 넣으면 `receipts/` 밖에 파일이 써진다(경로 탐색). |
| 4 | `proc` (27~28행) | 에러 처리 | 주의 | 맨 `except:` 뒤에 `pass`. 결제 실패가 조용히 사라진다. |
| 5 | `proc`, `c` | 이름 | 제안 | `proc`은 하는 일을 말해 주지 않고, `c`는 커서라는 사실을 말해 주지 않는다. |
| 6 | `proc` (22행) | 로깅 | 주의 | 카드 번호를 `print`로 출력한다. |
| 보조 | 파일 전체 | 테스트 | 주의 | 테스트가 하나도 없다(체크리스트 4번 항목). |
| 보너스 | `proc` (24~26행) | 정합성 | 치명/주의 | `paid = 1`을 커밋한 뒤에 결제를 호출한다. 결제가 실패해도 "결제 완료"로 남는다. 의도한 항목은 아니었지만 실제 실행에서 모델이 짚었다. |

`python check.py`는 1~3번 결함을 실제로 재현해 본다(SQL 인젝션으로 두 명의 주문이 모두 조회되는지, 경로 탐색으로 밖에 파일이 생기는지 등).

## 기대 결과

`opencode run`으로 `opencode/big-pickle` 모델에서 얻은 실제 출력이다(모델 출력은 매번 조금씩 다르다).

````
I'll load the code-review skill to follow the team's checklist.
| 심각도 | 위치 | 문제 | 제안 |
| --- | --- | --- | --- |
| 치명 | sample/orders.py:11 | `customer`를 f-string으로 넣어 SQL 실행 → SQL 인젝션 | `conn.execute("... WHERE customer = ?", (customer,))` 파라미터 바인딩 |
| 치명 | sample/orders.py:5 | 결제 API 키가 소스에 하드코딩됨 | 환경 변수/비밀 저장소로 옮기고 기존 키 폐기·재발급 |
| 치명 | sample/orders.py:16 | `filename`을 그대로 경로에 결합 → `../` 경로 탐색으로 임의 파일 쓰기 | `(RECEIPT_DIR / filename).resolve()` 후 `RECEIPT_DIR.resolve()` 하위인지 검사 |
| 치명 | sample/orders.py:22 | 카드 번호를 `print`로 남김 → 개인정보/결제정보 노출 | 카드 번호 마스킹 또는 로그에서 제외, `logging` 사용 |
| 치명 | sample/orders.py:24-26 | 결제 전에 `paid=1` 커밋 → `charge` 실패해도 결제 완료로 남아 데이터 오염 | `charge` 성공 후 커밋하고, 실패 시 롤백 |
| 주의 | sample/orders.py:27 | 맨 `except: pass`로 오류를 삼키고 기록도 없음 | 구체적 예외만 잡아 롤백 후 `logging.exception`으로 기록/재던짐 |
| 주의 | sample/orders.py:9-33 | 핵심 함수에 테스트가 없음(특히 보안·오류 처리) | 정상/경계값/오류 입력 케이스 테스트 추가(인젝션, 경로 탐색, 결제 실패) |
| 제안 | sample/orders.py:21 | `proc`는 의미 없는 이름이고 실제로는 결제 처리 | `process_payment` 등 동작을 드러내는 이름 |
| 제안 | sample/orders.py:10 | 커서 변수명 `c` | `cursor` 등 의미 있는 이름 |

## 요약
치명 5, 주의 2, 제안 2 — 현재 상태로는 머지 불가.
가장 먼저 `sample/orders.py:11`의 SQL 인젝션부터 파라미터 바인딩으로 고칠 것.


> build · big-pickle

→ Skill "code-review"
✱ Glob "**/sample/orders.py" 1 match
→ Read sample/orders.py
````

정답지 6개가 모두 나왔고, 스킬의 출력 형식(표 열 순서, 치명 → 주의 → 제안 정렬, `## 요약`)도 그대로 지켜졌다. 심각도 등급은 모델이 SKILL.md의 기준표를 보고 정한 것이라 정답지와 한 단계씩 다를 수 있다(카드 번호 로깅을 "치명"으로 올린 것처럼).

## 동작 원리

1. **발견**: 시작할 때 opencode는 `.opencode/skills/code-review/SKILL.md`의 `name`·`description`만 모델에게 알려 준다. description에는 "리뷰해줘", "코드 리뷰", "PR 리뷰" 같은 사용자가 실제로 치는 말을 넣어 두었다.
2. **로드**: "sample/orders.py 리뷰해줘"가 description과 맞아서 모델이 `skill` 도구로 본문 전체를 읽는다(`→ Skill "code-review"`).
3. **체크리스트 적용**: 본문은 다섯 영역을 "모두 훑으라"고 지시한다. 모델은 `Glob`·`Read`로 파일을 읽고(기록의 `✱ Glob`, `→ Read`), 영역별로 대조한다. 스킬 없이 "리뷰해줘"만 하면 영역을 건너뛰기 쉽다.
4. **출력 형식 강제**: 표의 열 이름·정렬 순서·요약 줄 수를 본문에 구체적으로 적었기 때문에 결과가 표 하나와 요약으로 일정하게 나온다. 형식 지시는 "좋은 리뷰를 써라"보다 "열은 이 네 개, 순서는 이렇게"처럼 구체적일수록 잘 지켜진다.
5. **읽기 전용**: 본문에 "고쳐 달라고 하기 전에는 수정하지 않는다"고 적어서 리뷰 요청이 파일 변경으로 번지지 않는다.

## 직접 바꿔 보기

- 체크리스트에 팀 규칙을 한 줄 추가해 보자. 예: "공개 함수에는 타입 힌트와 docstring이 있어야 한다(제안)". 같은 프롬프트로 다시 실행하면 `get_orders` 등에 대한 지적이 늘어난다.
- 표의 열을 `심각도 | 위치 | 문제 | 제안`에서 `심각도 | 위치 | 문제 | 수정 예시 코드`로 바꾸면 출력이 어떻게 달라지는지 보자.
- `sample/orders.py`의 결함 하나를 직접 고친 뒤(예: SQL을 `?` 바인딩으로) 다시 리뷰시켜서 지적이 사라지는지 확인하자.

## 주의할 점 / 문제 해결

- **이 폴더에서 바로 실행한다.** 이 예제는 `sandbox/`를 쓰지 않는다(git 변경이 필요 없기 때문). 폴더 이름이 길어 헷갈리면 `cd`한 뒤 `opencode debug skill`로 `location`이 이 폴더의 `.opencode/skills/code-review/SKILL.md`인지 확인하자.
- **등급은 모델마다 다르다.** 같은 결함을 어떤 모델은 "주의", 다른 모델은 "치명"으로 쓴다. 결함 목록이 빠짐없이 나왔는지를 먼저 보고, 등급은 SKILL.md의 심각도 표를 더 구체적으로 고쳐서 맞추자.
- **`.opencode/`가 있는 폴더에서는** opencode가 시작할 때 `@opencode-ai/plugin`을 npm에서 설치하려 시도하고, 성공하면 `.opencode/` 안에 `package.json`, `node_modules/`, `.gitignore`가 생긴다(모두 git에서 제외). 이 예제에는 플러그인(`.opencode/plugins/*.js`)이 없어서, 레지스트리에 닿지 않는 환경에서도 눈에 띄는 멈춤은 없었다(연결을 거부하는 레지스트리로 측정: `opencode debug skill` 약 2초, `opencode run` 약 4초. TUI는 확인하지 못했다). 설치 시도 자체는 일어난다. 같은 환경에서 `.opencode/plugins/*.js`가 있는 폴더(P1~P8 등)는 시작할 때마다 약 70초 멈춘다(새 환경의 맨 처음 시작은 약 130초). 패키지 미러를 지정하는 방법은 [P6 README](../../03-plugins/p6-custom-tool/README.md#npm-자동-설치와-레지스트리패키지-미러)에 있다.
- **샘플 코드는 실행용이 아니다.** `python sample/orders.py`는 메모리 DB로 한 줄만 출력한다. 결함을 일부러 고치지 않고 두는 것이 이 예제의 목적이다. Linux에서 `python` 명령이 없으면 `python3`로 바꾸세요.
