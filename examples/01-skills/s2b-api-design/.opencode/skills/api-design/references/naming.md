# 이름 규칙

- 경로의 리소스는 **복수형 명사, 소문자, 하이픈**: `/orders`, `/order-items`. 동사는 경로에 넣지 않는다(`/getOrders` 금지).
- 하위 리소스는 두 단계까지만: `/orders/{order_id}/items`. 그보다 깊으면 쿼리 필터로 푼다.
- JSON 필드는 **snake_case**: `created_at`, `total_amount`.
- 시각 필드는 `_at`으로 끝나고 UTC ISO 8601 문자열(`2026-03-01T09:30:00Z`).
- 불리언 필드는 `is_` 또는 `has_`로 시작: `is_paid`, `has_coupon`.
- 금액은 정수 + 통화 코드 두 필드: `total_amount: 12900`, `currency: "KRW"`. 소수·문자열 금액 금지.
- 리소스 ID는 문자열이고 종류를 나타내는 접두사를 붙인다: 주문 `ord_`, 고객 `cus_`, 결제 `pay_`. (예: `ord_2f9k3x`)
