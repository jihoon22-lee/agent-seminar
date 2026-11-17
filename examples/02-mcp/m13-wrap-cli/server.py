#!/usr/bin/env python3
"""M13 - 이미 있는 CLI(git)를 읽기 전용 MCP 도구로 감싼다 (표준 라이브러리만).

서버를 실행한 폴더(현재 작업 폴더)의 git 저장소를 대상으로 한다. opencode를 저장소 안에서 실행하면
그 저장소가 대상이 된다. 도구는 세 개이고 모두 읽기 전용이다.

    git_log         최근 커밋 목록 (선택: 경로, 개수)
    git_blame       파일의 줄 범위를 누가 언제 고쳤는지
    git_diff_stat   두 리비전 사이에 어떤 파일이 얼마나 바뀌었는지

"CLI를 감싼다"는 것은 모델이 보낸 값을 CLI 인자로 넘긴다는 뜻이다. 그래서 이 파일의 대부분은
기능이 아니라 방어다. 아래 일곱 가지가 이 예제가 가르치는 전부이고, 각각 check.py가 확인한다.

    1. 셸을 거치지 않는다   인자 리스트로 실행(shell=False). 모델 입력이 명령줄로 해석될 길이 없다.
    2. '-'로 시작하는 값 거부   "--output=파일" 같은 옵션 주입을 막는다. 경로 앞에는 '--'도 붙인다.
    3. 저장소 밖 경로 거부   '../../etc/passwd', 절대 경로, 심볼릭 링크로 빠져나가는 경로.
    4. 출력 줄 수 제한     넘치면 잘라 내고 "…(N줄 생략)"이라고 알린다. 모델이 잘린 줄 모르면 안 된다.
    5. 시간 제한          멈춘 git이 에이전트를 붙잡지 못하게 한다.
    6. 실패는 isError     git이 0이 아닌 코드로 끝나면 stderr 문장을 그대로 돌려준다. 모델이 읽고 고친다.
    7. 출력 형식 고정      색, 페이저, 지역화, 경로 이스케이프를 끄고 --format을 직접 지정한다. UTF-8로 읽는다.

실행 확인 (에이전트 없이): 저장소 안에서 python server.py 를 띄우고 JSON 줄을 넣어 본다. (README 참고)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
sys.stderr.reconfigure(encoding="utf-8")

SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32600, -32601, -32602

GIT_CMD = ["git"]          # 실행할 git. check.py가 시간 제한을 시험할 때만 바꾼다.
TIMEOUT_SEC = 10           # 5. git 한 번에 줄 수 있는 시간
MAX_LINES = 40             # 4. 한 번에 돌려줄 최대 줄 수
MAX_COUNT = 50             # git_log가 요청받을 수 있는 최대 커밋 수
DEFAULT_COUNT = 10


def log(*parts):
    print("[wrap-git]", *parts, file=sys.stderr, flush=True)


class ToolError(Exception):
    """모델에게 isError:true 결과로 돌려줄 문장. (프로토콜 오류가 아니라 도구 오류)"""


# --- 7. git 실행: 항상 같은 모양으로 ------------------------------------------------
def run_git(args, cwd=None, timeout=None, git_cmd=None):
    """git을 인자 리스트로 실행하고 stdout 텍스트를 돌려준다. 실패하면 ToolError.

    - 셸을 쓰지 않는다. args의 각 원소는 git의 인자 하나로 그대로 전달된다. (1)
    - 앞에 붙는 -c 옵션들이 출력 모양을 고정한다. (7)
        core.quotepath=false         한글 파일명을 "\\355\\225..." 로 이스케이프하지 않는다
        i18n.logOutputEncoding=utf-8 로그 출력을 UTF-8로
        color.ui=never               색 코드 없음 (--no-color도 명령별로 따로 준다)
        core.pager=cat               페이저가 뜨지 않는다
    - LC_ALL=C 로 git 안내 문구를 영어로 고정한다. 모델이 읽을 오류 문장이 환경마다 달라지지 않는다.
    """
    cmd = [*(git_cmd or GIT_CMD), "-c", "core.quotepath=false", "-c", "i18n.logOutputEncoding=utf-8",
           "-c", "color.ui=never", "-c", "core.pager=cat", *args]
    env = dict(os.environ)
    env.update({"LC_ALL": "C", "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0", "GIT_PAGER": "cat"})
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=timeout or TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        raise ToolError(f"git이 {timeout or TIMEOUT_SEC}초 안에 끝나지 않아 중단했습니다.")
    except FileNotFoundError:
        raise ToolError("git 실행 파일을 찾을 수 없습니다. git이 설치되어 PATH에 있어야 합니다.")
    out = proc.stdout.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        # 6. 실패 -> stderr 문장을 그대로. "fatal: bad revision 'x'" 같은 문장이 곧 다음 행동의 단서다.
        err = proc.stderr.decode("utf-8", errors="replace").strip() or "(stderr 없음)"
        raise ToolError(f"git이 종료 코드 {proc.returncode}로 실패했습니다: {err}")
    return out


def repo_root():
    """작업 폴더가 속한 저장소의 최상위 폴더. 저장소가 아니면 ToolError."""
    return Path(run_git(["rev-parse", "--show-toplevel"]).strip()).resolve()


# --- 2, 3. 입력 검증 ----------------------------------------------------------------
def check_value(name, value):
    """문자열 인자의 공통 검사. '-'로 시작하면 git이 옵션으로 읽는다."""
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"'{name}'은(는) 비어 있지 않은 문자열이어야 합니다.")
    if value.startswith("-"):
        raise ToolError(f"'{name}' 값은 '-'로 시작할 수 없습니다 (옵션 주입 방지): {value!r}")
    if any(ord(ch) < 32 for ch in value):
        raise ToolError(f"'{name}' 값에 제어 문자(줄바꿈 등)를 넣을 수 없습니다.")
    return value


def check_path(root, value):
    """저장소 안의 경로인지 확인하고, 저장소 기준 상대 경로(슬래시 표기)로 돌려준다."""
    check_value("path", value)
    target = Path(value)
    if target.is_absolute():
        raise ToolError("절대 경로는 쓸 수 없습니다. 저장소 기준 상대 경로를 쓰세요.")
    resolved = (root / target).resolve()  # '..'과 심볼릭 링크를 풀어 실제 위치를 본다
    try:
        rel = resolved.relative_to(root)
    except ValueError:
        raise ToolError(f"저장소 밖의 경로입니다: {value!r}")
    return rel.as_posix()


def check_int(name, value, low, high, default=None):
    if value is None and default is not None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ToolError(f"'{name}'은(는) {low}~{high} 사이 정수여야 합니다.")
    return value


# --- 4. 출력 줄 수 제한 ---------------------------------------------------------------
def clip(text):
    lines = text.rstrip("\n").split("\n") if text.strip() else []
    if len(lines) <= MAX_LINES:
        return "\n".join(lines) if lines else "(출력 없음)"
    hidden = len(lines) - MAX_LINES
    return "\n".join(lines[:MAX_LINES]) + f"\n…({hidden}줄 생략)"


# --- 도구 구현 -------------------------------------------------------------------------
def git_log(args):
    root = repo_root()
    count = check_int("max_count", args.get("max_count"), 1, MAX_COUNT, DEFAULT_COUNT)
    cmd = ["log", "--no-color", "--date=short", "--format=%h  %ad  %an  %s", "-n", str(count)]
    path = args.get("path")
    if path is not None:
        cmd += ["--", check_path(root, path)]  # '--' 뒤는 항상 경로로만 해석된다
    return clip(run_git(cmd, cwd=root))


def git_blame(args):
    root = repo_root()
    rel = check_path(root, args.get("file"))
    start = check_int("start_line", args.get("start_line"), 1, 10**7, 1)
    end = check_int("end_line", args.get("end_line"), 1, 10**7, start + MAX_LINES - 1)
    if end < start:
        raise ToolError("end_line은 start_line 이상이어야 합니다.")
    out = run_git(["blame", "--date=short", "-L", f"{start},{end}", "--", rel], cwd=root)
    return clip(out)


def git_diff_stat(args):
    root = repo_root()
    old = check_value("from", args.get("from"))
    new = check_value("to", args.get("to"))
    # --no-ext-diff / --no-textconv: 저장소 설정에 적힌 외부 프로그램이 실행되지 않게 한다.
    # 마지막 '--'는 리비전과 경로의 모호함을 없앤다.
    cmd = ["diff", "--stat", "--stat-width=100", "--no-color", "--no-ext-diff", "--no-textconv", old, new, "--"]
    return clip(run_git(cmd, cwd=root))


TOOLS = [
    {
        "name": "git_log",
        "description": (
            "현재 저장소의 최근 커밋을 한 줄씩 보여 준다 (해시, 날짜, 작성자, 제목). 읽기 전용. "
            "특정 파일이나 폴더의 이력만 보려면 path를 준다. 누가 언제 무엇을 바꿨는지 찾는 첫 단계로 쓴다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "저장소 기준 상대 경로 (선택). 예: 'src/pricing.py'"},
                "max_count": {"type": "integer", "description": f"가져올 커밋 수 (1~{MAX_COUNT}, 기본 {DEFAULT_COUNT})"},
            },
        },
    },
    {
        "name": "git_blame",
        "description": (
            "파일의 줄 범위마다 마지막으로 고친 커밋, 작성자, 날짜를 보여 준다. 읽기 전용. "
            f"한 번에 최대 {MAX_LINES}줄이다. 큰 파일은 start_line/end_line으로 나눠서 본다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "저장소 기준 상대 경로. 예: 'src/pricing.py'"},
                "start_line": {"type": "integer", "description": "시작 줄 (1부터, 기본 1)"},
                "end_line": {"type": "integer", "description": f"끝 줄 (기본: 시작 줄 + {MAX_LINES - 1})"},
            },
            "required": ["file"],
        },
    },
    {
        "name": "git_diff_stat",
        "description": (
            "두 리비전 사이에 어떤 파일이 몇 줄 바뀌었는지 요약한다 (git diff --stat). 읽기 전용. "
            "리비전은 커밋 해시, 브랜치, 'HEAD~3' 같은 이름이다."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "from": {"type": "string", "description": "기준 리비전. 예: 'HEAD~3'"},
                "to": {"type": "string", "description": "비교할 리비전. 예: 'HEAD'"},
            },
            "required": ["from", "to"],
        },
    },
]
HANDLERS = {"git_log": git_log, "git_blame": git_blame, "git_diff_stat": git_diff_stat}


def text_result(text, is_error=False):
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def call_tool(name, arguments):
    handler = HANDLERS.get(name)
    if handler is None:
        raise RpcError(INVALID_PARAMS, f"알 수 없는 도구: {name}")
    if not isinstance(arguments, dict):
        raise RpcError(INVALID_PARAMS, "arguments는 객체여야 합니다")
    try:
        return text_result(handler(arguments))
    except ToolError as err:
        log(f"{name} 거부/실패: {err}")
        return text_result(str(err), True)


# --- JSON-RPC (M1과 같다) -----------------------------------------------------------
def handle(msg):
    method, params, msg_id = msg.get("method"), msg.get("params") or {}, msg.get("id")
    if msg_id is None:  # 알림에는 답장하지 않는다
        return None
    try:
        if method == "initialize":
            wanted = params.get("protocolVersion")
            version = wanted if wanted in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            result = {"protocolVersion": version, "capabilities": {"tools": {}},
                      "serverInfo": {"name": "wrap-git-m13", "version": "1.0.0"}}
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


def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    log(f"시작: 작업 폴더={Path.cwd()}")
    for line in sys.stdin:
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
    log("stdin 종료")


if __name__ == "__main__":
    main()
