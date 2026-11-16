# 페이지네이션 규칙

목록을 돌려주는 모든 `GET` 컬렉션 API에 적용한다. **커서 방식만** 쓴다. `page`, `offset`, `per_page` 파라미터는 만들지 않는다.

## 요청

| 파라미터 | 설명 |
| --- | --- |
| `limit` | 한 번에 받을 개수. 기본 **25**, 최대 **100** |
| `cursor` | 이전 응답의 `next_cursor` 값. 첫 요청에서는 생략 |

- `limit`이 100을 넘으면 잘라서 주지 않고 `400`과 오류 코드 `limit_too_large`로 거절한다.
- 정렬은 항상 `created_at` 내림차순, 같으면 `id` 내림차순으로 고정한다. 정렬 파라미터를 열어 두지 않는다.

## 응답

```json
{
  "items": [ { "id": "ord_2f9k3x" } ],
  "next_cursor": "pg1_eyJpZCI6Im9yZF8yZjlrM3gifQ",
  "has_more": true
}
```

- 목록은 `data`가 아니라 **`items`** 에 담는다.
- 다음 페이지가 없으면 `next_cursor`는 `null`, `has_more`는 `false`다.
- 커서 값은 클라이언트가 해석하지 못하는 불투명한 문자열이며, 항상 **`pg1_`** 접두사로 시작한다. (`pg1`은 커서 형식 버전이다.)
- 전체 개수(`total_count`)는 기본 응답에 넣지 않는다. 필요하면 별도 `/orders/count` 엔드포인트로 제공한다.
