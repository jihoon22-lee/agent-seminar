#!/usr/bin/env python3
"""M6 - 장애 티켓 DB(SQLite)를 에이전트에게 "읽기 전용"으로 열어 주는 MCP 서버 (stdio).

"진짜 업무 시스템을 MCP로 연결한다"는 것이 어떤 모습인지 보여 주는 예제다.
여기서는 연습용 SQLite 파일(tickets.db)이지만, 팀의 이슈 트래커나 모니터링 API도 구조는 같다.

    에이전트 --(MCP 도구 호출)--> 이 서버 --(읽기 전용 SQL)--> tickets.db

설계 원칙 세 가지
  1. 최소 권한     DB를 읽기 전용(mode=ro)으로 연다. 도구도 조회용 세 개뿐이고, 모델이 SQL을 직접 쓰지 않는다.
  2. 결과 크기 제한 한 번에 최대 20건만 돌려주고, 긴 문장은 자른다. 모델의 컨텍스트가 터지지 않게 한다.
  3. 설명이 곧 설명서  모델은 도구 description과 입력 스키마만 보고 도구를 고른다. 날짜 형식, 허용 값, 한계를 거기에 적는다.

JSON-RPC 뼈대는 M1과 같다 (../m1-stdio-minimal/server.py 참고). 로그는 stderr로만.
환경 변수 TICKETS_DB 로 DB 경로를 바꿀 수 있다 (기본: server.py 옆의 tickets.db).
"""
import json
import os
import re
import sqlite3
import sys
from contextlib import closing
from datetime import date
from pathlib import Path

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
sys.stderr.reconfigure(encoding="utf-8")

SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
METHOD_NOT_FOUND, INVALID_PARAMS, PARSE_ERROR = -32601, -32602, -32700
HERE = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("TICKETS_DB") or HERE / "tickets.db")

# prepare.py와 같은 값. 도구 설명에 그대로 적어 모델이 허용 값을 추측하지 않게 한다.
SERVICES = ["payment", "auth", "search", "notification", "billing-batch", "gateway"]
SEVERITIES = ["SEV1", "SEV2", "SEV3", "SEV4"]
STATUSES = ["open", "investigating", "resolved", "closed"]
GROUP_COLUMNS = ["service", "severity", "status", "assignee"]  # ticket_stats의 group_by 허용 목록(화이트리스트)

DEFAULT_LIMIT, MAX_LIMIT = 10, 20  # 결과 크기 제한
MAX_TEXT = 120                     # 해결 내용 등 긴 문장은 이 길이로 자른다
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def log(*parts):
    print("[tickets]", *parts, file=sys.stderr, flush=True)


# --- 1. 읽기 전용 연결 ------------------------------------------------------------------------
def open_readonly():
    """tickets.db를 읽기 전용으로 연다.

    file:...?mode=ro 형태의 URI로 열면 SQLite 자체가 쓰기를 거부한다. (INSERT/UPDATE/DROP 모두 실패)
    Path.as_uri()는 Windows 경로(C:\\...)와 한글/공백 경로도 올바른 URI로 바꿔 준다.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"{DB_PATH.name} 파일이 없습니다. 먼저 `python prepare.py`를 실행하세요.")
    conn = sqlite3.connect(f"{DB_PATH.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")  # 이중 안전장치: 연결 수준에서도 쓰기 금지
    return conn


# --- 2. 입력 검증 도우미 -----------------------------------------------------------------------
class ToolError(Exception):
    """모델이 읽고 고쳐 쓸 수 있는 오류. isError: true 결과로 나간다."""


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def opt_str(args, key):
    value = args.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ToolError(f"'{key}'는 문자열이어야 합니다.")
    return value.strip()


def opt_choice(args, key, allowed):
    value = opt_str(args, key)
    if value is not None and value not in allowed:
        raise ToolError(f"'{key}' 값이 올바르지 않습니다: '{value}'. 허용 값: {', '.join(allowed)}")
    return value


def opt_date(args, key):
    value = opt_str(args, key)
    if value is not None:
        if not DATE_RE.match(value):
            raise ToolError(f"'{key}'는 YYYY-MM-DD 형식이어야 합니다 (받은 값: '{value}').")
        try:
            date.fromisoformat(value)
        except ValueError:
            raise ToolError(f"'{key}'가 존재하지 않는 날짜입니다: '{value}'.")
    return value


def clip(text, limit=MAX_TEXT):
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def like_pattern(word):
    """사용자가 준 검색어를 LIKE 패턴으로. %, _ 가 와일드카드로 해석되지 않게 이스케이프한다."""
    escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


FILTER_CHOICES = {"service": SERVICES, "status": STATUSES, "severity": SEVERITIES}


def where_clause(args, filters=("service", "status", "severity"), with_query=False):
    """공통 필터 -> (WHERE 문자열, 바인딩 값 목록). 값은 항상 ? 로 바인딩한다 (SQL 인젝션 방지)."""
    conds, params = [], []
    if with_query:
        query = opt_str(args, "query")
        if query:
            conds.append("(title LIKE ? ESCAPE '\\' OR resolution LIKE ? ESCAPE '\\')")
            params += [like_pattern(query)] * 2
    for key in filters:
        value = opt_choice(args, key, FILTER_CHOICES[key])
        if value:
            conds.append(f"{key} = ?")  # key는 위 filters 튜플의 고정 문자열이다
            params.append(value)
    since, until = opt_date(args, "since"), opt_date(args, "until")
    if since:
        conds.append("created_at >= ?")
        params.append(since)  # 'YYYY-MM-DD' <= 'YYYY-MM-DD HH:MM' 문자열 비교로 그날 0시부터
    if until:
        conds.append("created_at <= ?")
        params.append(until + " 23:59")  # until은 그날을 포함한다
    return (" WHERE " + " AND ".join(conds)) if conds else "", params


# --- 3. 도구 정의 (모델이 보는 설명서) --------------------------------------------------------------
TOOLS = [
    {
        "name": "search_tickets",
        "description": (
            "장애 티켓을 검색한다. 최신순으로 정렬해 최대 20건까지만 돌려주며, 전체 건수도 함께 알려 준다. "
            "서비스·상태·심각도·기간으로 좁힐 수 있고, query는 제목과 해결 내용에서 단어를 찾는다. "
            "날짜는 YYYY-MM-DD 형식이다. '지난주', '어제' 같은 상대 표현은 오늘 날짜를 기준으로 계산해 "
            "since/until(둘 다 그날 포함)로 넘겨라. 건수가 많으면 조건을 좁혀 다시 호출하라."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "제목/해결 내용에서 찾을 단어. 비우면 전체. 예: '타임아웃'"},
                "service": {"type": "string", "enum": SERVICES, "description": "서비스 이름"},
                "status": {"type": "string", "enum": STATUSES, "description": "티켓 상태"},
                "severity": {"type": "string", "enum": SEVERITIES, "description": "심각도. SEV1이 가장 심각"},
                "since": {"type": "string", "description": "이 날짜 이후(포함) YYYY-MM-DD"},
                "until": {"type": "string", "description": "이 날짜 이전(포함) YYYY-MM-DD"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": DEFAULT_LIMIT,
                          "description": f"돌려줄 최대 건수 (기본 {DEFAULT_LIMIT}, 최대 {MAX_LIMIT})"},
            },
        },
    },
    {
        "name": "get_ticket",
        "description": "티켓 번호(id)로 티켓 한 건의 전체 내용을 가져온다. search_tickets 결과에서 자세히 볼 티켓을 고를 때 사용한다.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "티켓 번호. 예: 1170"}},
            "required": ["id"],
        },
    },
    {
        "name": "ticket_stats",
        "description": (
            "티켓 건수를 service / severity / status / assignee 별로 집계한다. "
            "개별 티켓이 아니라 '몇 건인지' 분포가 궁금할 때 사용한다. since/until로 기간을, service로 서비스를 제한할 수 있다. "
            "날짜는 YYYY-MM-DD 형식(그날 포함)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_by": {"type": "string", "enum": GROUP_COLUMNS, "description": "집계 기준 열"},
                "service": {"type": "string", "enum": SERVICES, "description": "이 서비스만 집계"},
                "since": {"type": "string", "description": "이 날짜 이후(포함) YYYY-MM-DD"},
                "until": {"type": "string", "description": "이 날짜 이전(포함) YYYY-MM-DD"},
            },
            "required": ["group_by"],
        },
    },
]


# --- 4. 도구 구현 -------------------------------------------------------------------------------
def fmt_row(row):
    line = f"#{row['id']} | {row['created_at']} | {row['service']} | {row['severity']} | {row['status']} | {row['assignee']} | {clip(row['title'])}"
    if row["resolution"]:
        line += f"\n    해결: {clip(row['resolution'])}"
    return line


def search_tickets(args):
    where, params = where_clause(args, with_query=True)
    limit = args.get("limit", DEFAULT_LIMIT)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ToolError("'limit'는 정수여야 합니다.")
    limit = max(1, min(limit, MAX_LIMIT))  # 범위를 벗어난 값은 오류 대신 조용히 보정한다
    with closing(open_readonly()) as conn:  # closing: 쓰고 나면 꼭 닫는다 (Windows는 열린 DB 파일을 지울 수 없다)
        total = conn.execute(f"SELECT COUNT(*) FROM tickets{where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM tickets{where} ORDER BY created_at DESC, id DESC LIMIT ?", [*params, limit]
        ).fetchall()
    if total == 0:
        return "조건에 맞는 티켓이 없습니다."
    head = f"총 {total}건 중 최신 {len(rows)}건 표시"
    if total > len(rows):
        head += f" (나머지 {total - len(rows)}건은 생략: query/service/status/기간으로 좁히거나 limit을 늘리세요)"
    return head + "\n" + "\n".join(fmt_row(r) for r in rows)


def get_ticket(args):
    raw = args.get("id")
    if isinstance(raw, str) and raw.strip().lstrip("#").isdigit():
        raw = int(raw.strip().lstrip("#"))
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise RpcError(INVALID_PARAMS, "'id'(정수) 인자가 필요합니다")
    with closing(open_readonly()) as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", [raw]).fetchone()
    if row is None:
        raise ToolError(f"티켓 #{raw}를 찾을 수 없습니다. search_tickets로 번호를 먼저 확인하세요.")
    return "\n".join(f"{key}: {row[key] if row[key] is not None else '(아직 없음)'}" for key in row.keys())


def ticket_stats(args):
    group_by = opt_choice(args, "group_by", GROUP_COLUMNS)
    if group_by is None:
        raise RpcError(INVALID_PARAMS, f"'group_by' 인자가 필요합니다 ({', '.join(GROUP_COLUMNS)})")
    where, params = where_clause(args, filters=("service",))
    # group_by는 위에서 화이트리스트로 검증한 값만 SQL 문자열에 들어간다. 사용자 입력을 그대로 끼워 넣지 않는다.
    with closing(open_readonly()) as conn:
        rows = conn.execute(
            f"SELECT {group_by} AS k, COUNT(*) AS n FROM tickets{where} GROUP BY {group_by} ORDER BY n DESC, k", params
        ).fetchall()
    if not rows:
        return "조건에 맞는 티켓이 없습니다."
    total = sum(r["n"] for r in rows)
    return f"{group_by}별 건수 (합계 {total}건)\n" + "\n".join(f"- {r['k']}: {r['n']}건" for r in rows)


IMPLEMENTATIONS = {"search_tickets": search_tickets, "get_ticket": get_ticket, "ticket_stats": ticket_stats}


def call_tool(name, arguments):
    impl = IMPLEMENTATIONS.get(name)
    if impl is None:
        raise RpcError(INVALID_PARAMS, f"알 수 없는 도구: {name}")
    try:
        return {"content": [{"type": "text", "text": impl(arguments)}], "isError": False}
    except ToolError as err:
        return {"content": [{"type": "text", "text": str(err)}], "isError": True}
    except (FileNotFoundError, sqlite3.Error) as err:
        log("DB 오류:", err)  # 자세한 내용은 stderr 로그에, 모델에게는 짧은 설명만
        return {"content": [{"type": "text", "text": f"티켓 DB를 읽지 못했습니다: {err}"}], "isError": True}


# --- 5. JSON-RPC 처리 (M1과 동일) -----------------------------------------------------------------
def handle(msg):
    method, params, msg_id = msg.get("method"), msg.get("params") or {}, msg.get("id")
    if msg_id is None:
        return None
    try:
        if method == "initialize":
            wanted = params.get("protocolVersion")
            version = wanted if wanted in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            result = {"protocolVersion": version, "capabilities": {"tools": {}},
                      "serverInfo": {"name": "tickets-m6", "version": "1.0.0"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            log("tools/call", params.get("name"), json.dumps(params.get("arguments"), ensure_ascii=False))
            result = call_tool(params.get("name"), params.get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            raise RpcError(METHOD_NOT_FOUND, f"모르는 method: {method}")
    except RpcError as err:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": err.code, "message": err.message}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def main():
    log(f"시작: DB={DB_PATH.name} (읽기 전용)")
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            response = handle(msg) if isinstance(msg, dict) else None
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": "JSON 파싱 실패"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
