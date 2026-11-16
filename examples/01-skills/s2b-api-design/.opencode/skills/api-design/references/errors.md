# 오류 응답 규칙

모든 오류 응답의 본문은 아래 모양 하나로 통일한다.

```json
{
  "error": {
    "code": "order_not_found",
    "message": "주문을 찾을 수 없습니다.",
    "request_id": "req_7c1d0a"
  }
}
```

- `code`: 영문 snake_case. 클라이언트는 `message`가 아니라 `code`로 분기한다.
- `message`: 사람이 읽는 한국어 문장. 내부 구현(스택, SQL)은 담지 않는다.
- `request_id`: 모든 오류 응답에 필수. 로그에서 같은 ID로 찾을 수 있어야 한다.

## 상태 코드

| 상황 | 상태 | code 예 |
| --- | --- | --- |
| 입력 검증 실패 | 400 | `validation_failed` |
| 인증 안 됨 | 401 | `unauthenticated` |
| 권한 없음 | 403 | `forbidden` |
| 없음 | 404 | `<resource>_not_found` |
| 이미 처리됨(중복) | 409 | `already_processed` |
| 서버 오류 | 500 | `internal_error` |

- 검증 실패(`400`)에는 `error.details` 배열을 추가한다: `[{"field": "limit", "issue": "must_be_positive"}]`.
- `422`는 쓰지 않는다. 검증 실패는 모두 `400`이다.
