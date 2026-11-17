"""M12 check: server.py 를 설치 가능한 패키지로 만든 모양(python -m 경로, uvx 경로)을 확인한다.

- `python -m team_glossary_mcp` + PYTHONPATH=src 경로는 설치도 인터넷도 필요 없어서 항상 검사한다.
- uvx 경로는 uv 가 있고 패키지 인덱스(PyPI/미러)에 3초 안에 닿을 때만 검사한다. 아니면 WARN 으로 건너뛴다.
  (uv 가 패키지를 처음 빌드할 때 빌드 백엔드 hatchling 을 인덱스에서 내려받기 때문이다.)
- uvx 검사는 임시 폴더 + 임시 uv 캐시에서만 한다. 예제 폴더에는 dist/ 나 .venv 를 만들지 않는다.
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
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402

UV = shutil.which("uv")
UVX = shutil.which("uvx")


def http_ok(url, timeout=3.0):
    try:
        urllib.request.urlopen(urllib.request.Request(url), timeout=timeout).close()
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def index_reachable():
    if not (UV and UVX):
        return False, "(uv/uvx 없음)"
    url = os.environ.get("UV_DEFAULT_INDEX") or os.environ.get("UV_INDEX_URL") or os.environ.get("PIP_INDEX_URL") or "https://pypi.org/simple/"
    return http_ok(url), url


def clean_env(**extra):
    """PYTHONUTF8/PYTHONIOENCODING 을 제거해 Windows 기본 인코딩(cp949) 상태에서도 서버가 동작하는지 본다."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env.update(extra)
    return env


def scripted_call(sb, cwd, tool, args, extra_env=None):
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


def tool_seen(transcript, name):
    return any(name in line for line in transcript.splitlines() if line.lstrip().startswith(("⚙", "✗", "→")))


class StdioClient:
    def __init__(self, cmd, cwd, env=None):
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(cwd), env=env or clean_env())
        self.raw_lines = []

    def send(self, obj):
        self.proc.stdin.write(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
        self.proc.stdin.flush()

    def recv(self):
        line = self.proc.stdout.readline().decode("utf-8")
        if not line:
            raise RuntimeError("서버가 응답 없이 끝났다: " + self.proc.stderr.read().decode("utf-8", "replace")[-300:])
        self.raw_lines.append(line)
        return json.loads(line)

    def rpc(self, msg_id, method, params=None):
        self.send({"jsonrpc": "2.0", "id": msg_id, "method": method, **({"params": params} if params is not None else {})})
        return self.recv()

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        err = self.proc.stderr.read().decode("utf-8", "replace")
        self.proc.stderr.close()
        self.proc.stdout.close()
        return self.proc.returncode, err


def first_response_seconds(cmd, cwd, env=None):
    started = time.time()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(cwd), env=env)
    try:
        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}}}
        proc.stdin.write(json.dumps(msg).encode() + b"\n")
        proc.stdin.flush()
        line = proc.stdout.readline().decode("utf-8", "replace")
        return (time.time() - started) if '"protocolVersion"' in line else None
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
        proc.stderr.close()
        proc.stdout.close()


def run_once(cmd, cwd, env, stdin=b""):
    return subprocess.run(cmd, cwd=str(cwd), env=env, input=stdin, capture_output=True, timeout=180)


# --- 파일 ---------------------------------------------------------------------------------------
pyproject = (HERE / "pyproject.toml").read_text(encoding="utf-8")
config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
pkg = HERE / "src" / "team_glossary_mcp"
check("패키지 파일: src/team_glossary_mcp/{__init__,__main__,server}.py + glossary.json",
      all((pkg / n).is_file() for n in ("__init__.py", "__main__.py", "server.py", "glossary.json")))
check("pyproject.toml: 콘솔 스크립트 team-glossary-mcp = team_glossary_mcp.server:main, 의존성 없음",
      'team-glossary-mcp = "team_glossary_mcp.server:main"' in pyproject and "dependencies = []" in pyproject)
check("pyproject.toml: 버전은 __init__.py 의 __version__ 한 곳에서 읽는다 (dynamic)",
      'dynamic = ["version"]' in pyproject and 'path = "src/team_glossary_mcp/__init__.py"' in pyproject
      and '__version__ = "1.0.0"' in (pkg / "__init__.py").read_text(encoding="utf-8"))
check("server.py: 데이터 파일을 importlib.resources 로 읽는다 (__file__ 경로 계산 없음)",
      "resources.files" in (pkg / "server.py").read_text(encoding="utf-8") and "__file__" not in (pkg / "server.py").read_text(encoding="utf-8").replace("`__file__`", ""))
glossary = json.loads((pkg / "glossary.json").read_text(encoding="utf-8"))["terms"]
m1 = HERE.parent / "m1-stdio-minimal" / "glossary.json"
check("glossary.json 은 M1과 같은 용어집이다", not m1.exists() or json.loads(m1.read_text(encoding="utf-8"))["terms"] == glossary)
check("opencode.json: 기본 항목 ['python','-m','team_glossary_mcp'] + environment PYTHONPATH=src, uvx 항목은 enabled:false",
      config["mcp"]["glossary-pkg"]["command"] == ["python", "-m", "team_glossary_mcp"]
      and config["mcp"]["glossary-pkg"]["environment"] == {"PYTHONPATH": "src"} and config["mcp"]["glossary-pkg"].get("enabled") is True
      and config["mcp"]["glossary-uvx"]["command"] == ["uvx", "--from", ".", "team-glossary-mcp"]
      and config["mcp"]["glossary-uvx"]["enabled"] is False and "model" not in config)
ignored = (HERE / ".gitignore").read_text(encoding="utf-8").split()
check("이 예제의 .gitignore 가 dist/, build/, *.egg-info/, .venv/ 를 거른다", {"dist/", "build/", "*.egg-info/", ".venv/"} <= set(ignored))

# --- python -m 경로: 설치 없이, 인터넷 없이 -------------------------------------------------------------
env_src = clean_env(PYTHONPATH="src")
imp = subprocess.run([sys.executable, "-c", "import team_glossary_mcp.server as s; print(len(s.TERMS))"], cwd=str(HERE), env=env_src, capture_output=True, timeout=30)
check("import 만 해도 부작용이 없다 (stdout 에는 용어 개수만, stdin 을 읽지 않는다) — 14", imp.stdout.decode().strip() == "14", imp.stdout.decode() + imp.stderr.decode()[-200:])
noenv = subprocess.run([sys.executable, "-m", "team_glossary_mcp"], cwd=str(HERE), env=clean_env(PYTHONPATH=""), input=b"", capture_output=True, timeout=30)
check("PYTHONPATH 없이는 'No module named team_glossary_mcp' 로 실패한다 (그래서 opencode.json 에 environment 가 필요)",
      noenv.returncode != 0 and b"No module named" in noenv.stderr, noenv.stderr.decode()[-200:])

c = StdioClient([sys.executable, "-m", "team_glossary_mcp"], HERE, env_src)
r = c.rpc(1, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}})
check("initialize: serverInfo 가 team-glossary-mcp / __version__ (1.0.0)",
      r["result"]["serverInfo"] == {"name": "team-glossary-mcp", "version": "1.0.0"} and r["result"]["protocolVersion"] == "2025-11-25", str(r))
c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
r = c.rpc(2, "tools/list")
check("tools/list: lookup_term, list_terms", [t["name"] for t in r["result"]["tools"]] == ["lookup_term", "list_terms"], str(r))
adr = next(t for t in glossary if t["term"] == "ADR")
r = c.rpc(3, "tools/call", {"name": "lookup_term", "arguments": {"term": "아키텍처 결정 기록"}})
check("tools/call 성공: 패키지에 든 glossary.json 에서 한글 정의를 찾는다 (UTF-8 모드 없이)", adr["definition"] in r["result"]["content"][0]["text"] and r["result"]["isError"] is False, str(r))
r = c.rpc(4, "tools/call", {"name": "lookup_term", "arguments": {"term": "카나리아 배포"}})
check("tools/call 없는 용어: isError:true 결과 (JSON-RPC 오류 아님)", r["result"]["isError"] is True and "error" not in r and "카나리 배포" in r["result"]["content"][0]["text"], str(r))
r = c.rpc(5, "tools/call", {"name": "no_such_tool", "arguments": {}})
check("tools/call 모르는 도구: -32602 (M1과 같은 동작)", r.get("error", {}).get("code") == -32602, str(r))
rc, stderr = c.close()
check("stdout 의 모든 줄이 JSON 이고 stdin 을 닫으면 정상 종료(0), 로그는 stderr", all(json.loads(l) for l in c.raw_lines if l.strip()) and rc == 0 and "[team-glossary]" in stderr, f"rc={rc} {stderr[-200:]}")
t_py = first_response_seconds([sys.executable, "-m", "team_glossary_mcp"], HERE, env_src)
print(f"[info] python -m team_glossary_mcp 시작 시간: {t_py and round(t_py, 2)}초 (설치·인터넷 불필요)")

# --- opencode: 기본 경로 -------------------------------------------------------------------------------
reachable, index = index_reachable()
print(f"[info] uv {subprocess.run([UV, '--version'], capture_output=True, text=True).stdout.strip() if UV else '없음'}, 패키지 인덱스 {index} -> {'3초 안에 응답' if reachable else '응답 없음/도구 없음'}")
with Sandbox("m12") as sb:
    status = sb.mcp_list(HERE, extra_env={"PYTHONUTF8": "0"})
    check("opencode mcp list: glossary-pkg connected (environment 로 넘긴 상대 경로 PYTHONPATH=src 가 프로젝트 폴더 기준으로 풀린다), glossary-uvx disabled",
          status.get("glossary-pkg") == "connected" and status.get("glossary-uvx") == "disabled", str(status))
    out, names, results = scripted_call(sb, HERE, "glossary-pkg_lookup_term", {"term": "롤백"})
    check("(가짜 모델) glossary-pkg_lookup_term / glossary-pkg_list_terms 가 제공되고 한글 결과가 모델에게 돌아온다",
          {"glossary-pkg_lookup_term", "glossary-pkg_list_terms"} <= set(names) and any("직전의 정상 버전" in x for x in results), f"{names} {results} {out[-300:]}")
    check("(가짜 모델) enabled:false 인 glossary-uvx_* 도구는 없다", not any(n.startswith("glossary-uvx_") for n in names))
    out, names, results = scripted_call(sb, HERE, "glossary-pkg_lookup_term", {"term": "카나리아 배포"})
    check("(가짜 모델) isError 결과도 모델에게 돌아가고 화면에는 실패(✗)로 표시된다", any("비슷한 용어: 카나리 배포" in x for x in results) and "✗ glossary-pkg_lookup_term" in out, f"{results} {out[-300:]}")

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="m12-noenv-"))
    try:
        shutil.copytree(pkg, tmp / "src" / "team_glossary_mcp", ignore=shutil.ignore_patterns("__pycache__"))
        cfg = json.loads(json.dumps(config))
        del cfg["mcp"]["glossary-pkg"]["environment"]
        (tmp / "opencode.json").write_text(json.dumps(cfg), encoding="utf-8")
        status = sb.mcp_list(tmp)
        check("(대조) environment 를 빼면 같은 명령이 failed 가 된다 — opencode 가 environment 를 서버 프로세스에 실제로 전달한다는 증거", status.get("glossary-pkg") == "failed", str(status))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # --- uvx 경로 (uv + 패키지 인덱스 필요) ----------------------------------------------------------------
    if not reachable:
        check("WARN: uv 가 없거나 패키지 인덱스(PyPI/미러)에 닿지 않아 uvx 검사를 건너뜁니다 "
              "(처음 빌드할 때 빌드 백엔드 hatchling 을 인덱스에서 받으므로 미러가 필요합니다: UV_DEFAULT_INDEX 또는 uv.toml)", False, soft=True)
    else:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="m12-uvx-"))
        try:
            project = tmp / "project"
            shutil.copytree(HERE, project, ignore=shutil.ignore_patterns("__pycache__", "dist", ".venv", "*.egg-info", "build"))
            env = clean_env(UV_CACHE_DIR=str(tmp / "uv-cache"))  # 빈 캐시: 처음 실행 비용을 잰다
            cmd = [UVX, "--from", ".", "team-glossary-mcp"]
            t1 = first_response_seconds(cmd, project, env)
            t2 = first_response_seconds(cmd, project, env)
            print(f"[info] uvx --from . team-glossary-mcp 시작 시간: 첫 실행(빈 캐시, 빌드+백엔드 내려받기) {t1 and round(t1, 2)}초, 두 번째 {t2 and round(t2, 2)}초, python -m {t_py and round(t_py, 2)}초")
            check("uvx --from . team-glossary-mcp: 첫 실행에서 패키지를 빌드해 서버가 응답한다", t1 is not None)
            check("uvx 두 번째 실행은 캐시 덕에 첫 실행보다 빠르다", t1 is not None and t2 is not None and t2 < t1, f"{t1} {t2}")
            check("첫 실행도 opencode 시작 제한(30초) 안에 끝난다 — 느린 미러면 달라질 수 있다", t1 is not None and t1 < 30)

            # 같은 설정에서 uvx 항목만 켜서 opencode 가 연결하는지
            cfg = json.loads((project / "opencode.json").read_text(encoding="utf-8"))
            cfg["mcp"]["glossary-uvx"]["enabled"] = True
            cfg["mcp"]["glossary-pkg"]["enabled"] = False
            (project / "opencode.json").write_text(json.dumps(cfg), encoding="utf-8")
            status = sb.mcp_list(project, extra_env={"UV_CACHE_DIR": str(tmp / "uv-cache")})
            check("opencode mcp list: uvx 항목(glossary-uvx)을 켜면 connected", status.get("glossary-uvx") == "connected", str(status))
            out, names, results = scripted_call(sb, project, "glossary-uvx_lookup_term", {"term": "SLO"}, {"UV_CACHE_DIR": str(tmp / "uv-cache")})
            check("(가짜 모델) uvx 로 띄운 서버에서도 용어집 답이 돌아온다", any("내부 목표 수치" in x for x in results), f"{results} {out[-300:]}")

            # 빌드한 wheel 은 인덱스 없이 실행된다 (빌드 백엔드가 필요한 것은 '빌드'뿐)
            dist = tmp / "dist"
            built = run_once([UV, "build", "--wheel", "-o", str(dist), "."], project, env)
            wheels = sorted(dist.glob("*.whl"))
            check("uv build --wheel: team_glossary_mcp-1.0.0-py3-none-any.whl 이 만들어진다", built.returncode == 0 and len(wheels) == 1 and wheels[0].name == "team_glossary_mcp-1.0.0-py3-none-any.whl", built.stderr.decode()[-300:])
            if wheels:
                names_in = zipfile.ZipFile(wheels[0]).namelist()
                check("wheel 안에 glossary.json 이 들어 있다 (패키지 데이터)", "team_glossary_mcp/glossary.json" in names_in and "team_glossary_mcp/__main__.py" in names_in, str(names_in))
                fresh = clean_env(UV_CACHE_DIR=str(tmp / "uv-cache-2"))
                t3 = first_response_seconds([UVX, "--offline", "--from", str(wheels[0]), "team-glossary-mcp"], tmp, fresh)
                check(f"wheel 파일로 실행: 빈 캐시 + --offline 이어도 서버가 응답한다 ({t3 and round(t3, 2)}초) — 공유 폴더에 wheel 을 두는 배포가 가능한 이유", t3 is not None)
                t4 = first_response_seconds([UVX, "--no-index", "--find-links", str(dist), "--from", "team-glossary-mcp==1.0.0", "team-glossary-mcp"], tmp, clean_env(UV_CACHE_DIR=str(tmp / "uv-cache-3")))
                check(f"폴더를 인덱스처럼 쓰기: uvx --no-index --find-links <폴더> --from team-glossary-mcp==1.0.0 이 동작한다 ({t4 and round(t4, 2)}초)", t4 is not None)

            # 함정: 소스만 고치면 uvx --from . 는 낡은 빌드를 쓴다 (uv 버전에 따라 달라질 수 있어 soft)
            server_py = project / "src" / "team_glossary_mcp" / "server.py"
            server_py.write_text(server_py.read_text(encoding="utf-8").replace("stdin 대기 중", "stdin 대기 중 (고침)"), encoding="utf-8")
            stale = run_once(cmd, project, env).stderr.decode("utf-8", "replace")
            check("(함정) server.py 만 고치고 uvx --from . 를 다시 실행하면 고친 내용이 반영되지 않는다 (캐시된 빌드 사용)", "(고침)" not in stale, stale[-200:], soft=True)
            nocache = run_once([UVX, "--no-cache", "--from", ".", "team-glossary-mcp"], project, env).stderr.decode("utf-8", "replace")
            check("--no-cache 를 붙이면 다시 빌드해 반영된다 (--refresh-package, --reinstall-package 는 이 경우 효과 없었다)", "(고침)" in nocache, nocache[-200:], soft=True)
            server_py.write_text(server_py.read_text(encoding="utf-8").replace("(고침)", "(또 고침)"), encoding="utf-8")
            os.utime(project / "pyproject.toml")  # pyproject.toml 의 수정 시각이 바뀌면 uv 가 다시 빌드한다
            touched = run_once(cmd, project, env).stderr.decode("utf-8", "replace")
            check("pyproject.toml 을 건드리면(수정 시각 변경) 캐시된 빌드가 갱신된다", "(또 고침)" in touched, touched[-200:], soft=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if model_enabled():
        out = sb.run_model("팀 용어집에서 롤백이 무슨 뜻인지 찾아서 알려줘.", HERE, extra_env={"PWD": str(HERE), "PYTHONUTF8": "0"})
        model_check("모델이 glossary-pkg_lookup_term 도구를 호출했다", out, tool_seen(out, "glossary-pkg_lookup_term"))
        model_check("한글 결과가 답변에 반영됐다", out, any(w in out for w in ("직전의 정상 버전", "되돌리", "정상 버전")))
        print(out[-600:])
finish()
