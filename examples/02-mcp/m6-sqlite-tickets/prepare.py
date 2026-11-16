#!/usr/bin/env python3
"""prepare.py - M6 준비: 가상의 장애 티켓 DB(tickets.db)를 만든다.

실제 업무 시스템 대신 쓰는 연습용 데이터다. 약 200건의 합성 장애 티켓이 들어간다.
실행할 때마다 DB를 처음부터 다시 만들며(idempotent), 같은 기준일이면 항상 같은 내용이 나온다.

    python prepare.py                       # 오늘 날짜 기준 최근 60일치
    python prepare.py --today 2026-03-18    # 기준일을 고정 (재현용)

주의: 날짜는 "기준일로부터 며칠 전"으로 만든다. 그래서 며칠 뒤에 '지난주 티켓'을 물어보려면
prepare.py를 다시 실행해 기준일을 새로 잡아야 한다.
"""
import argparse
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "tickets.db"
SEED = 20240611  # 고정 시드: 같은 기준일 -> 같은 데이터

# server.py의 SERVICES / STATUSES / SEVERITIES와 같아야 한다 (check.py가 확인한다)
SERVICES = ["payment", "auth", "search", "notification", "billing-batch", "gateway"]
SEVERITIES = ["SEV1", "SEV2", "SEV3", "SEV4"]
STATUSES = ["open", "investigating", "resolved", "closed"]
ASSIGNEES = ["dev-a", "dev-b", "dev-c", "dev-d", "dev-e"]

# 서비스별 (제목 템플릿, 해결 내용) 후보. {n}은 임의 숫자로 채운다.
TEMPLATES = {
    "payment": [
        ("결제 승인 응답 지연 (p99 {n}초)", "DB 커넥션 풀 크기를 상향하고 서비스를 재시작했다"),
        ("카드사 연동 타임아웃으로 결제 실패율 {n}% 상승", "카드사 장애 확인 후 보조 승인 경로로 우회했다"),
        ("결제 취소 API가 500 오류를 반환", "취소 요청의 null 금액 필드를 방어하는 핫픽스를 배포했다"),
        ("간편결제 콜백 일부 누락", "콜백 재시도 큐의 소비자 수를 늘리고 누락분을 재처리했다"),
        ("환불 요청이 대기 상태에서 멈춤", "멈춘 환불 {n}건을 수동 재처리하고 워커 데드락을 수정했다"),
    ],
    "auth": [
        ("로그인 토큰 갱신 실패율 증가", "토큰 서명 키 캐시 만료 시간을 조정했다"),
        ("SSO 로그인 후 리다이렉트 루프 발생", "리다이렉트 URI 검증 규칙의 오타를 수정했다"),
        ("비밀번호 재설정 메일이 {n}분째 도착하지 않음", "메일 큐 적체를 해소하고 재발송했다"),
    ],
    "search": [
        ("검색 결과가 {n}분 전 데이터로 고정됨", "색인 갱신 작업의 멈춘 스레드를 재시작했다"),
        ("자동완성 응답 지연", "캐시 키 설계를 고쳐 적중률을 높였다"),
        ("특정 키워드 검색 시 결과 0건", "형태소 분석 사전을 이전 버전으로 되돌렸다"),
    ],
    "notification": [
        ("푸시 알림 발송 지연 ({n}분)", "발송 워커를 증설하고 대기열을 비웠다"),
        ("알림 중복 발송", "발송 요청에 멱등 키를 추가했다"),
        ("문자 발송 대행사 오류 응답 증가", "대행사 장애 종료 후 실패 건을 재발송했다"),
    ],
    "billing-batch": [
        ("정산 배치가 중복 실행됨", "스케줄러 잠금을 추가하고 중복 정산분을 정정했다"),
        ("월말 정산 배치 소요 시간 {n}시간 초과", "조회 쿼리 인덱스를 추가해 처리 시간을 단축했다"),
        ("정산 파일 생성 실패", "저장소 용량을 확보하고 배치를 재실행했다"),
    ],
    "gateway": [
        ("API 게이트웨이 429 응답 급증", "클라이언트별 속도 제한 설정을 조정했다"),
        ("인증서 만료 {n}일 전 경고", "인증서를 갱신하고 자동 갱신 알림을 추가했다"),
        ("일부 리전 라우팅 오류", "라우팅 규칙 배포를 롤백했다"),
    ],
}

# "지난주 payment 서비스 장애 티켓 요약" 데모용으로 최근 2주 안에 payment 티켓을 확실히 심어 둔다.
# (며칠 전, 시각, 심각도, 제목, 상태, 담당, 해결 내용)
PAYMENT_STORY = [
    (13, "09:12", "SEV3", "정산 대사 화면에서 일부 결제 건이 누락되어 보임", "closed", "dev-c", "대사 조회 쿼리의 날짜 경계 조건을 수정했다"),
    (9, "21:40", "SEV2", "카드사 연동 타임아웃으로 결제 실패율 12% 상승", "closed", "dev-a", "카드사 장애 확인 후 보조 승인 경로로 우회했다"),
    (6, "10:05", "SEV1", "결제 승인 전면 실패 (전체 결제 불가 {m}분)", "resolved", "dev-a", "배포된 설정 변경을 롤백하고 승인 서버를 재기동했다. 포스트모템 작성 예정"),
    (6, "14:30", "SEV3", "SEV1 장애 여파로 결제 취소 요청 대기열 적체", "resolved", "dev-b", "적체된 취소 요청을 순차 재처리했다"),
    (5, "11:20", "SEV2", "결제 승인 응답 지연 (p99 9초)", "resolved", "dev-a", "DB 커넥션 풀 크기를 상향하고 느린 쿼리를 최적화했다"),
    (4, "16:45", "SEV3", "간편결제 콜백 일부 누락", "resolved", "dev-d", "콜백 재시도 큐의 소비자 수를 늘리고 누락분을 재처리했다"),
    (3, "08:50", "SEV2", "환불 요청 {m}건이 대기 상태에서 멈춤", "investigating", "dev-b", None),
    (2, "13:15", "SEV4", "결제 영수증 메일의 금액 표기 오류", "open", "dev-e", None),
    (1, "17:30", "SEV3", "해외 카드 결제 승인율 저하", "open", "dev-c", None),
]


def make_rows(today: date) -> list[tuple]:
    rng = random.Random(SEED)
    rows = []  # (created_at, service, severity, title, status, assignee, resolution)

    for days_ago, hhmm, sev, title, status, assignee, resolution in PAYMENT_STORY:
        day = today - timedelta(days=days_ago)
        title = title.replace("{m}", str(rng.randint(8, 40)))
        rows.append((f"{day.isoformat()} {hhmm}", "payment", sev, title, status, assignee, resolution))

    # 나머지: 최근 60일에 걸친 합성 티켓
    while len(rows) < 200:
        service = rng.choices(SERVICES, weights=[2, 3, 3, 3, 2, 3])[0]  # payment는 이미 심어 둔 분량이 있어 가중치를 낮춘다
        days_ago = int(rng.triangular(0, 60, 8))  # 최근일수록 조금 더 많다
        minutes = rng.randint(8 * 60, 22 * 60)
        created = datetime.combine(today - timedelta(days=days_ago), datetime.min.time()) + timedelta(minutes=minutes)
        severity = rng.choices(SEVERITIES, weights=[5, 15, 40, 40])[0]
        title_tpl, resolution = rng.choice(TEMPLATES[service])
        title = title_tpl.replace("{n}", str(rng.randint(2, 45)))
        resolution = resolution.replace("{n}", str(rng.randint(2, 30)))
        # 오래된 티켓일수록 닫혀 있고, 최근 티켓은 진행 중일 확률이 높다
        if days_ago <= 2:
            status = rng.choices(STATUSES, weights=[4, 3, 2, 0])[0]
        elif days_ago <= 7:
            status = rng.choices(STATUSES, weights=[1, 1, 4, 3])[0]
        else:
            status = rng.choices(STATUSES, weights=[0, 0, 2, 8])[0]
        if status in ("open", "investigating"):
            resolution = None
        rows.append((created.strftime("%Y-%m-%d %H:%M"), service, severity, title, status, rng.choice(ASSIGNEES), resolution))

    rows.sort(key=lambda r: r[0])  # 오래된 순으로 id를 매긴다
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="가상 장애 티켓 DB(tickets.db) 생성")
    parser.add_argument("--today", help="기준일 YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--db", default=str(DB_PATH), help="생성할 DB 경로 (기본: tickets.db)")
    args = parser.parse_args()
    today = date.fromisoformat(args.today) if args.today else date.today()

    db_path = Path(args.db)
    for suffix in ("", "-journal", "-wal", "-shm"):  # 이전 DB 흔적 제거 -> 항상 처음부터
        Path(str(db_path) + suffix).unlink(missing_ok=True)

    rows = make_rows(today)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """CREATE TABLE tickets (
                   id          INTEGER PRIMARY KEY,
                   created_at  TEXT NOT NULL,      -- 'YYYY-MM-DD HH:MM'
                   service     TEXT NOT NULL,
                   severity    TEXT NOT NULL,      -- SEV1(가장 심각) ~ SEV4
                   title       TEXT NOT NULL,
                   status      TEXT NOT NULL,      -- open / investigating / resolved / closed
                   assignee    TEXT NOT NULL,
                   resolution  TEXT                -- 해결 전에는 NULL
               )"""
        )
        conn.execute("CREATE INDEX idx_tickets_created ON tickets(created_at)")
        conn.executemany(
            "INSERT INTO tickets (id, created_at, service, severity, title, status, assignee, resolution) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(1000 + i, *row) for i, row in enumerate(rows, start=1)],
        )
        conn.commit()
    finally:
        conn.close()

    print(f"만들었습니다: {db_path.name}  (티켓 {len(rows)}건, 기준일 {today.isoformat()})")
    print("다음: opencode를 실행하고 '지난주 payment 서비스 장애 티켓 요약해줘'라고 물어보세요.")


if __name__ == "__main__":
    main()
