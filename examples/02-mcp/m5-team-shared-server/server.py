"""M5: 팀이 함께 쓰는 원격 MCP 서버 (표준 라이브러리만 사용, Streamable HTTP).

    python server.py                         # 127.0.0.1:3918 (내 컴퓨터에서만 접속 가능)
    python server.py --host 0.0.0.0          # 같은 네트워크의 팀원이 접속하게 열기 (방화벽·토큰 주의!)
    python server.py --port 4000 --tokens my-tokens.json

핵심 기능
  - 토큰마다 사용자 이름이 붙는다 (tokens.json: {"토큰": "사용자"}). 요청마다 파일을 다시 읽으므로
    토큰을 추가·삭제해도 서버를 재시작할 필요가 없다.
  - 모든 도구 호출은 "누가, 어떤 도구를, 언제" 감사 로그로 stderr 와 logs/server.log 에 남는다.
  - 도구: oncall_lookup(team, date?), team_status()

HTTP 규칙 (opencode 의 type: remote 가 기대하는 최소 형태)
  POST  JSON-RPC 요청 -> 200 + application/json   /  알림(id 없음) -> 202
  GET   -> 405 (서버가 먼저 보내는 SSE 스트림은 지원하지 않음. 토큰이 틀리면 401)
  GET /healthz -> 200 "ok"  (인증 없음, 방화벽·로드밸런서 점검용)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class QuietHTTPServer(ThreadingHTTPServer):
    """opencode 가 끝나면서 연결을 끊을 때 Windows 에서는 ConnectionResetError 가 나는데, 이건 정상 종료라서
    traceback 을 찍지 않는다. 그 밖의 오류는 기본 동작대로 보여 준다."""

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

HERE = Path(__file__).resolve().parent
SERVER_NAME, SERVER_VERSION = "team-shared", "1.0.0"
STARTED = time.time()
LOG_LOCK = threading.Lock()
STATS = {"calls": 0}

TOOLS = [
    {
        "name": "oncall_lookup",
        "description": "팀의 온콜 당번(1차/2차)을 조회한다. date 를 생략하면 오늘 기준이다. 팀 이름은 platform, payment, data 중 하나.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "team": {"type": "string", "description": "팀 이름. 예: platform"},
                "date": {"type": "string", "description": "조회 날짜 YYYY-MM-DD (선택, 기본값 오늘)"},
            },
            "required": ["team"],
        },
    },
    {
        "name": "team_status",
        "description": "팀 서비스들의 현재 상태(ok / degraded / maintenance)와 메모를 한 번에 보여 준다. 인자 없음.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# --------------------------------------------------------------------------- 데이터 / 인증
class Config:
    def __init__(self, tokens: Path, oncall: Path, status: Path, log_file: Path) -> None:
        self.tokens, self.oncall, self.status, self.log_file = tokens, oncall, status, log_file

    @staticmethod
    def _load(path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def user_for(self, token: str) -> str | None:
        """요청마다 tokens.json 을 읽는다. 토큰을 바꿔도 재시작이 필요 없다."""
        try:
            return self._load(self.tokens).get(token)
        except (OSError, ValueError):
            return None


def audit(cfg: Config, user: str, what: str, detail: str, outcome: str) -> None:
    """감사 로그: 시각(UTC 오프셋 포함) / 사용자 / 동작 / 상세 / 결과"""
    now = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    line = f"{now} user={user} {what} {detail} -> {outcome}"
    with LOG_LOCK:
        print(line, file=sys.stderr, flush=True)
        cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg.log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# --------------------------------------------------------------------------- 도구 구현
def tool_oncall_lookup(cfg: Config, args: dict) -> tuple[str, bool]:
    team = str(args.get("team", "")).strip().lower()
    day_text = args.get("date") or dt.date.today().isoformat()
    try:
        day = dt.date.fromisoformat(day_text)
    except ValueError:
        return f"날짜 형식이 올바르지 않습니다: {day_text} (YYYY-MM-DD)", True
    table = cfg._load(cfg.oncall)
    if team not in table:
        return f"알 수 없는 팀: {team!r}. 등록된 팀: {', '.join(sorted(table))}", True
    for row in table[team]:
        if dt.date.fromisoformat(row["from"]) <= day <= dt.date.fromisoformat(row["to"]):
            return (f"{team} 팀 온콜 ({day}): 1차 {row['primary']}, 2차 {row['secondary']} "
                    f"(근무 기간 {row['from']} ~ {row['to']})"), False
    # 표에 없는 날짜: 등록된 항목을 ISO 주 번호 순서대로 돌려 가며 쓰는 "주간 순환"으로 대신 답한다.
    # (자습하는 사람이 일정표가 끝난 뒤에 실행해도 빈 답이 나오지 않게 하려는 데모용 규칙이다.)
    rows = table[team]
    if not rows:
        return f"{team} 팀은 {day} 에 등록된 온콜 일정이 없습니다.", True
    week = day.isocalendar()[1]
    row = rows[week % len(rows)]
    return (f"{team} 팀 온콜 ({day}): 1차 {row['primary']}, 2차 {row['secondary']} "
            f"(등록된 일정표 밖의 날짜라서 ISO {week}주 번호를 항목 {len(rows)}개로 나눈 나머지로 고른 순환 배정입니다)"), False


def tool_team_status(cfg: Config, _args: dict) -> tuple[str, bool]:
    services = cfg._load(cfg.status)
    lines = [f"- {name}: {info['state']}" + (f" ({info['note']})" if info.get("note") else "")
             for name, info in services.items()]
    bad = [n for n, i in services.items() if i["state"] != "ok"]
    head = f"서비스 {len(services)}개 중 정상이 아닌 것 {len(bad)}개" + (f": {', '.join(bad)}" if bad else "")
    return head + "\n" + "\n".join(lines), False


HANDLERS = {"oncall_lookup": tool_oncall_lookup, "team_status": tool_team_status}


# --------------------------------------------------------------------------- JSON-RPC
def handle(cfg: Config, user: str, msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:                       # 알림(notifications/initialized 등)에는 응답하지 않는다
        return None
    if method == "initialize":
        result = {
            "protocolVersion": (msg.get("params") or {}).get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = msg.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if handler is None:
            audit(cfg, user, f"tool={name}", json.dumps(args, ensure_ascii=False), "unknown-tool")
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool: {name}"}}
        STATS["calls"] += 1
        try:
            text, is_error = handler(cfg, args)
        except Exception as exc:  # noqa: BLE001 - 도구 오류는 모델이 읽을 수 있게 결과로 돌려준다
            text, is_error = f"서버 오류: {exc}", True
        audit(cfg, user, f"tool={name}", json.dumps(args, ensure_ascii=False), "error" if is_error else "ok")
        result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def make_handler(cfg: Config):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_a) -> None:   # 기본 접속 로그는 끄고 감사 로그만 남긴다
            pass

        def _send(self, status: int, body: bytes = b"", ctype: str = "application/json", extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _authenticate(self) -> str | None:
            """Authorization: Bearer <토큰> 을 검사해 사용자 이름을 돌려준다. 실패하면 401 을 보내고 None."""
            header = self.headers.get("Authorization", "")
            token = header[7:].strip() if header.lower().startswith("bearer ") else ""
            user = cfg.user_for(token) if token else None
            if user is None:
                audit(cfg, "-", "auth", f"{self.command} from={self.client_address[0]}", "denied(401)")
                self._send(401, b'{"error":"invalid or missing token"}',
                           extra={"WWW-Authenticate": 'Bearer realm="team-shared"'})
            return user

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/healthz":
                return self._send(200, b"ok", "text/plain")
            # 클라이언트는 POST 가 실패하면 SSE(GET)로도 시도한다. 토큰이 틀렸을 때 405 대신 401 이 보이게
            # GET 도 인증을 먼저 검사한다.
            if self._authenticate() is not None:
                self._send(405, b"", extra={"Allow": "POST"})

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length)            # 인증에 실패해도 본문은 끝까지 읽는다 (연결 재사용을 위해)
            user = self._authenticate()
            if user is None:
                return
            try:
                msg = json.loads(raw.decode("utf-8"))
            except ValueError:
                return self._send(400, b'{"error":"invalid json"}')
            if isinstance(msg, list):                # 배치는 지원하지 않는다
                return self._send(400, b'{"error":"batch not supported"}')
            out = handle(cfg, user, msg)
            if out is None:
                return self._send(202)
            self._send(200, json.dumps(out, ensure_ascii=False).encode("utf-8"))

        def do_DELETE(self) -> None:  # noqa: N802  (세션 종료 요청: 상태가 없으니 그냥 허용)
            self._send(200)

    return Handler


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="127.0.0.1", help="바인딩 주소. 팀에 공유하려면 0.0.0.0 (기본 127.0.0.1)")
    p.add_argument("--port", type=int, default=3918)
    p.add_argument("--tokens", type=Path, default=HERE / "tokens.json")
    p.add_argument("--oncall", type=Path, default=HERE / "oncall.json")
    p.add_argument("--status", type=Path, default=HERE / "status.json")
    p.add_argument("--log-file", type=Path, default=HERE / "logs" / "server.log")
    a = p.parse_args()
    cfg = Config(a.tokens, a.oncall, a.status, a.log_file)
    server = QuietHTTPServer((a.host, a.port), make_handler(cfg))
    print(f"{SERVER_NAME} MCP 서버: http://{a.host}:{a.port}  (감사 로그: {a.log_file})", file=sys.stderr, flush=True)
    if a.host not in ("127.0.0.1", "localhost", "::1"):
        print("주의: 이 컴퓨터 밖에서도 접속할 수 있는 주소입니다. 방화벽과 토큰을 확인하세요.", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
