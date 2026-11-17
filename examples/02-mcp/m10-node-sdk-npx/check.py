"""M10 check: 공식 TypeScript SDK로 만든 Node 서버(npx 배포 형태 포함)를 확인한다.

- node가 없거나, node_modules가 없는데 npm 레지스트리에 3초 안에 닿지 못하면 WARN만 남기고 SDK가 필요한 검사를 건너뛴다.
- node_modules가 없고 레지스트리에 닿으면 이 예제 폴더 안에서 `npm install`을 실행한다 (node_modules/는 .gitignore 대상).
- 배포 형태(npm pack -> npx ./x.tgz) 검사는 임시 폴더에서, 임시 npm 캐시로 한다. 예제 폴더에는 .tgz를 만들지 않는다.
"""
import json
import os
import shutil
import subprocess
import sys
import pathlib
import tempfile
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402

NODE = shutil.which("node")
NPM = shutil.which("npm")
SERVER = HERE / "src" / "server.mjs"


def registry_reachable(timeout=3.0):
    """사용자가 설정한 npm 레지스트리(npm config get registry)에 3초 안에 HTTP 응답이 오는지. 반환: (가능 여부, 주소)."""
    try:
        url = subprocess.run([NPM, "config", "get", "registry"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False, "(npm config 실패)"
    if not url.startswith("http"):
        return False, url
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout).close()
        return True, url
    except urllib.error.HTTPError:
        return True, url  # 응답이 왔다 (401/404여도 서버는 살아 있다)
    except Exception:
        return False, url


def scripted_call(sb, cwd, tool, args):
    """가짜 모델이 `tool`을 `args`로 부르게 한다. 반환: (opencode 출력, 모델에게 제공된 도구 이름들, 모델에게 돌아간 도구 결과들)."""
    with FakeLLM(script=[("tool", tool, args), "DONE"]) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
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


def tool_seen(transcript, name):
    return any(name in line for line in transcript.splitlines() if line.lstrip().startswith(("⚙", "✗", "→")))


class StdioClient:
    """서버를 띄워 JSON 줄을 주고받는 최소 클라이언트 (바이트 단위)."""

    def __init__(self, cmd, cwd):
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(cwd))
        self.raw_lines = []

    def send(self, obj):
        self.proc.stdin.write(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
        self.proc.stdin.flush()

    def rpc(self, msg_id, method, params=None):
        self.send({"jsonrpc": "2.0", "id": msg_id, "method": method, **({"params": params} if params is not None else {})})
        while True:  # 요청 id와 같은 응답이 올 때까지 읽는다 (SDK는 알림을 섞어 보낼 수 있다)
            line = self.proc.stdout.readline().decode("utf-8")
            if not line:
                raise RuntimeError("서버가 응답 없이 끝났다: " + self.proc.stderr.read().decode("utf-8", "replace")[-300:])
            self.raw_lines.append(line)
            msg = json.loads(line)
            if msg.get("id") == msg_id:
                return msg

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


def first_response_seconds(cmd, cwd, env=None):
    """서버를 띄워 initialize 응답이 올 때까지의 시간(초). 못 받으면 None."""
    started = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(cwd), env=env)
    try:
        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}}}
        proc.stdin.write(json.dumps(msg).encode() + b"\n")
        proc.stdin.flush()
        line = proc.stdout.readline().decode("utf-8", "replace")
        ok = '"protocolVersion"' in line
        return (time.time() - started) if ok else None
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        proc.stderr.close()
        proc.stdout.close()


# --- 파일 (node 없이 확인) -----------------------------------------------------------------
pkg = json.loads((HERE / "package.json").read_text(encoding="utf-8"))
config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
glossary = json.loads((HERE / "glossary.json").read_text(encoding="utf-8"))["terms"]
check("package.json: name, version 1.0.0, type module, bin", pkg["name"] == "team-glossary-mcp" and pkg["version"] == "1.0.0"
      and pkg["type"] == "module" and pkg["bin"] == {"team-glossary-mcp": "src/server.mjs"}, str(pkg))
check("package.json: SDK를 정확한 버전(1.32.2)으로 고정한다 (^, ~ 없음)", pkg["dependencies"].get("@modelcontextprotocol/sdk") == "1.32.2", str(pkg["dependencies"]))
check("package.json: files에 glossary.json과 src가 있다 (배포 파일에 데이터 포함)", set(pkg["files"]) == {"src", "glossary.json"})
check("src/server.mjs 첫 줄이 shebang이다", SERVER.read_text(encoding="utf-8").startswith("#!/usr/bin/env node"))
check("opencode.json: 기본 항목은 ['node','src/server.mjs'] enabled, npx 항목은 enabled:false + timeout 60000",
      config["mcp"]["glossary-node"]["command"] == ["node", "src/server.mjs"] and config["mcp"]["glossary-node"].get("enabled") is True
      and config["mcp"]["glossary-npx"]["command"][:2] == ["npx", "-y"] and config["mcp"]["glossary-npx"]["enabled"] is False
      and config["mcp"]["glossary-npx"]["timeout"] == 60000 and "model" not in config)
ignored = (HERE / ".gitignore").read_text(encoding="utf-8").split()
check("이 예제의 .gitignore가 node_modules/와 *.tgz를 거른다", "node_modules/" in ignored and "*.tgz" in ignored)

if not NODE or not NPM:
    check("WARN: node/npm이 없어 M10의 서버 검사를 건너뜁니다 (Node.js 18+ 설치 필요)", False, soft=True)
    finish()

# --- 의존성 설치 (미러/레지스트리가 필요한 단계) ------------------------------------------------
reachable, registry = registry_reachable()
print(f"[info] node {subprocess.run([NODE, '-v'], capture_output=True, text=True).stdout.strip()}, npm 레지스트리 {registry} -> {'3초 안에 응답' if reachable else '응답 없음'}")
if not (HERE / "node_modules" / "@modelcontextprotocol" / "sdk").is_dir():
    if not reachable:
        check("WARN: node_modules가 없고 레지스트리에 닿지 않아 SDK 서버 검사를 건너뜁니다 "
              "(패키지 미러가 필요합니다: `npm config set registry <미러 주소>` 후 `npm install`)", False, soft=True)
        finish()
    started = time.time()
    proc = subprocess.run([NPM, "install", "--no-audit", "--no-fund"], cwd=str(HERE), capture_output=True, text=True, timeout=300)
    check(f"npm install 성공 ({time.time() - started:.1f}초)", proc.returncode == 0, proc.stdout[-300:] + proc.stderr[-300:])
    if proc.returncode != 0:
        finish()

# --- 직접 만든 JSON-RPC 세션 ---------------------------------------------------------------------
c = StdioClient([NODE, str(SERVER)], HERE)
r = c.rpc(1, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}})
check("initialize: protocolVersion 2025-11-25, tools 기능, serverInfo.name=team-glossary-mcp",
      r["result"]["protocolVersion"] == "2025-11-25" and "tools" in r["result"]["capabilities"]
      and r["result"]["serverInfo"]["name"] == "team-glossary-mcp", str(r))
c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
r = c.rpc(2, "tools/list")
tools = {t["name"]: t for t in r["result"]["tools"]}
check("tools/list: lookup_term, list_terms", set(tools) == {"lookup_term", "list_terms"}, str(list(tools)))
schema = tools["lookup_term"]["inputSchema"]
check("zod 스키마에서 inputSchema가 만들어진다 (term: string, required)", schema["properties"]["term"]["type"] == "string" and schema["required"] == ["term"], str(schema))
adr = next(t for t in glossary if t["term"] == "ADR")
r = c.rpc(3, "tools/call", {"name": "lookup_term", "arguments": {"term": "아키텍처 결정 기록"}})
text = r["result"]["content"][0]["text"]
check("tools/call 성공: 한글 별칭으로 찾아 M1과 같은 정의를 돌려준다", adr["definition"] in text and not r["result"].get("isError"), str(r))
r = c.rpc(4, "tools/call", {"name": "lookup_term", "arguments": {"term": "카나리아 배포"}})
check("tools/call 없는 용어: JSON-RPC 오류가 아니라 isError:true 결과 (비슷한 용어 안내 포함)",
      r.get("result", {}).get("isError") is True and "error" not in r and "카나리 배포" in r["result"]["content"][0]["text"], str(r))
r = c.rpc(5, "tools/call", {"name": "lookup_term", "arguments": {}})
check("필수 인자 누락: SDK가 검증해 isError 결과로 답한다 (M1은 -32602 오류, 서버가 죽지 않음)", r.get("result", {}).get("isError") is True, str(r))
r = c.rpc(6, "resources/list")
check("지원하지 않는 method는 -32601", r.get("error", {}).get("code") == -32601, str(r))
rc, stderr = c.close()
check("stdout의 모든 줄이 JSON이다 (로그는 stderr로만)", all(json.loads(line) for line in c.raw_lines if line.strip()))
check("stdin을 닫으면 서버가 정상 종료(0)하고 로그는 stderr에 있다", rc == 0 and "[team-glossary]" in stderr, f"rc={rc} {stderr[-200:]}")
t_node = first_response_seconds([NODE, str(SERVER)], HERE)
check(f"node src/server.mjs: initialize 응답까지 {t_node and round(t_node, 2)}초 (opencode 시작 제한 30초 이내)", t_node is not None and t_node < 30)

# --- opencode (기본 항목: node src/server.mjs) -----------------------------------------------------
with Sandbox("m10") as sb:
    status = sb.mcp_list(HERE)
    check("opencode mcp list: glossary-node connected, glossary-npx disabled",
          status.get("glossary-node") == "connected" and status.get("glossary-npx") == "disabled", str(status))
    out, names, results = scripted_call(sb, HERE, "glossary-node_lookup_term", {"term": "롤백"})
    check("(가짜 모델) glossary-node_lookup_term / glossary-node_list_terms 가 제공되고 한글 결과가 모델에게 돌아온다",
          {"glossary-node_lookup_term", "glossary-node_list_terms"} <= set(names) and any("직전의 정상 버전" in x for x in results), f"{names} {results} {out[-300:]}")
    check("(가짜 모델) 'glossary-npx_*' 는 enabled:false 라서 도구가 없다", not any(n.startswith("glossary-npx_") for n in names))
    out, names, results = scripted_call(sb, HERE, "glossary-node_lookup_term", {"term": "카나리아 배포"})
    check("(가짜 모델) isError 결과도 모델에게 돌아가고 화면에는 실패(✗)로 표시된다",
          any("비슷한 용어: 카나리 배포" in x for x in results) and "✗ glossary-node_lookup_term" in out, f"{results} {out[-300:]}")

    # --- 배포 형태: npm pack -> npx -y ./team-glossary-mcp-1.0.0.tgz (레지스트리 필요) ---------------------
    if not reachable:
        check("WARN: 레지스트리에 닿지 않아 npx 배포 형태 검사를 건너뜁니다 (npx는 처음 실행할 때 의존성을 내려받는다: 패키지 미러 필요)", False, soft=True)
    else:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="m10-check-"))
        try:
            project = tmp / "project"
            (project / "src").mkdir(parents=True)
            for name in ("package.json", "glossary.json", "opencode.json", "fake_llm.py"):
                shutil.copy(HERE / name, project / name)
            shutil.copy(SERVER, project / "src" / "server.mjs")
            cache = tmp / "npm-cache"  # 일부러 빈 npm 캐시: 처음 실행 비용을 잰다
            env = dict(os.environ, npm_config_cache=str(cache))
            pack = subprocess.run([NPM, "pack", "--quiet"], cwd=str(project), capture_output=True, text=True, env=env, timeout=120)
            tgz = project / "team-glossary-mcp-1.0.0.tgz"
            check("npm pack: team-glossary-mcp-1.0.0.tgz 가 만들어진다 (glossary.json 포함)", pack.returncode == 0 and tgz.exists(), pack.stdout + pack.stderr)
            if tgz.exists():
                import tarfile
                with tarfile.open(tgz) as tar:
                    members = sorted(tar.getnames())
                check("tgz 내용: package.json, glossary.json, src/server.mjs 만 들어 있다 (node_modules·.gitignore 대상 제외)",
                      members == ["package/glossary.json", "package/package.json", "package/src/server.mjs"], str(members))
                npx_cmd = [shutil.which("npx") or "npx", "-y", "./team-glossary-mcp-1.0.0.tgz"]
                t1 = first_response_seconds(npx_cmd, project, env)
                t2 = first_response_seconds(npx_cmd, project, env)
                print(f"[info] npx -y ./...tgz 시작 시간: 첫 실행(빈 캐시, 의존성 설치) {t1 and round(t1, 2)}초, 두 번째 {t2 and round(t2, 2)}초, node 직접 {t_node and round(t_node, 2)}초")
                check("npx -y ./team-glossary-mcp-1.0.0.tgz: 첫 실행에도 서버가 응답한다 (의존성 자동 설치)", t1 is not None)
                check("npx 두 번째 실행은 캐시 덕에 첫 실행보다 빠르다", t1 is not None and t2 is not None and t2 < t1, f"{t1} {t2}")
                check("첫 실행도 opencode 시작 제한(30초) 안에 끝난다 — 느린 미러면 달라질 수 있다", t1 is not None and t1 < 30)
                # 같은 설정에서 glossary-npx 만 켜서 opencode가 연결하는지 본다
                overlay = json.loads((project / "opencode.json").read_text(encoding="utf-8"))
                overlay["mcp"]["glossary-npx"]["enabled"] = True
                overlay["mcp"]["glossary-node"]["enabled"] = False
                (project / "opencode.json").write_text(json.dumps(overlay), encoding="utf-8")
                status = sb.mcp_list(project, extra_env={"npm_config_cache": str(cache)})
                check("opencode mcp list: npx 항목(glossary-npx)을 켜면 connected", status.get("glossary-npx") == "connected", str(status))
                with FakeLLM(script=[("tool", "glossary-npx_lookup_term", {"term": "SLO"}), "DONE"]) as llm:
                    env2 = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "npm_config_cache": str(cache)}
                    sb.opencode(["run", "-m", "fake/echo", "--auto", "go"], project, timeout=120, extra_env=env2)
                    got = [llm.message_text(m) for rq in llm.main_requests() for m in rq["messages"] if m.get("role") == "tool"]
                check("(가짜 모델) npx로 띄운 서버에서도 용어집 답이 돌아온다", any("내부 목표 수치" in x for x in got), str(got))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if model_enabled():
        out = sb.run_model("팀 용어집에서 롤백이 무슨 뜻인지 찾아서 알려줘.", HERE, extra_env={"PWD": str(HERE)})
        model_check("모델이 glossary-node_lookup_term 도구를 호출했다", out, tool_seen(out, "glossary-node_lookup_term"))
        model_check("한글 결과가 답변에 반영됐다", out, any(w in out for w in ("직전의 정상 버전", "되돌리", "정상 버전")))
        print(out[-600:])
finish()
