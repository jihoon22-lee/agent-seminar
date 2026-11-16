"""X2 준비: 가짜 티켓 DB(tickets.db)를 만든다. 실행할 때마다 처음부터 다시 만든다. (표준 라이브러리만 사용)

    python prepare.py              # 오늘을 기준일로 삼아 '최근 7일' 동안 payment 장애가 있었던 데이터를 만든다
    python prepare.py --as-of 2026-11-17   # 기준일을 고정 (재현용)

만들어지는 것
  tickets.db   tickets(티켓), deploys(배포 이력), meta(기준일) 세 테이블
  reports/     리포트가 저장될 빈 폴더
  logs/        플러그인이 감사 로그를 쓸 빈 폴더

이야기(모두 가짜 데이터)
  기준일 -4일 14:05  payment-api v2.14.0 배포 (DB 커넥션 풀 max 40 -> 10 로 정리, 카드사 호출 재시도 추가)
  기준일 -4일 14:20~ card-gateway 승인 타임아웃·풀 고갈 티켓이 급증
  기준일 -3일 09:30  v2.14.1 핫픽스 (풀 max 20), 티켓 감소
  기준일 -2일       카드사 B 응답 지연으로 일부 재발 (배포와 무관한 외부 요인)
  그 밖에 auth / search / notification 서비스의 잡음 티켓과, 지난주(-13~-7일)의 평온한 payment 기준선
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import shutil
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent

SCHEMA = """
CREATE TABLE tickets (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,      -- 'YYYY-MM-DD HH:MM'
  resolved_at TEXT,              -- 해결 전이면 NULL
  service TEXT NOT NULL,
  component TEXT NOT NULL,
  severity TEXT NOT NULL,        -- P1(치명) ~ P4(경미)
  status TEXT NOT NULL,          -- open / resolved
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  reporter TEXT NOT NULL
);
CREATE TABLE deploys (
  id INTEGER PRIMARY KEY,
  service TEXT NOT NULL,         -- tickets.service 와 같은 이름 (payment)
  artifact TEXT NOT NULL,        -- 배포 대상 (payment-api)
  version TEXT NOT NULL,
  deployed_at TEXT NOT NULL,
  summary TEXT NOT NULL
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX idx_tickets_service_time ON tickets(service, created_at);
"""

REPORTERS = ["monitor-bot", "cs-team", "monitor-bot", "monitor-bot", "ops-kim", "ops-lee"]


def fmt(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M")


class Builder:
    def __init__(self, con: sqlite3.Connection, rng: random.Random) -> None:
        self.con, self.rng, self.next_id = con, rng, 1000

    def ticket(self, when: dt.datetime, service: str, component: str, severity: str, title: str, desc: str,
               minutes_to_resolve: int | None, reporter: str | None = None) -> int:
        self.next_id += 1
        resolved = fmt(when + dt.timedelta(minutes=minutes_to_resolve)) if minutes_to_resolve is not None else None
        self.con.execute(
            "INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?)",
            (self.next_id, fmt(when), resolved, service, component, severity,
             "resolved" if resolved else "open", title, desc, reporter or self.rng.choice(REPORTERS)))
        return self.next_id


def build(as_of: dt.date) -> sqlite3.Connection:
    rng = random.Random(20261117)
    db = HERE / "tickets.db"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    con.execute("INSERT INTO meta VALUES ('as_of', ?)", (as_of.isoformat(),))
    b = Builder(con, rng)
    day = lambda n, h=0, m=0: dt.datetime.combine(as_of - dt.timedelta(days=n), dt.time(h, m))  # noqa: E731

    # ---- 배포 이력
    deploys = [
        ("payment", "payment-api", "v2.13.4", day(11, 11, 0), "프로모션 쿠폰 계산 버그 수정"),
        ("payment", "payment-api", "v2.14.0", day(4, 14, 5), "DB 커넥션 풀 기본값 정리(max 40 -> 10), 카드사 승인 호출 재시도(최대 3회) 추가"),
        ("payment", "payment-api", "v2.14.1", day(3, 9, 30), "핫픽스: DB 커넥션 풀 max 10 -> 20 으로 상향, 재시도 간격에 지터 추가"),
        ("auth", "auth-api", "v5.2.0", day(5, 16, 0), "로그인 시도 제한 로직 개선"),
        ("search", "search-api", "v1.9.3", day(2, 10, 30), "색인 배치 시간 조정"),
        ("notification", "notification-worker", "v3.0.2", day(6, 15, 20), "푸시 템플릿 업데이트"),
    ]
    for svc, artifact, ver, when, summary in deploys:
        con.execute("INSERT INTO deploys(service, artifact, version, deployed_at, summary) VALUES (?,?,?,?,?)",
                    (svc, artifact, ver, fmt(when), summary))

    # ---- payment 기준선: 지난주(-13 ~ -7일) 평온 (하루 0~2건, P3/P4)
    baseline = [
        ("card-gateway", "P4", "승인 응답이 가끔 느립니다", "특정 카드사에서 승인 응답이 1~2초 걸린다는 문의. 재현은 안 됨."),
        ("webhook", "P3", "정산 웹훅 중복 수신", "정산 웹훅이 같은 건으로 두 번 들어옴. 멱등 키로 처리되어 영향 없음."),
        ("db-pool", "P4", "야간 배치 중 풀 사용률 경고", "02:00 배치 구간에 커넥션 풀 사용률 70% 경고 후 자동 해소."),
        ("card-gateway", "P3", "해외 카드 승인 거절 문의", "해외 발급 카드 거절 문의. 카드사 정책 때문으로 확인됨."),
    ]
    for n in range(13, 6, -1):
        for _ in range(rng.choice([0, 1, 1, 2])):
            comp, sev, title, desc = rng.choice(baseline)
            b.ticket(day(n, rng.randint(9, 20), rng.randint(0, 59)), "payment", comp, sev, title, desc, rng.randint(20, 240))

    # ---- payment 이번 주(-6 ~ 0일): 평소 수준 + 배포 후 급증
    for n in (6, 5):
        for _ in range(rng.choice([1, 2])):
            comp, sev, title, desc = rng.choice(baseline)
            b.ticket(day(n, rng.randint(9, 20), rng.randint(0, 59)), "payment", comp, sev, title, desc, rng.randint(20, 240))

    # 배포 전 같은 날(-4일) 오전: 평소 수준
    b.ticket(day(4, 10, 12), "payment", "card-gateway", "P4", "승인 응답이 가끔 느립니다",
             "특정 카드사에서 승인 응답이 1~2초 걸린다는 문의. 재현은 안 됨.", 90)

    surge_titles = {
        "card-gateway": [
            ("P1", "결제 승인 요청 타임아웃 급증", "카드 승인 API 호출이 3000ms 를 넘겨 타임아웃. 최근 10분간 실패율 {pct}%. 재시도 로그가 평소보다 많음."),
            ("P2", "결제 승인 실패 문의 폭주", "고객센터로 '결제하다가 멈춘다'는 문의가 {n}건 들어옴. 승인 단계 타임아웃 메시지 확인."),
            ("P2", "card-gateway 재시도 폭증", "card-gateway 가 동일 승인 건을 최대 3회 재시도하면서 카드사 호출량이 평소의 {x}배."),
        ],
        "db-pool": [
            ("P1", "payment DB 커넥션 풀 고갈", "payment-api 의 DB 커넥션 풀이 가득 차서 대기 중인 요청이 쌓임(pool exhausted, active=10/10, waiting={n})."),
            ("P2", "커넥션 풀 대기 시간 증가", "커넥션 획득 대기 p99 가 {ms}ms 로 증가. 승인 요청 처리 지연과 동시에 발생."),
        ],
        "webhook": [
            ("P3", "결제 완료 웹훅 지연", "결제 완료 웹훅이 평균 {min}분 늦게 도착. 주문 상태 갱신이 늦어짐."),
        ],
    }
    # (시각 오프셋 분 기준, 건수 가중치) : v2.14.0 배포 후 폭증 -> 핫픽스 후 감소
    phases = [
        (day(4, 14, 20), day(4, 23, 59), 17, {"card-gateway": 0.55, "db-pool": 0.3, "webhook": 0.15}, (0.2, 0.35, 0.45)),
        (day(3, 0, 0), day(3, 9, 25), 6, {"card-gateway": 0.5, "db-pool": 0.4, "webhook": 0.1}, (0.15, 0.35, 0.5)),
        (day(3, 9, 40), day(3, 23, 59), 6, {"card-gateway": 0.6, "db-pool": 0.15, "webhook": 0.25}, (0.0, 0.3, 0.7)),
        (day(2, 8, 0), day(2, 18, 0), 5, {"card-gateway": 0.8, "db-pool": 0.0, "webhook": 0.2}, (0.0, 0.3, 0.7)),
        (day(1, 9, 0), day(0, 12, 0), 3, {"card-gateway": 0.5, "db-pool": 0.2, "webhook": 0.3}, (0.0, 0.1, 0.9)),
    ]
    for start, end, count, comp_w, _sev_w in phases:
        span = int((end - start).total_seconds() // 60)
        for i in range(count):
            when = start + dt.timedelta(minutes=int(span * (i + rng.random() * 0.8) / count))
            comp = rng.choices(list(comp_w), weights=list(comp_w.values()))[0] if sum(comp_w.values()) else "card-gateway"
            sev, title, desc = rng.choice(surge_titles[comp])
            if start.date() == day(4).date() and i < 2 and comp != "webhook":
                sev = "P1"  # 급증 직후 첫 건들은 치명
            elif start.date() >= day(2).date() and sev == "P1":
                sev = "P2"
            if comp == "card-gateway" and start.date() == day(2).date():
                title, desc = ("카드사 B 승인 응답 지연", "카드사 B 로 가는 승인 요청만 느림(평균 2.8초). 다른 카드사는 정상. 카드사 B 점검 공지 확인 필요.")
            desc = desc.format(pct=rng.randint(18, 42), n=rng.randint(9, 40), x=rng.randint(2, 4),
                               ms=rng.randint(1800, 5200), min=rng.randint(4, 15))
            fast = start.date() >= day(2).date()
            b.ticket(when, "payment", comp, sev, title, desc, rng.randint(15, 90) if fast else rng.randint(40, 260))

    # 아직 해결되지 않은 건 (가장 최근 2건)
    b.ticket(day(0, 8, 40), "payment", "card-gateway", "P3", "카드사 B 간헐적 지연 지속",
             "카드사 B 구간만 간헐적으로 느림. 카드사 측 회신 대기 중.", None)
    b.ticket(day(1, 17, 5), "payment", "db-pool", "P3", "커넥션 풀 max 설정 재검토 필요",
             "v2.14.1 이후에도 피크 시간대에 풀 사용률이 85% 까지 오름. 적정 max 값 논의 필요.", None)

    # ---- 다른 서비스 잡음 (+ payment 와 얽힌 연관 티켓 1건)
    noise = [
        ("auth", "login", "P3", "로그인 실패 알림", "SMS 인증 코드 도착이 늦다는 문의.", 5),
        ("auth", "session", "P4", "세션 만료 시간 문의", "자동 로그아웃이 너무 빠르다는 사용자 의견.", 3),
        ("auth", "login", "P2", "특정 지역 로그인 오류", "일부 통신사 망에서 로그인 요청이 실패.", 5),
        ("search", "index", "P3", "신규 상품 검색 반영 지연", "신규 상품이 검색에 나오기까지 30분 이상 걸림.", 2),
        ("search", "index", "P4", "자동완성 오타 교정 요청", "자동완성 결과 오타 교정 요청.", 4),
        ("search", "api", "P3", "검색 API 5xx 일시 증가", "배포 직후 5xx 가 3분간 증가했다가 회복.", 2),
        ("notification", "push", "P3", "푸시 알림 중복 발송", "일부 사용자에게 같은 푸시가 두 번 발송됨.", 6),
        ("notification", "push", "P4", "푸시 문구 오타", "푸시 템플릿에 오타.", 6),
    ]
    for svc, comp, sev, title, desc, n in noise:
        b.ticket(day(n, rng.randint(9, 19), rng.randint(0, 59)), svc, comp, sev, title, desc, rng.randint(30, 300))
    b.ticket(day(4, 15, 40), "notification", "webhook-consumer", "P2", "결제 완료 알림 지연",
             "payment-api 의 결제 완료 이벤트가 늦게 도착해서 '결제 완료' 푸시가 평균 10분 지연됨. 원인은 notification 쪽이 아님.", 240)
    con.commit()
    return con


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of", help="기준일 YYYY-MM-DD (기본: 오늘)")
    args = ap.parse_args()
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else dt.date.today()
    con = build(as_of)
    total = con.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    week = con.execute("SELECT COUNT(*) FROM tickets WHERE service='payment' AND created_at >= ?",
                       (fmt(dt.datetime.combine(as_of - dt.timedelta(days=6), dt.time(0, 0))),)).fetchone()[0]
    prev = con.execute("SELECT COUNT(*) FROM tickets WHERE service='payment' AND created_at < ? AND created_at >= ?",
                       (fmt(dt.datetime.combine(as_of - dt.timedelta(days=6), dt.time(0, 0))),
                        fmt(dt.datetime.combine(as_of - dt.timedelta(days=13), dt.time(0, 0))))).fetchone()[0]
    con.close()
    for sub in ("reports", "logs"):
        shutil.rmtree(HERE / sub, ignore_errors=True)
        (HERE / sub).mkdir()
    print(f"tickets.db 생성: 기준일 {as_of}, 티켓 {total}건 (payment: 최근 7일 {week}건 / 그 전 7일 {prev}건)")
    print("reports/, logs/ 를 비웠습니다. 이제 이 폴더에서 opencode 를 실행하세요.")


if __name__ == "__main__":
    main()
