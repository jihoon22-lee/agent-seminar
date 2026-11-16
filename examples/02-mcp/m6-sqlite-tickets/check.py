"""M6 check: tickets.db 생성이 결정적인지, 서버가 읽기 전용으로 DB를 열고 결과 크기를 제한하는지, opencode에서 연결되는지 확인한다."""
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402  (모델 없이 결정적으로 도구 호출을 시험하는 가짜 모델 서버)


_LAST_SYSTEM = {"text": ""}


def today_in_prompt():
    """직전 scripted_call의 시스템 프롬프트에 오늘 날짜가 들어 있는지 (자정 경계를 고려해 어제/내일도 허용)."""
    from datetime import date, timedelta
    candidates = [(date.today() + timedelta(days=d)).strftime("%a %b %d %Y") for d in (-1, 0, 1)]
    return any(c in _LAST_SYSTEM["text"] for c in candidates)


def scripted_call(sb, cwd, tool, args, extra_env=None):
    """가짜 모델이 `tool`을 `args`로 부르게 한다. 반환: (opencode 출력, 모델에게 제공된 도구 이름들, 모델에게 돌아간 도구 결과 텍스트들)."""
    with FakeLLM(script=[("tool", tool, args), "DONE"]) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "PYTHONUTF8": "0"}
        env.update(extra_env or {})
        proc = sb.opencode(["run", "-m", "fake/echo", "--auto", "go"], cwd, timeout=120, extra_env=env)
        requests = llm.main_requests()
        names = FakeLLM.tool_names(requests[0]) if requests else []
        if requests:
            _LAST_SYSTEM["text"] = " ".join(llm.message_text(m) for m in requests[0]["messages"] if m.get("role") == "system")
        results = []
        for request in requests:
            for message in request["messages"]:
                text = llm.message_text(message)
                if message.get("role") == "tool" and text not in results:
                    results.append(text)
    return proc.stdout + proc.stderr, names, results
FIXED_DAY = "2026-03-18"


def clean_env(**extra):
    """자식 프로세스용 환경: PYTHONUTF8/PYTHONIOENCODING을 제거해 Windows 기본 인코딩(cp949) 상태에서도 서버가 동작하는지 확인한다."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env.update(extra)
    return env


def tool_seen(transcript, name):
    """성공(⚙)뿐 아니라 실패(✗, isError 결과)한 호출도 포함해 도구 이름이 transcript에 나오는지 본다."""
    return any(name in line for line in transcript.splitlines() if line.lstrip().startswith(("⚙", "✗", "→")))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rows_of(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
    finally:
        conn.close()


def scalar(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def run_prepare(*args):
    return subprocess.run([sys.executable, str(HERE / "prepare.py"), *args], cwd=str(HERE), capture_output=True, timeout=60)


class Server:
    def __init__(self, db_path):
        env = clean_env(TICKETS_DB=str(db_path))
        self.proc = subprocess.Popen([sys.executable, str(HERE / "server.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, cwd=str(HERE), env=env)
        self.n = 0
        self.rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}})

    def rpc(self, method, params=None):
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False).encode("utf-8") + b"\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline().decode("utf-8"))

    def call(self, name, **arguments):
        resp = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if "error" in resp:
            return resp
        return {"isError": resp["result"]["isError"], "text": resp["result"]["content"][0]["text"]}

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)
        self.proc.stderr.read()
        self.proc.stderr.close()
        self.proc.stdout.close()


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = pathlib.Path(tmp_name)
    db1, db2 = tmp / "a.db", tmp / "b.db"

    # --- prepare.py: 결정적 생성 ----------------------------------------------------------------------------
    p1, p2 = run_prepare("--today", FIXED_DAY, "--db", str(db1)), run_prepare("--today", FIXED_DAY, "--db", str(db2))
    check("prepare.py --today 로 tickets DB가 만들어진다", p1.returncode == 0 and db1.exists(), p1.stderr.decode("utf-8", "replace"))
    r1, r2 = rows_of(db1), rows_of(db2)
    check("같은 기준일이면 두 번 만들어도 내용이 같다 (결정적)", r1 == r2 and len(r1) > 0)
    check("티켓은 약 200건이다", 190 <= len(r1) <= 210, str(len(r1)))
    run_prepare("--today", FIXED_DAY, "--db", str(db1))
    check("prepare.py는 여러 번 실행해도 같은 결과 (idempotent)", rows_of(db1) == r1)
    other = tmp / "c.db"
    run_prepare("--today", "2026-04-01", "--db", str(other))
    check("기준일이 다르면 날짜가 달라진다", rows_of(other) != r1)

    prepare = load_module("m6_prepare", HERE / "prepare.py")
    os.environ["TICKETS_DB"] = str(db1)
    server = load_module("m6_server", HERE / "server.py")
    del os.environ["TICKETS_DB"]  # 아래 opencode 실행에 임시 DB 경로가 새어 들어가지 않도록 곧바로 지운다
    check("server.py의 SERVICES/SEVERITIES/STATUSES가 prepare.py와 같다",
          server.SERVICES == prepare.SERVICES and server.SEVERITIES == prepare.SEVERITIES and server.STATUSES == prepare.STATUSES)
    check("DB의 값이 모두 허용 목록 안에 있다 (service/severity/status)",
          all(r[2] in server.SERVICES and r[3] in server.SEVERITIES and r[5] in server.STATUSES for r in r1))
    check("assignee는 dev-a 같은 가상 이름뿐이다", {r[6] for r in r1} <= {"dev-a", "dev-b", "dev-c", "dev-d", "dev-e"})

    # --- 읽기 전용 -------------------------------------------------------------------------------------------
    conn = server.open_readonly()
    try:
        try:
            conn.execute("DELETE FROM tickets")
            wrote = True
        except sqlite3.OperationalError as err:
            wrote, message = False, str(err)
        check("서버의 DB 연결은 읽기 전용이다 (DELETE가 'readonly database'로 거부됨)", not wrote and "readonly" in message, message if not wrote else "쓰기가 허용됨")
        try:
            conn.execute("DROP TABLE tickets")
            dropped = True
        except sqlite3.OperationalError:
            dropped = False
        check("DROP TABLE도 거부된다", not dropped)
    finally:
        conn.close()

    # --- 도구 동작 (stdio) -----------------------------------------------------------------------------------------
    before = sha(db1)
    s = Server(db1)
    names = [t["name"] for t in s.rpc("tools/list")["result"]["tools"]]
    check("tools/list: search_tickets, get_ticket, ticket_stats", names == ["search_tickets", "get_ticket", "ticket_stats"], str(names))
    tools = {t["name"]: t for t in s.rpc("tools/list")["result"]["tools"]}
    check("도구 설명에 날짜 형식(YYYY-MM-DD)과 최대 건수가 적혀 있다",
          "YYYY-MM-DD" in tools["search_tickets"]["description"] and "20건" in tools["search_tickets"]["description"]
          and tools["search_tickets"]["inputSchema"]["properties"]["service"]["enum"] == server.SERVICES)

    since, until = "2026-03-10", "2026-03-16"
    expected = scalar(db1, "SELECT COUNT(*) FROM tickets WHERE service='payment' AND created_at >= ? AND created_at <= ?",
                      (since, until + " 23:59"))
    res = s.call("search_tickets", service="payment", since=since, until=until, limit=3)
    check("search_tickets: 서비스+기간 필터 건수가 SQL 직접 집계와 같다", not res["isError"] and res["text"].startswith(f"총 {expected}건 중 최신 3건 표시"), res["text"][:200])
    check("search_tickets: 결과는 한글이 깨지지 않고 최신순이다", "결제" in res["text"] and res["text"].index("2026-03-1") > 0)

    res = s.call("search_tickets", limit=500)
    shown = sum(1 for line in res["text"].splitlines() if line.startswith("#"))
    check("limit=500을 줘도 최대 20건만 돌려준다 (결과 크기 제한)", shown == 20 and "최신 20건 표시" in res["text"], res["text"][:120])
    res = s.call("search_tickets")
    check("limit 기본값은 10건이다", sum(1 for line in res["text"].splitlines() if line.startswith("#")) == 10)
    res = s.call("search_tickets", service="payment", status="resolved", query="롤백")
    check("query는 제목/해결 내용에서 찾는다", not res["isError"] and ("롤백" in res["text"] or "조건에 맞는 티켓이 없습니다" in res["text"]))
    check("검색어의 LIKE 와일드카드(_)는 문자 그대로 취급한다", s.call("search_tickets", query="_")["text"] == "조건에 맞는 티켓이 없습니다.")
    check("SQL 인젝션 문자열은 그냥 검색어일 뿐이다", s.call("search_tickets", query="' OR 1=1 --")["text"] == "조건에 맞는 티켓이 없습니다.")
    res = s.call("search_tickets", service="pay")
    check("잘못된 service 값은 isError:true + 허용 값 안내", res["isError"] and "payment" in res["text"], str(res))
    res = s.call("search_tickets", since="어제")
    check("날짜 형식이 틀리면 isError:true + 형식 안내", res["isError"] and "YYYY-MM-DD" in res["text"], str(res))

    sample = r1[len(r1) // 2]
    res = s.call("get_ticket", id=sample[0])
    check("get_ticket: 한 건의 모든 열을 돌려준다", not res["isError"] and sample[4] in res["text"] and f"id: {sample[0]}" in res["text"], res["text"][:200])
    res = s.call("get_ticket", id=99999)
    check("get_ticket: 없는 번호는 isError:true", res["isError"] and "찾을 수 없습니다" in res["text"])
    res = s.call("ticket_stats", group_by="service")
    check("ticket_stats: 서비스별 합계가 전체 건수와 같다", f"합계 {len(r1)}건" in res["text"], res["text"][:120])
    res = s.call("ticket_stats", group_by="severity", service="payment", since=since, until=until)
    check("ticket_stats: 기간/서비스 필터가 적용된다", f"합계 {expected}건" in res["text"], res["text"][:120])
    res = s.call("ticket_stats", group_by="id; DROP TABLE tickets")
    check("ticket_stats: group_by는 화이트리스트만 허용한다", res["isError"] and "허용 값" in res["text"], str(res))
    res = s.call("no_such_tool")
    check("모르는 도구는 JSON-RPC -32602", res.get("error", {}).get("code") == -32602, str(res))
    s.close()
    check("도구를 모두 호출한 뒤에도 DB 파일이 바뀌지 않았다 (sha256 동일)", sha(db1) == before)

    s = Server(tmp / "missing.db")
    res = s.call("search_tickets")
    check("DB가 없으면 isError:true + prepare.py 실행 안내 (서버는 죽지 않는다)", res["isError"] and "prepare.py" in res["text"], str(res))
    s.close()

# --- opencode (실제 폴더, 오늘 기준 DB) ----------------------------------------------------------------------------
p = run_prepare()
check("prepare.py (기준일=오늘)로 tickets.db 생성", p.returncode == 0 and (HERE / "tickets.db").exists())
with Sandbox("m6") as sb:
    status = sb.mcp_list(HERE, extra_env={"PYTHONUTF8": "0"})
    check("opencode mcp list: tickets connected", status.get("tickets") == "connected", str(status))
    out, names, results = scripted_call(sb, HERE, "tickets_search_tickets", {"service": "payment", "since": "2000-01-01", "limit": 500})
    check("(가짜 모델) 모델에게 tickets_search_tickets / get_ticket / ticket_stats가 제공된다",
          all(n in names for n in ("tickets_search_tickets", "tickets_get_ticket", "tickets_ticket_stats")), str(names))
    check("(가짜 모델) limit=500으로 불러도 모델에게 돌아간 결과는 20건 이하 + 총 건수 안내",
          bool(results) and results[0].startswith("총 ") and sum(1 for l in results[0].splitlines() if l.startswith("#")) == 20, results[0][:200] if results else out[-300:])
    check("opencode가 모델에게 오늘 날짜를 알려 준다 (시스템 프롬프트의 \"Today's date\")", today_in_prompt(), "시스템 프롬프트에서 날짜를 찾지 못함")
    if model_enabled():
        # PYTHONUTF8=0: Sandbox가 켜 둔 UTF-8 모드를 꺼서 Windows 기본 인코딩 상태에서 시험한다
        out = sb.run_model("지난주 payment 서비스 장애 티켓 요약해줘", HERE, extra_env={"PWD": str(HERE), "PYTHONUTF8": "0"})
        model_check("모델이 tickets_search_tickets 도구를 호출했다", out, tool_seen(out, "tickets_search_tickets"))
        model_check("모델이 payment 서비스 필터로 호출했다", out, any("payment" in l for l in out.splitlines() if l.lstrip().startswith("⚙")))
        print(out[-1800:])
finish()
