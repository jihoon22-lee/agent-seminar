#!/usr/bin/env python3
"""logs/app.log 를 만든다 (약 2,000줄, 시드 고정이라 항상 같은 결과).

심어 둔 사건: 2026-11-03 10:40~10:55 사이 payment 게이트웨이 타임아웃이 급증한다.
그 직전(10:35~)에 db 커넥션 풀 포화 경고가 먼저 나온다. 그 밖의 시간대는 평소 수준의 잡음이다.

사용: python prepare.py   (Linux에서 python이 없으면 python3 prepare.py)
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
START = datetime(2026, 11, 3, 9, 0, 0)
END = datetime(2026, 11, 3, 12, 0, 0)
INCIDENT = (datetime(2026, 11, 3, 10, 40, 0), datetime(2026, 11, 3, 10, 55, 0))
PRECURSOR = (datetime(2026, 11, 3, 10, 35, 0), datetime(2026, 11, 3, 10, 40, 0))

NORMAL = [  # (level, component, message template)
    ("INFO", "api", "GET /api/products 200 {ms}ms"),
    ("INFO", "api", "GET /api/cart 200 {ms}ms"),
    ("INFO", "api", "POST /api/orders 201 {ms}ms"),
    ("INFO", "auth", "login ok user={user}"),
    ("INFO", "auth", "token refreshed user={user}"),
    ("INFO", "payment", "charge ok order={order} amount={amount}"),
    ("INFO", "db", "query ok rows={rows} took={ms}ms"),
    ("INFO", "cache", "hit key=product:{rows}"),
    ("DEBUG", "cache", "miss key=product:{rows}"),
    ("INFO", "worker", "job email-receipt done in {ms}ms"),
    ("DEBUG", "db", "pool usage {pool}%"),
]
BACKGROUND_ERRORS = [  # low-rate noise that is always there
    ("WARN", "auth", "invalid password attempt user={user}"),
    ("ERROR", "auth", "token expired user={user}"),
    ("ERROR", "cache", "redis connection reset, reconnecting"),
    ("WARN", "api", "slow response GET /api/products {ms}ms"),
    ("ERROR", "worker", "job email-receipt failed attempt={n} smtp 421 try again later"),
]


def fill(rng: random.Random, template: str) -> str:
    return template.format(
        ms=rng.randint(4, 380), user=f"u{rng.randint(1000, 1400)}", order=f"ORD-{rng.randint(40000, 59999)}",
        amount=rng.choice([9900, 12900, 19800, 35000, 4900]), rows=rng.randint(1, 500),
        pool=rng.randint(20, 55), n=rng.randint(1, 3),
    )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    rng = random.Random(20261103)
    lines: list[tuple[datetime, str]] = []

    t = START
    while t < END:
        t += timedelta(seconds=rng.expovariate(1 / 5.4))  # ~1 event / 5.4 s -> ~2,000 lines
        if t >= END:
            break
        in_incident = INCIDENT[0] <= t < INCIDENT[1]
        in_precursor = PRECURSOR[0] <= t < PRECURSOR[1]
        roll = rng.random()
        if in_incident and roll < 0.55:
            order = f"ORD-{rng.randint(40000, 59999)}"
            if rng.random() < 0.8:
                msg = f"ERROR [payment] gateway timeout after 30000ms (order={order})"
            else:
                msg = f"ERROR [payment] charge failed order={order} reason=upstream_unavailable"
        elif in_incident and roll < 0.62:
            msg = f"ERROR [db] connection pool exhausted (active={rng.randint(48, 50)}/50 waiting={rng.randint(5, 30)})"
        elif in_precursor and roll < 0.35:
            msg = f"WARN [db] connection pool usage {rng.randint(82, 97)}% (active={rng.randint(41, 49)}/50)"
        elif roll < 0.035:
            level, comp, tpl = rng.choice(BACKGROUND_ERRORS)
            msg = f"{level} [{comp}] {fill(rng, tpl)}"
        else:
            level, comp, tpl = rng.choice(NORMAL)
            msg = f"{level} [{comp}] {fill(rng, tpl)}"
        lines.append((t, f"{t.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"))

    # A few multi-line entries (stack trace continuation lines) to prove the parser tolerates them.
    out: list[str] = []
    for t, line in lines:
        out.append(line)
        if "gateway timeout" in line and rng.random() < 0.08:
            out.append("    at PaymentClient.charge (payment/client.js:88)")
            out.append("    at async OrderService.checkout (orders/service.js:142)")

    log_dir = HERE / "logs"
    log_dir.mkdir(exist_ok=True)
    (log_dir / "app.log").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {log_dir / 'app.log'} ({len(out)} lines)")
    print("다음: opencode 를 이 폴더에서 실행하고 '[logs/app.log](logs/app.log) 에서 장애 원인을 찾아줘' 라고 요청하세요.")


if __name__ == "__main__":
    main()
