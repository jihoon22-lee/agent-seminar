#!/usr/bin/env python3
"""M3 - 환경 변수로 설정을 받는 MCP 서버 (stdio).

M1과 같은 용어집 서버인데, 설정과 비밀 값을 코드가 아니라 "환경 변수"로 받는다.

    GLOSSARY_PATH   용어집 JSON 파일 경로 (없으면 server.py 옆의 glossary.json)
    API_TOKEN       (가상의) 용어집 백엔드에 쓸 인증 토큰. 없으면 도구가 거절한다
    LOG_LEVEL       DEBUG / INFO / WARNING / ERROR (기본 INFO). 로그는 stderr로만 나간다

환경 변수는 opencode.json의 mcp.<이름>.environment 에서 넣어 준다.
JSON-RPC 처리 뼈대는 M1과 같다. 자세한 설명은 ../m1-stdio-minimal/server.py 를 보자.
"""
import difflib
import json
import logging
import os
import sys
from pathlib import Path

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
sys.stderr.reconfigure(encoding="utf-8")

SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
METHOD_NOT_FOUND, INVALID_PARAMS, PARSE_ERROR = -32601, -32602, -32700
HERE = Path(__file__).resolve().parent

# --- 설정 읽기 ----------------------------------------------------------------
# os.environ.get(이름, 기본값). 값이 아예 없을 때와 "빈 문자열"일 때를 모두 "없음"으로 취급한다.
# (opencode.json에서 {env:DEMO_API_TOKEN}의 환경 변수가 정의되지 않았다면 빈 문자열이 넘어온다)
LOG_LEVEL = (os.environ.get("LOG_LEVEL") or "INFO").upper()
API_TOKEN = os.environ.get("API_TOKEN") or ""
GLOSSARY_PATH = Path(os.environ.get("GLOSSARY_PATH") or HERE / "glossary.json")

# 로그는 stderr로만. stdout은 프로토콜 전용이다.
logging.basicConfig(stream=sys.stderr, level=getattr(logging, LOG_LEVEL, logging.INFO),
                    format="[glossary-env] %(levelname)s %(message)s")
log = logging.getLogger("glossary")


def load_glossary():
    # 상대 경로면 "서버 프로세스의 현재 폴더" 기준이다. (opencode는 프로젝트 폴더에서 서버를 띄운다)
    return json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))["terms"]


TERMS = load_glossary()


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


def token_missing_result():
    """토큰이 없을 때의 거절 메시지. 모델이 읽고 사용자에게 그대로 전달할 수 있게 구체적으로 쓴다."""
    return text_result(
        "API_TOKEN 환경 변수가 설정되지 않아 용어집을 조회할 수 없습니다. "
        "opencode.json의 mcp.glossary-env.environment.API_TOKEN 값을 확인하세요. "
        "({env:DEMO_API_TOKEN}을 쓰는 경우 opencode를 실행하는 셸에서 DEMO_API_TOKEN을 먼저 설정해야 합니다.)",
        True,
    )


# --- 도구 ---------------------------------------------------------------------
TOOLS = [
    {
        "name": "lookup_term",
        "description": (
            "팀 용어집에서 용어 하나의 뜻을 찾는다. ADR, SLO, 롤백, 카나리 배포 같은 팀 내부 용어의 정의가 "
            "필요할 때 사용한다. 영어 이름이나 별칭으로도 찾을 수 있다. API_TOKEN 설정이 필요하다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"term": {"type": "string", "description": "찾을 용어. 예: 'ADR', '카나리 배포'"}},
            "required": ["term"],
        },
    },
    {
        "name": "list_terms",
        "description": "팀 용어집에 등록된 모든 용어 이름을 나열한다. API_TOKEN 설정이 필요하다.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "server_info",
        "description": (
            "이 용어집 서버가 어떤 설정으로 떠 있는지 보여 준다 (용어집 경로, 로그 수준, 토큰 설정 여부). "
            "토큰 값 자체는 보여 주지 않는다. 용어 조회가 실패할 때 원인을 확인하는 용도."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def call_tool(name, arguments):
    if name == "server_info":
        # 토큰은 "설정됨/안 됨"만 알려 준다. 값, 앞 글자, 길이도 노출하지 않는 것이 안전하다.
        token_state = "설정됨" if API_TOKEN else "없음"
        return text_result(
            f"GLOSSARY_PATH={GLOSSARY_PATH}\nLOG_LEVEL={LOG_LEVEL}\nAPI_TOKEN={token_state}\n용어 수={len(TERMS)}"
        )

    if name in ("lookup_term", "list_terms"):
        if not API_TOKEN:
            log.warning("%s 호출이 거절됨: API_TOKEN 없음", name)
            return token_missing_result()  # 조회 도구는 토큰이 없으면 일하지 않는다
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


# --- JSON-RPC 처리 (M1과 동일) ---------------------------------------------------
def handle(msg):
    method, params, msg_id = msg.get("method"), msg.get("params") or {}, msg.get("id")
    if msg_id is None:  # 알림: 답장하지 않는다
        return None
    try:
        if method == "initialize":
            wanted = params.get("protocolVersion")
            version = wanted if wanted in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            log.info("initialize: 클라이언트=%s 버전=%s", params.get("clientInfo"), version)
            result = {"protocolVersion": version, "capabilities": {"tools": {}},
                      "serverInfo": {"name": "glossary-m3", "version": "1.0.0"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            log.debug("tools/call %s %s", params.get("name"), params.get("arguments"))
            result = call_tool(params.get("name"), params.get("arguments") or {})
        elif method == "ping":
            result = {}
        else:
            raise RpcError(METHOD_NOT_FOUND, f"모르는 method: {method}")
    except RpcError as err:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": err.code, "message": err.message}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def main():
    log.info("시작: GLOSSARY_PATH=%s LOG_LEVEL=%s API_TOKEN=%s", GLOSSARY_PATH, LOG_LEVEL, "설정됨" if API_TOKEN else "없음")
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
