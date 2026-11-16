"""M1 check: 직접 만든 stdio MCP 서버가 JSON-RPC 핸드셰이크에 올바르게 답하고, opencode가 연결하는지 확인한다."""
import json
import os
import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402  (모델 없이 결정적으로 도구 호출을 시험하는 가짜 모델 서버)


def scripted_call(sb, cwd, tool, args, extra_env=None):
    """가짜 모델이 `tool`을 `args`로 부르게 한다. 반환: (opencode 출력, 모델에게 제공된 도구 이름들, 모델에게 돌아간 도구 결과 텍스트들)."""
    with FakeLLM(script=[("tool", tool, args), "DONE"]) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "PYTHONUTF8": "0"}
        env.update(extra_env or {})
        proc = sb.opencode(["run", "-m", "fake/echo", "--auto", "go"], cwd, timeout=120, extra_env=env)
        requests = llm.main_requests()
        names = FakeLLM.tool_names(requests[0]) if requests else []
        results = []
        for request in requests:
            for message in request["messages"]:
                text = llm.message_text(message)
                if message.get("role") == "tool" and text not in results:
                    results.append(text)
    return proc.stdout + proc.stderr, names, results
SERVER = HERE / "server.py"


def clean_env(**extra):
    """자식 프로세스용 환경: PYTHONUTF8/PYTHONIOENCODING을 제거해 Windows 기본 인코딩(cp949) 상태에서도 서버가 동작하는지 확인한다."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env.update(extra)
    return env


def tool_seen(transcript, name):
    """성공(⚙)뿐 아니라 실패(✗, isError 결과)한 호출도 포함해 도구 이름이 transcript에 나오는지 본다."""
    return any(name in line for line in transcript.splitlines() if line.lstrip().startswith(("⚙", "✗", "→")))


class StdioClient:
    """server.py를 띄워 JSON 줄을 주고받는 최소 클라이언트. 바이트 단위로 읽고 쓴다."""

    def __init__(self):
        self.proc = subprocess.Popen([sys.executable, str(SERVER)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(HERE), env=clean_env())
        self.raw_lines = []

    def send(self, obj):
        data = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
        self.proc.stdin.write(data.encode("utf-8") + b"\n")
        self.proc.stdin.flush()

    def recv(self):
        line = self.proc.stdout.readline().decode("utf-8")
        self.raw_lines.append(line)
        return json.loads(line)

    def rpc(self, msg_id, method, params=None):
        self.send({"jsonrpc": "2.0", "id": msg_id, "method": method, **({"params": params} if params is not None else {})})
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


# --- 파일 -------------------------------------------------------------------------
config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
glossary = json.loads((HERE / "glossary.json").read_text(encoding="utf-8"))["terms"]
check("opencode.json은 v1 형식(mcp.<이름>.type/command)이고 model 키가 없다",
      config["mcp"]["glossary"]["type"] == "local" and isinstance(config["mcp"]["glossary"]["command"], list)
      and "model" not in config and config.get("$schema") == "https://opencode.ai/config.json")

# --- 직접 만든 JSON-RPC 핸드셰이크 ------------------------------------------------------------
c = StdioClient()
r = c.rpc(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}})
check("initialize: 클라이언트가 요청한 protocolVersion(2025-06-18)을 그대로 돌려준다", r["result"]["protocolVersion"] == "2025-06-18", str(r))
check("initialize: capabilities에 tools가 있다", "tools" in r["result"]["capabilities"])
r = c.rpc(2, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}})
check("initialize: opencode 1.19.5가 보내는 2025-11-25도 echo한다", r["result"]["protocolVersion"] == "2025-11-25")
r = c.rpc(3, "initialize", {"protocolVersion": "1999-01-01", "capabilities": {}})
check("initialize: 모르는 버전이면 서버의 최신 버전을 제안한다", r["result"]["protocolVersion"] == "2025-11-25")

c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})  # 알림: 답장이 없어야 한다
r = c.rpc(4, "tools/list")
check("알림(notifications/initialized)에는 답장하지 않는다 (다음 응답이 id=4)", r.get("id") == 4, str(r))
names = [t["name"] for t in r["result"]["tools"]]
check("tools/list: lookup_term, list_terms", names == ["lookup_term", "list_terms"], str(names))
check("tools/list: 모든 도구에 description과 inputSchema가 있다",
      all(t.get("description") and t.get("inputSchema", {}).get("type") == "object" for t in r["result"]["tools"]))

adr = next(t for t in glossary if t["term"] == "ADR")
r = c.rpc(5, "tools/call", {"name": "lookup_term", "arguments": {"term": "adr"}})
text = r["result"]["content"][0]["text"]
check("tools/call: 대소문자 무시하고 찾으며 한글 정의가 그대로 나온다", adr["definition"] in text and r["result"]["isError"] is False, text)
r = c.rpc(6, "tools/call", {"name": "lookup_term", "arguments": {"term": "아키텍처 결정 기록"}})
check("tools/call: 한글 인자(별칭)를 받아 한글 결과를 돌려준다 (UTF-8 모드 없이도)", "ADR" in r["result"]["content"][0]["text"])
r = c.rpc(7, "tools/call", {"name": "lookup_term", "arguments": {"term": "없는용어"}})
check("tools/call: 없는 용어는 JSON-RPC 오류가 아니라 isError:true 결과", r["result"]["isError"] is True and "error" not in r, str(r))
r = c.rpc(8, "tools/call", {"name": "lookup_term", "arguments": {}})
check("tools/call: 필수 인자 누락은 -32602", r.get("error", {}).get("code") == -32602, str(r))
r = c.rpc(9, "tools/call", {"name": "no_such_tool", "arguments": {}})
check("tools/call: 모르는 도구 이름은 -32602", r.get("error", {}).get("code") == -32602, str(r))
r = c.rpc(10, "resources/list")
check("모르는 method는 -32601", r.get("error", {}).get("code") == -32601, str(r))
r = c.rpc(11, "ping")
check("ping -> 빈 result", r.get("result") == {}, str(r))
c.send("{이건 JSON이 아님")
r = c.recv()
check("깨진 JSON 줄은 -32700 (서버는 죽지 않는다)", r.get("error", {}).get("code") == -32700, str(r))
r = c.rpc(12, "ping")
check("깨진 줄 뒤에도 서버가 계속 응답한다", r.get("result") == {})
rc, stderr = c.close()
check("stdout의 모든 줄이 JSON이다 (로그는 stderr로만)", all(json.loads(line) for line in c.raw_lines if line.strip()))
check("stdin을 닫으면 서버가 정상 종료(0)한다", rc == 0, f"rc={rc}")
check("로그가 stderr로 나온다", "[glossary]" in stderr)

# --- raw_session.py ------------------------------------------------------------------------
proc = subprocess.run([sys.executable, str(HERE / "raw_session.py")], cwd=str(HERE), capture_output=True, timeout=60, env=clean_env())
out = proc.stdout.decode("utf-8", "replace")
check("raw_session.py가 끝까지 실행되고 JSON 줄을 출력한다",
      proc.returncode == 0 and out.count("  >> ") == 8 and "MCP는 결국" in out and '"isError": true' in out, out[-400:] + proc.stderr.decode("utf-8", "replace")[-300:])

# --- opencode ------------------------------------------------------------------------------
with Sandbox("m1") as sb:
    status = sb.mcp_list(HERE, extra_env={"PYTHONUTF8": "0"})
    check("opencode mcp list: glossary connected", status.get("glossary") == "connected", str(status))

    # 가짜 모델이 도구를 부르게 해서(모델 없이) opencode <-> 서버 사이의 실제 호출을 확인한다
    out, names, results = scripted_call(sb, HERE, "glossary_lookup_term", {"term": "롤백"})
    check("모델에게 제공되는 도구 이름은 서버이름_도구이름 (glossary_lookup_term, glossary_list_terms)",
          "glossary_lookup_term" in names and "glossary_list_terms" in names, str(names))
    check("한글 인자로 호출하면 한글 결과가 모델에게 돌아간다 (opencode <-> 서버, UTF-8 모드 없이)",
          any("직전의 정상 버전" in r for r in results) and "⚙ glossary_lookup_term" in out, f"{results} / {out[-300:]}")
    out, names, results = scripted_call(sb, HERE, "glossary_lookup_term", {"term": "카나리아 배포"})
    check("isError:true 결과도 모델에게 돌아가고 화면에는 실패(✗)로 표시된다",
          any("비슷한 용어: 카나리 배포" in r for r in results) and "✗ glossary_lookup_term" in out, f"{results} / {out[-300:]}")
    if model_enabled():
        prompt = "팀 용어집에서 롤백이 무슨 뜻인지 찾아서 알려줘."
        # PYTHONUTF8=0: Sandbox가 켜 둔 UTF-8 모드를 꺼서, 서버의 reconfigure가 실제로 필요한 상태에서 시험한다.
        out = sb.run_model(prompt, HERE, extra_env={"PWD": str(HERE), "PYTHONUTF8": "0"})
        model_check("모델이 glossary_lookup_term 도구를 호출했다", out, tool_seen(out, "glossary_lookup_term"))
        model_check("한글 결과가 깨지지 않고 답변에 반영됐다 (롤백 정의의 일부가 나온다)", out, any(w in out for w in ("직전의 정상 버전", "되돌리", "정상 버전")))
        print(out[-700:])
finish()
