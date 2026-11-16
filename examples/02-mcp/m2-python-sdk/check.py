"""M2 check: 공식 Python SDK(mcp)로 만든 서버가 M1과 같은 용어집을 제공하는지 확인한다.

pip 설치가 불가능한 환경(패키지 미러 없음, 오프라인)이면 WARN만 남기고 SDK가 필요한 검사는 건너뛴다.
검사용 가상환경은 임시 폴더에 만들고 끝나면 지운다 (예제 폴더의 .venv는 건드리지 않는다).
"""
import json
import os
import shutil
import subprocess
import sys
import pathlib
import tempfile

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


def clean_env(**extra):
    """자식 프로세스용 환경: PYTHONUTF8/PYTHONIOENCODING을 제거해 Windows 기본 인코딩(cp949) 상태에서도 서버가 동작하는지 확인한다."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env.update(extra)
    return env


def tool_seen(transcript, name):
    """성공(⚙)뿐 아니라 실패(✗, isError 결과)한 호출도 포함해 도구 이름이 transcript에 나오는지 본다."""
    return any(name in line for line in transcript.splitlines() if line.lstrip().startswith(("⚙", "✗", "→")))

# --- SDK 없이 확인할 수 있는 것 -------------------------------------------------------------------------
req = (HERE / "requirements.txt").read_text(encoding="utf-8")
check("requirements.txt가 mcp 버전을 고정한다 (mcp==x.y.z)", any(l.startswith("mcp==") for l in req.splitlines()))
win = json.loads((HERE / "opencode.windows.json").read_text(encoding="utf-8"))
lin = json.loads((HERE / "opencode.linux.json").read_text(encoding="utf-8"))
check("템플릿: Windows는 .venv/Scripts/python.exe, Linux는 .venv/bin/python",
      win["mcp"]["glossary-sdk"]["command"] == [".venv/Scripts/python.exe", "server.py"]
      and lin["mcp"]["glossary-sdk"]["command"] == [".venv/bin/python", "server.py"]
      and "model" not in win and "model" not in lin)
ignored = (HERE / ".gitignore").read_text(encoding="utf-8").split()
check("생성되는 opencode.json과 .venv는 이 예제의 .gitignore에 있다", "opencode.json" in ignored and ".venv/" in ignored)
glossary = json.loads((HERE / "glossary.json").read_text(encoding="utf-8"))["terms"]
check("glossary.json은 M1과 같은 용어집이다 (14개)", len(glossary) == 14)


def count_code_lines(path):
    """주석·빈 줄·docstring을 뺀 실제 코드 줄 수 (대략)."""
    import ast
    source = pathlib.Path(path).read_text(encoding="utf-8")
    doc_lines = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body and isinstance(node.body[0], ast.Expr) \
                and isinstance(getattr(node.body[0], "value", None), ast.Constant) and isinstance(node.body[0].value.value, str):
            doc_lines.update(range(node.body[0].lineno, node.body[0].end_lineno + 1))
    return sum(1 for i, line in enumerate(source.splitlines(), start=1)
               if line.strip() and not line.strip().startswith("#") and i not in doc_lines)


m1_server = HERE.parent / "m1-stdio-minimal" / "server.py"
if m1_server.exists():
    print(f"[info] 코드 줄 수(주석·빈 줄·docstring 제외): M1 server.py={count_code_lines(m1_server)}, M2 server.py={count_code_lines(HERE / 'server.py')}")

# --- venv + pip install ---------------------------------------------------------------------------------
# 예제 폴더의 .venv를 건드리지 않도록, 배포되는 파일만 임시 프로젝트로 복사해서 prepare.py를 "기본 옵션 그대로" 실행한다.
# (그래야 사용자가 받게 될 opencode.json - 상대 경로 .venv/bin/python 또는 .venv/Scripts/python.exe - 을 그대로 시험할 수 있다)
tmp = pathlib.Path(tempfile.mkdtemp(prefix="m2-check-"))
try:
    project = tmp / "project"
    project.mkdir()
    for name in ("server.py", "glossary.json", "prepare.py", "requirements.txt", "opencode.windows.json", "opencode.linux.json"):
        shutil.copy(HERE / name, project / name)
    try:
        proc = subprocess.run([sys.executable, str(project / "prepare.py")], cwd=str(project), capture_output=True, timeout=600)
        installed = proc.returncode == 0
        detail = (proc.stdout + proc.stderr).decode("utf-8", "replace")[-500:]
    except subprocess.TimeoutExpired:
        installed, detail = False, "pip 설치 시간 초과"
    if not installed:
        check("WARN: pip로 mcp SDK를 설치할 수 없어 M2의 SDK 검사를 건너뜁니다 (패키지 미러/네트워크 확인: README 참고)", False, detail, soft=True)
        finish()

    check("prepare.py: 가상환경 + SDK 설치 + opencode.json 생성", (project / "opencode.json").exists() and (project / ".venv").is_dir())
    cfg = json.loads((project / "opencode.json").read_text(encoding="utf-8"))
    command = cfg["mcp"]["glossary-sdk"]["command"]
    expected = [".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python", "server.py"]
    check("생성된 opencode.json은 이 OS용 템플릿 그대로다 (상대 경로의 venv 파이썬)", command == expected and (project / command[0]).exists(), str(command))
    again = subprocess.run([sys.executable, str(project / "prepare.py")], cwd=str(project), capture_output=True, timeout=600)
    check("prepare.py는 다시 실행해도 성공한다 (idempotent)", again.returncode == 0)

    # --- 핸드셰이크 ---------------------------------------------------------------------------------------
    py = str(project / command[0])
    proc = subprocess.Popen([py, str(project / "server.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=str(project), env=clean_env())

    def rpc(i, method, params=None):
        msg = {"jsonrpc": "2.0", "id": i, "method": method, **({"params": params} if params is not None else {})}
        proc.stdin.write(json.dumps(msg, ensure_ascii=False).encode("utf-8") + b"\n")
        proc.stdin.flush()
        line = proc.stdout.readline().decode("utf-8")
        return json.loads(line)

    r = rpc(1, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}})
    check("initialize: protocolVersion 2025-11-25를 협상한다", r["result"]["protocolVersion"] == "2025-11-25", str(r))
    proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
    proc.stdin.flush()
    r = rpc(2, "tools/list")
    tools = {t["name"]: t for t in r["result"]["tools"]}
    check("tools/list: lookup_term, list_terms (함수 이름 -> 도구 이름)", set(tools) == {"lookup_term", "list_terms"}, str(list(tools)))
    schema = tools["lookup_term"]["inputSchema"]
    check("타입 힌트에서 inputSchema가 만들어진다 (term: string, required)", schema["properties"]["term"]["type"] == "string" and schema["required"] == ["term"], str(schema))
    check("docstring이 description이 된다", "팀 용어집" in tools["lookup_term"]["description"])
    adr = next(t for t in glossary if t["term"] == "ADR")
    r = rpc(3, "tools/call", {"name": "lookup_term", "arguments": {"term": "아키텍처 결정 기록"}})
    check("tools/call: 한글 인자(별칭)로 M1과 같은 한글 정의를 돌려준다 (UTF-8 모드 없이도)", adr["definition"] in r["result"]["content"][0]["text"] and r["result"]["isError"] is False, str(r))
    r = rpc(4, "tools/call", {"name": "lookup_term", "arguments": {"term": "없는용어"}})
    check("없는 용어: ToolError -> isError:true", r["result"]["isError"] is True and "용어집에 없습니다" in r["result"]["content"][0]["text"], str(r))
    r = rpc(5, "tools/call", {"name": "no_such_tool", "arguments": {}})
    check("모르는 도구: SDK는 -32602 오류가 아니라 isError 결과로 답한다 (M1과 다른 점)", r.get("result", {}).get("isError") is True, str(r))
    proc.stdin.close()
    proc.wait(timeout=15)
    err = proc.stderr.read().decode("utf-8", "replace")
    proc.stderr.close()
    proc.stdout.close()
    check("stdin을 닫으면 정상 종료한다", proc.returncode == 0, f"rc={proc.returncode} {err[-200:]}")

    # --- opencode ------------------------------------------------------------------------------------------
    with Sandbox("m2") as sb:
        status = sb.mcp_list(project, extra_env={"PYTHONUTF8": "0"})
        check("opencode mcp list: glossary-sdk connected (venv 파이썬으로 SDK 서버 실행)", status.get("glossary-sdk") == "connected", str(status))
        out, names, results = scripted_call(sb, project, "glossary-sdk_lookup_term", {"term": "서비스 수준 목표"})
        check("(가짜 모델) SDK 서버의 도구 glossary-sdk_lookup_term이 제공되고 한글 결과가 돌아온다 (UTF-8 모드 없이)",
              "glossary-sdk_lookup_term" in names and any("서비스가 지키기로 한 내부 목표" in r for r in results), f"{names} {results} {out[-300:]}")
        out, names, results = scripted_call(sb, project, "glossary-sdk_lookup_term", {"term": "없는용어"})
        check("(가짜 모델) SDK의 ToolError는 isError 결과로 모델에게 돌아간다", any("용어집에 없습니다" in r for r in results) and "✗ glossary-sdk_lookup_term" in out, f"{results} {out[-300:]}")
        if model_enabled():
            # PYTHONUTF8=0: Sandbox가 켜 둔 UTF-8 모드를 꺼서 Windows 기본 인코딩 상태에서 시험한다
            out = sb.run_model("팀 용어집에서 SLO가 무슨 뜻인지 찾아줘.", project, extra_env={"PWD": str(project), "PYTHONUTF8": "0"})
            model_check("모델이 glossary-sdk_lookup_term을 호출했다", out, tool_seen(out, "glossary-sdk_lookup_term"))
            model_check("한글 결과가 깨지지 않고 답변에 반영됐다 (SLO 정의의 일부가 나온다)", out, any(w in out for w in ("내부 목표", "목표 수치", "99.9")))
            print(out[-500:])
finally:
    shutil.rmtree(tmp, ignore_errors=True)
finish()
