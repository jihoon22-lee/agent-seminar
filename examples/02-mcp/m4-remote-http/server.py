#!/usr/bin/env python3
"""M4 - 같은 용어집 서버를 stdio(로컬)와 Streamable HTTP(원격) 두 방식으로 실행한다.

    python server.py                     # stdio: opencode가 직접 띄우는 방식 (M1~M3와 같다)
    python server.py --http              # HTTP: http://127.0.0.1:3917/mcp 에서 직접 켜 두는 방식
    python server.py --http --port 4000

도구와 JSON-RPC 처리 코드는 M3와 같고, 달라지는 것은 "메시지를 실어 나르는 길"뿐이다.

    stdio  : 줄 단위 JSON을 stdin/stdout으로 주고받는다.
    HTTP   : 같은 JSON을 HTTP POST 본문으로 주고받는다. (Streamable HTTP, 이 파일은 그 최소 구현)

HTTP 규칙 요약 (이 서버가 지키는 것)
    POST /mcp  요청(id 있음)        -> 200, Content-Type: application/json, 본문 = JSON-RPC 응답
    POST /mcp  알림/응답(id 없음)   -> 202, 본문 없음
    GET  /mcp                       -> 405 (서버가 먼저 말을 거는 SSE 스트림을 제공하지 않는다)
    Authorization: Bearer <API_TOKEN> 이 다르면 -> 401
    Origin 헤더가 있는데 localhost가 아니면 -> 403 (브라우저를 이용한 DNS 리바인딩 공격 방어)

환경 변수 (M3와 같다)
    API_TOKEN       HTTP 모드에서는 "접속 암호"다. 없으면 서버가 시작하지 않는다.
                    stdio 모드에서는 도구 호출에 필요한 값이다.
    GLOSSARY_PATH   용어집 JSON 경로 (기본: server.py 옆의 glossary.json)
    LOG_LEVEL       DEBUG / INFO / WARNING / ERROR
"""
import argparse
import difflib
import hmac
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
sys.stderr.reconfigure(encoding="utf-8")

SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
METHOD_NOT_FOUND, INVALID_PARAMS, PARSE_ERROR, INVALID_REQUEST = -32601, -32602, -32700, -32600
HERE = Path(__file__).resolve().parent
DEFAULT_PORT = 3917
ENDPOINT = "/mcp"

LOG_LEVEL = (os.environ.get("LOG_LEVEL") or "INFO").upper()
API_TOKEN = os.environ.get("API_TOKEN") or ""
GLOSSARY_PATH = Path(os.environ.get("GLOSSARY_PATH") or HERE / "glossary.json")
TRANSPORT = "stdio"  # main()에서 --http 이면 "http"로 바뀐다

logging.basicConfig(stream=sys.stderr, level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="[glossary-remote] %(levelname)s %(message)s")
log = logging.getLogger("glossary")

TERMS = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))["terms"]


def find_term(query):
    q = query.strip().casefold()
    for item in TERMS:
        if q in (n.casefold() for n in [item["term"], *item.get("aliases", [])]):
            return item
    return None


def text_result(text, is_error=False):
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


TOOLS = [
    {
        "name": "lookup_term",
        "description": (
            "팀 용어집에서 용어 하나의 뜻을 찾는다. ADR, SLO, 롤백, 카나리 배포 같은 팀 내부 용어의 정의가 "
            "필요할 때 사용한다. 영어 이름이나 별칭으로도 찾을 수 있다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"term": {"type": "string", "description": "찾을 용어. 예: 'ADR', '카나리 배포'"}},
            "required": ["term"],
        },
    },
    {
        "name": "list_terms",
        "description": "팀 용어집에 등록된 모든 용어 이름을 나열한다.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "server_info",
        "description": (
            "이 용어집 서버의 실행 방식(stdio/http), 용어집 경로, 로그 수준, 토큰 설정 여부를 보여 준다. "
            "토큰 값 자체는 보여 주지 않는다. 어떤 서버에 연결됐는지 확인하는 용도."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def call_tool(name, arguments):
    if name == "server_info":
        return text_result(
            f"TRANSPORT={TRANSPORT}\nGLOSSARY_PATH={GLOSSARY_PATH}\nLOG_LEVEL={LOG_LEVEL}\n"
            f"API_TOKEN={'설정됨' if API_TOKEN else '없음'}\n용어 수={len(TERMS)}\nPID={os.getpid()}"
        )
    if name in ("lookup_term", "list_terms"):
        if not API_TOKEN:  # stdio에서 토큰 없이 띄운 경우 (HTTP는 토큰 없이는 시작하지 않는다)
            return text_result("API_TOKEN 환경 변수가 설정되지 않아 용어집을 조회할 수 없습니다.", True)
        if name == "list_terms":
            return text_result("\n".join(f"- {i['term']}" for i in TERMS))
        term = arguments.get("term")
        if not isinstance(term, str) or not term.strip():
            raise RpcError(INVALID_PARAMS, "'term'(문자열) 인자가 필요합니다")
        item = find_term(term)
        if item:
            return text_result(f"{item['term']}: {item['definition']}\n(별칭: {', '.join(item.get('aliases', [])) or '-'})")
        near = difflib.get_close_matches(term, [i["term"] for i in TERMS], n=3, cutoff=0.4)
        hint = f" 비슷한 용어: {', '.join(near)}." if near else ""
        return text_result(f"'{term}'은(는) 용어집에 없습니다.{hint}", True)
    raise RpcError(INVALID_PARAMS, f"알 수 없는 도구: {name}")


# --- JSON-RPC 처리: stdio와 HTTP가 "똑같이" 쓴다 ------------------------------------------
def handle(msg):
    """JSON-RPC 요청 하나 -> 응답 dict. 알림(id 없음)이면 None."""
    method, params, msg_id = msg.get("method"), msg.get("params") or {}, msg.get("id")
    if msg_id is None:
        return None
    try:
        if method == "initialize":
            wanted = params.get("protocolVersion")
            version = wanted if wanted in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            log.info("initialize: 클라이언트=%s 버전=%s", params.get("clientInfo"), version)
            result = {"protocolVersion": version, "capabilities": {"tools": {}},
                      "serverInfo": {"name": "glossary-m4", "version": "1.0.0"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            log.info("tools/call %s %s", params.get("name"), params.get("arguments"))
            result = call_tool(params.get("name"), params.get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            raise RpcError(METHOD_NOT_FOUND, f"모르는 method: {method}")
    except RpcError as err:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": err.code, "message": err.message}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


# --- 길 1: stdio ---------------------------------------------------------------------------
def serve_stdio():
    log.info("stdio 모드 시작: API_TOKEN=%s", "설정됨" if API_TOKEN else "없음")
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


# --- 길 2: Streamable HTTP --------------------------------------------------------------------
class McpHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # keep-alive 허용. 그래서 모든 응답에 Content-Length를 꼭 붙인다.

    def log_message(self, fmt, *args):  # 기본 접속 로그(stderr)를 우리 로거로 바꾼다
        log.debug("http %s", fmt % args)

    def _reply(self, status, body=b"", content_type=None, extra=None):
        self.send_response(status)
        if content_type:
            self.send_header("Content-Type", content_type)
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, status, obj, extra=None):
        # HTTP 본문은 바이트다. 인코딩을 UTF-8로 못 박아 Windows에서도 한글이 안전하다.
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._reply(status, data, "application/json; charset=utf-8", extra)

    def _authorized(self):
        expected = "Bearer " + API_TOKEN
        # compare_digest: 문자열 비교 시간으로 토큰을 추측하는 공격을 막는 상수 시간 비교
        return hmac.compare_digest(self.headers.get("Authorization", "").encode("utf-8"), expected.encode("utf-8"))

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        if not origin:  # opencode 같은 CLI 클라이언트는 Origin을 보내지 않는다
            return True
        return urlparse(origin).hostname in ("127.0.0.1", "localhost", "::1")

    def _gate(self):
        """POST/GET 공통 관문: 경로 -> Origin -> 토큰 순서로 확인한다. 통과하면 True, 아니면 응답을 이미 보냈다."""
        if self.path != ENDPOINT:
            self._json(404, {"error": "not found"})  # 예: opencode가 찔러 보는 /.well-known/... 경로
        elif not self._origin_ok():
            self._json(403, {"error": "forbidden origin"})
        elif not self._authorized():
            log.warning("401: Authorization 헤더가 맞지 않음 (%s %s)", self.command, self.path)
            self._json(401, {"error": "unauthorized"}, {"WWW-Authenticate": "Bearer"})
        else:
            return True
        return False

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)  # 거절하더라도 본문은 읽어서 연결 상태를 깨끗하게 둔다
        if not self._gate():
            return
        try:
            msg = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._json(400, {"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": "JSON 파싱 실패"}})
        if not isinstance(msg, dict):
            return self._json(400, {"jsonrpc": "2.0", "id": None, "error": {"code": INVALID_REQUEST, "message": "객체가 아님"}})
        log.debug("MCP-Protocol-Version 헤더=%s method=%s", self.headers.get("MCP-Protocol-Version"), msg.get("method"))
        response = handle(msg)
        if response is None:
            return self._reply(202)  # 알림에는 본문 없이 202 Accepted
        self._json(200, response)

    def do_GET(self):
        # GET은 "서버가 먼저 보내는 SSE 스트림"을 여는 용도다. 이 서버는 제공하지 않으므로 405.
        # (인증은 GET에도 똑같이 적용한다: 토큰이 틀리면 405가 아니라 401)
        if self._gate():
            self._reply(405, b"", extra={"Allow": "POST"})

    do_DELETE = do_GET  # 세션 종료용 DELETE도 지원하지 않는다 (이 서버는 세션이 없다)


def serve_http(host, port):
    if not API_TOKEN:
        sys.exit("API_TOKEN 환경 변수가 필요합니다. 예) API_TOKEN=demo-token-123 python server.py --http")
    httpd = ThreadingHTTPServer((host, port), McpHandler)
    log.info("HTTP 모드 시작: http://%s:%d%s  (Bearer 토큰 필요, 종료는 Ctrl+C)", host, port, ENDPOINT)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("종료합니다")
    finally:
        httpd.server_close()


def main():
    global TRANSPORT
    parser = argparse.ArgumentParser(description="팀 용어집 MCP 서버 (stdio 또는 Streamable HTTP)")
    parser.add_argument("--http", action="store_true", help="stdio 대신 HTTP 서버로 실행")
    parser.add_argument("--host", default="127.0.0.1", help="바인딩 주소 (기본: 127.0.0.1 = 이 PC에서만 접속 가능)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"HTTP 포트 (기본: {DEFAULT_PORT})")
    args = parser.parse_args()
    if args.http:
        TRANSPORT = "http"
        serve_http(args.host, args.port)
    else:
        serve_stdio()


if __name__ == "__main__":
    main()
