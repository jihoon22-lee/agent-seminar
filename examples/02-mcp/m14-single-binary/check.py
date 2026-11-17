"""M14 check: Rust로 만든 단일 실행 파일 MCP 서버를 빌드하고, JSON-RPC 대화·opencode 연결·시작 시간을 확인한다.

cargo가 없거나 crates를 받을 수 없으면(인터넷 없음 + 캐시 없음) 경고만 내고 건너뛴다.
"""
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402

EXE = "glossary-mcp" + (".exe" if sys.platform == "win32" else "")
BIN = HERE / "bin" / EXE
M1_SERVER = HERE.parent / "m1-stdio-minimal" / "server.py"

config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
entry = config["mcp"]["glossary"]
check("opencode.json은 v1 형식이고 command가 ./bin/glossary-mcp 하나다 (.exe 없이 두 OS 공용)",
      entry["type"] == "local" and entry["command"] == ["./bin/glossary-mcp"] and "model" not in config
      and config.get("$schema") == "https://opencode.ai/config.json")
ignore_text = (HERE / ".gitignore").read_text(encoding="utf-8") if (HERE / ".gitignore").exists() else ""
check("폴더의 .gitignore가 target/ 과 bin/ 을 막는다", "target/" in ignore_text and "bin/" in ignore_text)

# --- 빌드 ----------------------------------------------------------------------------------
if not shutil.which("cargo"):
    check("cargo가 설치되어 있다 (없으면 M14는 건너뜀: rustup.rs)", False, soft=True)
    finish()
t0 = time.time()
proc = subprocess.run([sys.executable, str(HERE / "build.py")], cwd=str(HERE), capture_output=True, timeout=900,
                      encoding="utf-8", errors="replace")
build_secs = time.time() - t0
if proc.returncode == 3:
    check("crates(serde_json)를 받을 수 없어 빌드를 건너뜀 (인터넷 또는 미러 필요)", False, soft=True)
    finish()
check("build.py: cargo build --release 후 bin/에 실행 파일이 생긴다", proc.returncode == 0 and BIN.exists(),
      (proc.stdout + proc.stderr)[-800:])
if not BIN.exists():
    finish()
print(f"       (빌드 {build_secs:.1f}초, 마지막 줄: {proc.stdout.strip().splitlines()[-1]})")


def clean_env():
    return {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}


class StdioClient:
    def __init__(self, argv, cwd):
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     cwd=str(cwd), env=clean_env())
        self.raw_lines = []
        self.n = 0

    def send(self, obj):
        data = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
        self.proc.stdin.write(data.encode("utf-8") + b"\n")
        self.proc.stdin.flush()

    def recv(self):
        line = self.proc.stdout.readline().decode("utf-8")
        self.raw_lines.append(line)
        return json.loads(line)

    def rpc(self, method, params=None):
        self.n += 1
        self.send({"jsonrpc": "2.0", "id": self.n, "method": method, **({"params": params} if params is not None else {})})
        return self.recv()

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        err = self.proc.stderr.read().decode("utf-8", "replace")
        self.proc.stderr.close()
        self.proc.stdout.close()
        return self.proc.returncode, err


INIT = {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}}

# --- 실행 파일 하나만 다른 폴더에 복사해서 실행 (glossary.json 없이도 돈다 = 내장됨) -------------------------
with tempfile.TemporaryDirectory(prefix="m14-alone-") as alone:
    lone = pathlib.Path(alone) / EXE
    shutil.copy2(BIN, lone)
    c = StdioClient([str(lone)], alone)
    r = c.rpc("initialize", INIT)
    check("실행 파일 하나만 빈 폴더로 복사해도 동작한다 (용어집이 파일 안에 들어 있다)",
          r["result"]["protocolVersion"] == "2025-11-25", str(r))
    check("initialize: 요청한 버전을 그대로 돌려주고 capabilities.tools가 있다", "tools" in r["result"]["capabilities"])
    r = c.rpc("initialize", {"protocolVersion": "1999-01-01", "capabilities": {}})
    check("initialize: 모르는 버전이면 서버의 최신 버전(2025-11-25)을 제안한다", r["result"]["protocolVersion"] == "2025-11-25")
    c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    r = c.rpc("tools/list")
    check("알림에는 답장하지 않는다 (다음 응답이 id=3)", r.get("id") == 3, str(r))
    names = [t["name"] for t in r["result"]["tools"]]
    check("tools/list: lookup_term, list_terms (description과 inputSchema 있음)",
          names == ["lookup_term", "list_terms"]
          and all(t.get("description") and t["inputSchema"]["type"] == "object" for t in r["result"]["tools"]), str(names))
    r = c.rpc("tools/call", {"name": "lookup_term", "arguments": {"term": "adr"}})
    rust_adr = r["result"]["content"][0]["text"]
    check("tools/call: 대소문자 무시하고 찾고 한글 정의가 그대로 나온다", "중요한 설계 결정" in rust_adr and r["result"]["isError"] is False, rust_adr)
    r = c.rpc("tools/call", {"name": "lookup_term", "arguments": {"term": "아키텍처 결정 기록"}})
    check("tools/call: 한글 별칭 인자 (UTF-8 모드 없이도)", r["result"]["content"][0]["text"].startswith("ADR:"))
    r = c.rpc("tools/call", {"name": "lookup_term", "arguments": {"term": "없는용어"}})
    check("없는 용어는 JSON-RPC 오류가 아니라 isError:true 결과", r["result"]["isError"] is True and "error" not in r, str(r))
    r = c.rpc("tools/call", {"name": "lookup_term", "arguments": {}})
    check("필수 인자 누락은 -32602", r.get("error", {}).get("code") == -32602, str(r))
    r = c.rpc("tools/call", {"name": "no_such_tool", "arguments": {}})
    check("모르는 도구 이름은 -32602", r.get("error", {}).get("code") == -32602, str(r))
    r = c.rpc("resources/list")
    check("모르는 method는 -32601", r.get("error", {}).get("code") == -32601, str(r))
    r = c.rpc("ping")
    check("ping -> 빈 result", r.get("result") == {}, str(r))
    c.send("{이건 JSON이 아님")
    r = c.recv()
    check("깨진 JSON 줄은 -32700이고 서버는 죽지 않는다", r.get("error", {}).get("code") == -32700 and c.rpc("ping").get("result") == {}, str(r))
    r = c.rpc("tools/call", {"name": "list_terms", "arguments": {}})
    rust_list = r["result"]["content"][0]["text"]
    rc, stderr = c.close()
    check("stdout의 모든 줄이 JSON이고, 로그는 stderr로만 나온다", all(json.loads(x) for x in c.raw_lines if x.strip()) and "[glossary-rs]" in stderr)
    check("stdin을 닫으면 정상 종료(0)한다", rc == 0, f"rc={rc}")

# --- Python M1 서버와 결과가 같은가 -----------------------------------------------------------------
py = StdioClient([sys.executable, str(M1_SERVER)], M1_SERVER.parent)
py.rpc("initialize", INIT)
py_adr = py.rpc("tools/call", {"name": "lookup_term", "arguments": {"term": "adr"}})["result"]["content"][0]["text"]
py_list = py.rpc("tools/call", {"name": "list_terms", "arguments": {}})["result"]["content"][0]["text"]
py.close()
check("같은 질문(ADR, 전체 목록)에 M1의 Python 서버와 글자 하나까지 같은 답을 준다", py_adr == rust_adr and py_list == rust_list,
      f"{py_adr!r} / {rust_adr!r}")


# --- 크기와 시작 시간 (Python M1 서버와 같은 방법으로 측정) ---------------------------------------------
def start_ms(argv, cwd, runs=15):
    """프로세스를 띄우고 initialize 응답을 받을 때까지의 시간(ms)의 중앙값."""
    times = []
    for _ in range(runs):
        t = time.perf_counter()
        cl = StdioClient(argv, cwd)
        cl.rpc("initialize", INIT)
        times.append((time.perf_counter() - t) * 1000)
        cl.close()
    return statistics.median(times), min(times)


rust_med, rust_min = start_ms([str(BIN)], HERE)
py_med, py_min = start_ms([sys.executable, str(M1_SERVER)], M1_SERVER.parent)
size_kib = BIN.stat().st_size / 1024
print(f"       실행 파일 크기: {size_kib:.0f} KiB ({EXE}, 파이썬 없이 이 파일만으로 실행)")
print(f"       시작~initialize 응답 (15회): Rust 중앙값 {rust_med:.1f}ms (최소 {rust_min:.1f}) / "
      f"Python M1 중앙값 {py_med:.1f}ms (최소 {py_min:.1f})  -> 약 {py_med / rust_med:.0f}배")
check("실행 파일이 5 MiB보다 작다 (serde_json만 쓴 릴리스 빌드)", BIN.stat().st_size < 5 * 1024 * 1024)
check("Rust 서버의 시작 시간이 Python M1 서버보다 짧다 (중앙값 기준)", rust_med < py_med, f"{rust_med:.1f} vs {py_med:.1f}")

# --- opencode ------------------------------------------------------------------------------
with Sandbox("m14") as sb:
    status = sb.mcp_list(HERE)
    check("opencode mcp list: glossary connected (command: ./bin/glossary-mcp)", status.get("glossary") == "connected", str(status))
    with FakeLLM(script=[("tool", "glossary_lookup_term", {"term": "롤백"}), "DONE"]) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
        p = sb.opencode(["run", "-m", "fake/echo", "--auto", "go"], HERE, timeout=120, extra_env=env)
        out = p.stdout + p.stderr
        requests = llm.main_requests()
        names = llm.tool_names(requests[0]) if requests else []
        results = [llm.message_text(m) for r in requests for m in r["messages"] if m.get("role") == "tool"]
    check("모델에게 제공되는 도구: glossary_lookup_term, glossary_list_terms",
          {"glossary_lookup_term", "glossary_list_terms"} <= set(names), str(names))
    check("가짜 모델이 Rust 서버의 도구를 부르고 한글 결과가 돌아간다",
          "⚙ glossary_lookup_term" in out and any("직전의 정상 버전" in r for r in results), f"{results}\n{out[-300:]}")
    if model_enabled():
        out = sb.run_model("팀 용어집에서 롤백이 무슨 뜻인지 찾아서 알려줘.", HERE)
        model_check("모델이 glossary_lookup_term 도구를 호출했다", out, "glossary_lookup_term" in out)
finish()
