"""team_glossary_mcp.server - M1의 server.py를 패키지로 옮긴 것 (표준 라이브러리만 사용).

M1과 달라진 점은 세 가지뿐이다. 프로토콜 처리 코드는 그대로다.
  1. glossary.json 을 `__file__` 경로가 아니라 importlib.resources 로 읽는다.
     -> 압축된 wheel 이나 다른 곳에 설치된 상태에서도 패키지 안의 데이터 파일을 찾는다.
  2. 서버 버전을 __init__.py 의 __version__ 에서 가져온다 (pyproject.toml 도 같은 값을 쓴다).
  3. main() 함수가 진입점이다: `python -m team_glossary_mcp` 또는 설치 후 `team-glossary-mcp` 명령.

규칙은 M1과 같다: stdout에는 JSON-RPC 메시지만 쓴다. 로그는 stderr로.
"""
import difflib
import json
import sys
from importlib import resources

from . import __version__

# 이 서버가 알고 있는 프로토콜 버전들 (최신순).
# 클라이언트가 이 중 하나를 요청하면 그대로 따라가고, 모르는 버전이면 우리 최신 버전을 답한다.
SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

# JSON-RPC 표준 오류 코드
PARSE_ERROR = -32700       # 줄이 JSON이 아님
INVALID_REQUEST = -32600   # JSON이지만 JSON-RPC 요청 모양이 아님
METHOD_NOT_FOUND = -32601  # 모르는 method
INVALID_PARAMS = -32602    # 인자가 잘못됨 (모르는 도구 이름, 필수 인자 누락 등)


def log(*parts):
    """로그는 반드시 stderr로. (stdout은 프로토콜 전용)"""
    print("[team-glossary]", *parts, file=sys.stderr, flush=True)


# --- 1. 데이터: 용어집 ---------------------------------------------------------
def load_glossary():
    data = json.loads(resources.files("team_glossary_mcp").joinpath("glossary.json").read_text(encoding="utf-8"))
    return data["terms"]


TERMS = load_glossary()


def find_term(query):
    """이름이나 별칭이 (대소문자 무시하고) 정확히 일치하는 항목을 찾는다."""
    q = query.strip().casefold()
    for item in TERMS:
        names = [item["term"], *item.get("aliases", [])]
        if q in (n.casefold() for n in names):
            return item
    return None


# --- 2. 도구 정의 ---------------------------------------------------------------
# tools/list가 돌려주는 내용이다. 모델은 이 "description"과 "inputSchema"만 보고
# 언제 이 도구를 부를지, 인자를 어떻게 채울지 결정한다. 설명이 곧 사용 설명서다.
TOOLS = [
    {
        "name": "lookup_term",
        "description": (
            "팀 용어집에서 용어 하나의 뜻을 찾는다. "
            "ADR, SLO, 롤백, 카나리 배포 같은 팀 내부 용어의 정의가 필요할 때 사용한다. "
            "영어 이름이나 별칭으로도 찾을 수 있다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "term": {"type": "string", "description": "찾을 용어. 예: 'ADR', '카나리 배포'"},
            },
            "required": ["term"],
        },
    },
    {
        "name": "list_terms",
        "description": "팀 용어집에 등록된 모든 용어 이름을 나열한다. 어떤 용어가 있는지 모를 때 먼저 사용한다.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def text_result(text, is_error=False):
    """tools/call 결과의 표준 모양. content는 '블록' 배열이고, 가장 흔한 블록이 text다."""
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


class RpcError(Exception):
    """JSON-RPC 수준의 오류 (프로토콜 오류). 응답의 result 대신 error 필드로 나간다."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def call_tool(name, arguments):
    if name == "lookup_term":
        term = arguments.get("term")
        if not isinstance(term, str) or not term.strip():
            # 필수 인자가 없다 -> 프로토콜 오류 -32602
            raise RpcError(INVALID_PARAMS, "'term'(문자열) 인자가 필요합니다")
        item = find_term(term)
        if item:
            aliases = ", ".join(item.get("aliases", [])) or "-"
            return text_result(f"{item['term']}: {item['definition']}\n(별칭: {aliases})")
        # "도구는 정상 동작했지만 결과가 없다"는 JSON-RPC 오류가 아니라 isError 결과로 알린다.
        # 이렇게 하면 모델이 오류 문구를 읽고 스스로 다른 검색어를 시도할 수 있다.
        names = [i["term"] for i in TERMS]
        near = difflib.get_close_matches(term, names, n=3, cutoff=0.4)
        hint = f" 비슷한 용어: {', '.join(near)}." if near else ""
        return text_result(f"'{term}'은(는) 용어집에 없습니다.{hint} list_terms로 전체 목록을 볼 수 있습니다.", True)

    if name == "list_terms":
        return text_result("\n".join(f"- {i['term']}" for i in TERMS))

    # 모르는 도구 이름은 프로토콜 오류(-32602)다.
    raise RpcError(INVALID_PARAMS, f"알 수 없는 도구: {name}")


# --- 3. 메시지 한 개 처리 ---------------------------------------------------------
def handle(msg):
    """요청 하나를 받아 응답 dict를 돌려준다. 알림이면 None (= 아무것도 쓰지 않음)."""
    method = msg.get("method")
    params = msg.get("params") or {}
    msg_id = msg.get("id")  # 알림에는 id가 없다

    # 알림(id 없음)에는 절대 답장하지 않는다. 모르는 알림도 조용히 무시한다.
    if msg_id is None:
        if method == "notifications/initialized":
            log("클라이언트 초기화 완료")
        return None

    try:
        if method == "initialize":
            # 클라이언트가 말한 버전을 우리가 알면 그대로 echo, 모르면 우리 최신 버전을 제안한다.
            wanted = params.get("protocolVersion")
            version = wanted if wanted in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            log(f"initialize: 클라이언트={params.get('clientInfo')} 요청 버전={wanted} -> 응답 버전={version}")
            result = {
                "protocolVersion": version,
                # capabilities: 이 서버가 할 수 있는 일. tools만 지원한다고 선언한다.
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "team-glossary-mcp", "version": __version__},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            log(f"tools/call: {params.get('name')} {params.get('arguments')}")
            result = call_tool(params.get("name"), params.get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            raise RpcError(METHOD_NOT_FOUND, f"모르는 method: {method}")
    except RpcError as err:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": err.code, "message": err.message}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


# --- 4. 메인 루프: 한 줄 읽고, 처리하고, 한 줄 쓴다 ---------------------------------------
def send(obj):
    # ensure_ascii=False: 한글을 \uXXXX로 바꾸지 않고 그대로 보낸다 (사람이 읽기 좋다).
    # json.dumps는 줄바꿈을 \n 으로 이스케이프하므로 결과는 항상 한 줄이다.
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()  # flush를 빼먹으면 응답이 버퍼에 갇혀 클라이언트가 영원히 기다린다.


def main():
    # --- 입출력을 UTF-8로 고정 (M1은 파일 맨 위에서 했지만, 패키지는 import만 해도 부작용이 없도록 main 안에서 한다)
    # Windows의 파이썬은 stdin/stdout을 cp949로 열기 때문에, 한글이 든 JSON이 깨진다.
    # newline="\n"은 Windows가 줄 끝을 \r\n으로 바꿔 쓰지 않게 한다 (JSON 한 줄 = \n으로 끝남).
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8")
    log(f"시작: 용어 {len(TERMS)}개, stdin 대기 중")
    for line in sys.stdin:  # 에이전트가 stdin을 닫으면 반복이 끝나고 프로세스가 종료된다.
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": "JSON 파싱 실패"}})
            continue
        if not isinstance(msg, dict):
            send({"jsonrpc": "2.0", "id": None, "error": {"code": INVALID_REQUEST, "message": "객체가 아님"}})
            continue
        response = handle(msg)
        if response is not None:
            send(response)
    log("stdin 종료, 서버를 마칩니다")


if __name__ == "__main__":
    main()
