"""티켓 DB 읽기 전용 MCP 서버 (stdio, 표준 라이브러리만 사용).

tickets.db 를 sqlite 의 읽기 전용 모드(mode=ro)로 연다. 쓰기 도구는 아예 없고, 혹시 쓰기 SQL 이 들어와도
데이터베이스 수준에서 거부된다. 즉 '읽기 전용'을 도구 설계와 DB 연결, 두 겹으로 보장한다.

도구
  week_range(offset)                        '이번 주'(= 데이터 기준일까지 최근 7일)와 그 이전 구간의 날짜 범위
  list_services()                           서비스별 티켓 수
  ticket_stats(service, from_date, to_date) 심각도·구성요소·일별 건수와 평균 해결 시간
  search_tickets(service, from_date, to_date, keyword, component, severity, limit)
  get_ticket(ticket_id)                     티켓 본문 + 같은 서비스의 직전 배포
  recent_deploys(service, from_date, to_date)

stdout 에는 MCP 메시지만 쓴다. (진단 메시지는 stderr)
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

DB = Path(__file__).resolve().parent / "tickets.db"


def connect() -> sqlite3.Connection:
    if not DB.is_file():
        raise RuntimeError("tickets.db 가 없습니다. 먼저 `python prepare.py` 를 실행하세요.")
    con = sqlite3.connect(f"{DB.resolve().as_uri()}?mode=ro", uri=True)   # 읽기 전용으로 연다
    con.row_factory = sqlite3.Row
    return con


def as_of(con: sqlite3.Connection) -> dt.date:
    return dt.date.fromisoformat(con.execute("SELECT value FROM meta WHERE key='as_of'").fetchone()[0])


def day_range(from_date: str, to_date: str) -> tuple[str, str]:
    """'YYYY-MM-DD' 두 개를 [시작, 끝) 비교용 문자열로 바꾼다. 끝날도 포함한다."""
    start = dt.date.fromisoformat(from_date)
    end = dt.date.fromisoformat(to_date) + dt.timedelta(days=1)
    return f"{start} 00:00", f"{end} 00:00"


def minutes_between(a: str, b: str) -> int:
    f = "%Y-%m-%d %H:%M"
    return int((dt.datetime.strptime(b, f) - dt.datetime.strptime(a, f)).total_seconds() // 60)


# ---------------------------------------------------------------- 도구
def week_range(args: dict) -> dict:
    con = connect()
    today = as_of(con)
    offset = int(args.get("offset", 0))
    end = today - dt.timedelta(days=7 * offset)
    start = end - dt.timedelta(days=6)
    label = "이번 주(최근 7일)" if offset == 0 else f"{offset}주 전(그 이전 7일)"
    return {"label": label, "from": start.isoformat(), "to": end.isoformat(), "today": today.isoformat(),
            "note": "today 는 tickets.db 의 데이터 기준일이다. 리포트 파일명의 날짜로 이 값을 쓴다."}


def list_services(_args: dict) -> dict:
    rows = connect().execute("SELECT service, COUNT(*) n, SUM(status='open') open_n FROM tickets GROUP BY service ORDER BY n DESC")
    return {"services": [{"service": r["service"], "tickets": r["n"], "open": r["open_n"]} for r in rows]}


def ticket_stats(args: dict) -> dict:
    con = connect()
    start, end = day_range(args["from_date"], args["to_date"])
    where, params = "service=? AND created_at>=? AND created_at<?", (args["service"], start, end)
    total = con.execute(f"SELECT COUNT(*) FROM tickets WHERE {where}", params).fetchone()[0]
    by = lambda col: {r[0]: r[1] for r in con.execute(  # noqa: E731
        f"SELECT {col}, COUNT(*) FROM tickets WHERE {where} GROUP BY 1 ORDER BY 2 DESC", params)}
    daily = {r[0]: r[1] for r in con.execute(
        f"SELECT substr(created_at,1,10), COUNT(*) FROM tickets WHERE {where} GROUP BY 1 ORDER BY 1", params)}
    resolved = [minutes_between(r["created_at"], r["resolved_at"]) for r in con.execute(
        f"SELECT created_at, resolved_at FROM tickets WHERE {where} AND resolved_at IS NOT NULL", params)]
    peak = max(daily.items(), key=lambda kv: kv[1]) if daily else None
    return {
        "service": args["service"], "from": args["from_date"], "to": args["to_date"], "total": total,
        "by_severity": by("severity"), "by_component": by("component"), "by_day": daily,
        "peak_day": {"date": peak[0], "tickets": peak[1]} if peak else None,
        "open": con.execute(f"SELECT COUNT(*) FROM tickets WHERE {where} AND status='open'", params).fetchone()[0],
        "avg_resolution_minutes": round(sum(resolved) / len(resolved)) if resolved else None,
    }


def search_tickets(args: dict) -> dict:
    con = connect()
    start, end = day_range(args["from_date"], args["to_date"])
    sql = ["SELECT id, created_at, resolved_at, service, component, severity, status, title FROM tickets",
           "WHERE service=? AND created_at>=? AND created_at<?"]
    params: list = [args["service"], start, end]
    if args.get("keyword"):
        sql.append("AND (title LIKE ? OR description LIKE ?)")
        params += [f"%{args['keyword']}%"] * 2
    if args.get("component"):
        sql.append("AND component=?")
        params.append(args["component"])
    if args.get("severity"):
        sql.append("AND severity=?")
        params.append(args["severity"])
    sql.append("ORDER BY created_at LIMIT ?")
    params.append(min(int(args.get("limit", 20)), 50))
    rows = [dict(r) for r in con.execute(" ".join(sql), params)]
    return {"count": len(rows), "tickets": rows}


def recent_deploys(args: dict) -> dict:
    con = connect()
    start, end = day_range(args["from_date"], args["to_date"])
    rows = con.execute("SELECT id, service, artifact, version, deployed_at, summary FROM deploys WHERE service=? AND deployed_at>=? "
                       "AND deployed_at<? ORDER BY deployed_at", (args["service"], start, end))
    return {"deploys": [dict(r) for r in rows]}


def get_ticket(args: dict) -> dict:
    con = connect()
    row = con.execute("SELECT * FROM tickets WHERE id=?", (int(args["ticket_id"]),)).fetchone()
    if row is None:
        raise ValueError(f"티켓 {args['ticket_id']} 가 없습니다.")
    ticket = dict(row)
    prev = con.execute("SELECT artifact, version, deployed_at, summary FROM deploys WHERE service=? AND deployed_at<=? "
                       "ORDER BY deployed_at DESC LIMIT 1", (row["service"], row["created_at"])).fetchone()
    ticket["previous_deploy"] = dict(prev) if prev else None
    return ticket


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


S = {"type": "string"}
DATE = {"type": "string", "description": "YYYY-MM-DD"}
TOOLS = {
    "week_range": (week_range, "'이번 주'(데이터 기준일까지 최근 7일)와 지난주의 날짜 범위, 그리고 오늘(데이터 기준일)을 알려 준다. 분석을 시작할 때 가장 먼저 호출한다. offset=1 이면 그 이전 7일.",
                   _schema({"offset": {"type": "integer", "description": "0=이번 주, 1=지난주 (기본 0)"}}, [])),
    "list_services": (list_services, "티켓이 있는 서비스 이름과 티켓 수, 미해결 수를 보여 준다.", _schema({}, [])),
    "ticket_stats": (ticket_stats, "기간 안의 티켓 통계: 총 건수, 심각도·구성요소·일별 건수, 피크 일자, 미해결 수, 평균 해결 시간(분).",
                     _schema({"service": S, "from_date": DATE, "to_date": DATE}, ["service", "from_date", "to_date"])),
    "search_tickets": (search_tickets, "기간 안의 티켓 목록을 검색한다(요약 필드만). keyword 는 제목·본문 부분 일치, component·severity 로 좁힐 수 있다. 최대 50건.",
                       _schema({"service": S, "from_date": DATE, "to_date": DATE, "keyword": S, "component": S,
                                "severity": {"type": "string", "description": "P1~P4"}, "limit": {"type": "integer"}},
                               ["service", "from_date", "to_date"])),
    "get_ticket": (get_ticket, "티켓 한 건의 전체 내용과, 그 티켓이 생기기 직전의 배포 정보를 보여 준다.",
                   _schema({"ticket_id": {"type": "integer"}}, ["ticket_id"])),
    "recent_deploys": (recent_deploys, "기간 안의 배포 이력(서비스 이름은 티켓과 같다. 예: payment).",
                       _schema({"service": S, "from_date": DATE, "to_date": DATE}, ["service", "from_date", "to_date"])),
}


# ---------------------------------------------------------------- MCP (줄 단위 JSON-RPC)
def handle(msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": (msg.get("params") or {}).get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}}, "serverInfo": {"name": "tickets", "version": "1.0.0"}}
    elif method == "tools/list":
        result = {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (_f, d, s) in TOOLS.items()]}
    elif method == "tools/call":
        params = msg.get("params") or {}
        entry = TOOLS.get(params.get("name"))
        if entry is None:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": "unknown tool"}}
        try:
            text, is_error = json.dumps(entry[0](params.get("arguments") or {}), ensure_ascii=False), False
        except Exception as exc:  # noqa: BLE001 - 오류는 모델이 읽고 고칠 수 있게 결과로 돌려준다
            text, is_error = f"오류: {exc}", True
        result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        reply = handle(json.loads(line))
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
