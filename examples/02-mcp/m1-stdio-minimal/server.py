#!/usr/bin/env python3
"""M1 - 표준 라이브러리만으로 만든 가장 작은 MCP 서버 (stdio).

이 파일 하나가 "MCP 서버가 실제로 하는 일"의 전부다.

    에이전트(opencode)  --- 표준 입력(stdin) --->  이 프로세스
    에이전트(opencode)  <-- 표준 출력(stdout) ---  이 프로세스

주고받는 것은 "JSON 한 덩어리 = 한 줄" 뿐이다. (JSON-RPC 2.0, 줄바꿈으로 구분)

    요청     {"jsonrpc":"2.0","id":1,"method":"tools/list"}
    응답     {"jsonrpc":"2.0","id":1,"result":{...}}
    알림     {"jsonrpc":"2.0","method":"notifications/initialized"}   <- id가 없다 = 답장을 주면 안 된다

서버가 구현해야 하는 최소 메서드는 다섯 가지다.

    initialize                    첫 인사. 프로토콜 버전과 기능(capabilities)을 맞춘다.
    notifications/initialized     "인사 끝, 이제부터 일하자"는 알림. 답장 없음.
    tools/list                    "어떤 도구를 갖고 있나요?" -> 이름, 설명, 입력 스키마 목록
    tools/call                    "이 도구를 이 인자로 실행해 줘" -> 결과
    ping                          살아 있는지 확인

가장 중요한 규칙 하나: stdout에는 JSON-RPC 메시지만 쓴다.
로그, 디버그 출력, print()는 전부 stderr로 보낸다. (opencode 1.19.5에서 확인: 줄바꿈이 있는
출력 한 줄은 무시되지만, 줄바꿈 없는 출력이 JSON 앞에 붙으면 스트림이 깨져 30초 뒤 연결이
실패한다. 안 깨지는 경우가 있어도 stdout 출력에 기대지 말 것.)

실행 확인 (에이전트 없이): python raw_session.py
"""
import difflib
import json
import sys
from pathlib import Path

# --- 1. 입출력을 UTF-8로 고정 ------------------------------------------------
# Windows의 파이썬은 stdin/stdout을 cp949로 열기 때문에, 한글이 든 JSON이 깨진다.
# newline="\n"은 Windows가 줄 끝을 \r\n으로 바꿔 쓰지 않게 한다 (JSON 한 줄 = \n으로 끝남).
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
sys.stderr.reconfigure(encoding="utf-8")

# 이 서버가 알고 있는 프로토콜 버전들 (최신순).
# 클라이언트가 이 중 하나를 요청하면 그대로 따라가고, 모르는 버전이면 우리 최신 버전을 답한다.
SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

# JSON-RPC 표준 오류 코드
PARSE_ERROR = -32700       # 줄이 JSON이 아님
INVALID_REQUEST = -32600   # JSON이지만 JSON-RPC 요청 모양이 아님
METHOD_NOT_FOUND = -32601  # 모르는 method
INVALID_PARAMS = -32602    # 인자가 잘못됨 (모르는 도구 이름, 필수 인자 누락 등)

HERE = Path(__file__).resolve().parent


def log(*parts):
    """로그는 반드시 stderr로. (stdout은 프로토콜 전용)"""
    print("[glossary]", *parts, file=sys.stderr, flush=True)


# --- 2. 데이터: 용어집 ---------------------------------------------------------
def load_glossary():
    data = json.loads((HERE / "glossary.json").read_text(encoding="utf-8"))
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


# --- 3. 도구 정의 ---------------------------------------------------------------
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


# --- 4. 메시지 한 개 처리 ---------------------------------------------------------
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
                "serverInfo": {"name": "glossary-m1", "version": "1.0.0"},
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


# --- 5. 메인 루프: 한 줄 읽고, 처리하고, 한 줄 쓴다 ---------------------------------------
def send(obj):
    # ensure_ascii=False: 한글을 \uXXXX로 바꾸지 않고 그대로 보낸다 (사람이 읽기 좋다).
    # json.dumps는 줄바꿈을 \n 으로 이스케이프하므로 결과는 항상 한 줄이다.
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()  # flush를 빼먹으면 응답이 버퍼에 갇혀 클라이언트가 영원히 기다린다.


def main():
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
