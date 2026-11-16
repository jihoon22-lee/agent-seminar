"""M3 check: 환경 변수 설정이 서버에 실제로 전달되는지, 토큰이 없으면 도구가 거절하는지, debug config에서 마스킹되는지 확인한다."""
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
SERVER = HERE / "server.py"
ENV_TOKEN = "demo-env-" + "token-123"          # 가짜 값 (런타임에 조립)


def clean_env(**extra):
    """자식 프로세스용 환경: PYTHONUTF8/PYTHONIOENCODING을 제거해 Windows 기본 인코딩(cp949) 상태에서도 서버가 동작하는지 확인한다."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env.update(extra)
    return env


def tool_seen(transcript, name):
    """성공(⚙)뿐 아니라 실패(✗, isError 결과)한 호출도 포함해 도구 이름이 transcript에 나오는지 본다."""
    return any(name in line for line in transcript.splitlines() if line.lstrip().startswith(("⚙", "✗", "→")))


def stdio_session(env_extra, calls, cwd=HERE):
    """server.py를 지정한 환경 변수로 띄워 호출 목록을 실행한다. (결과 리스트, stderr) 반환."""
    env = clean_env(**env_extra)
    for key in ("API_TOKEN", "GLOSSARY_PATH", "LOG_LEVEL"):
        if key not in env_extra:
            env.pop(key, None)
    proc = subprocess.Popen([sys.executable, str(SERVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=str(cwd), env=env)
    results = []

    def rpc(i, method, params):
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params}, ensure_ascii=False).encode("utf-8") + b"\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline().decode("utf-8"))

    rpc(0, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}})
    for i, (name, args) in enumerate(calls, start=1):
        results.append(rpc(i, "tools/call", {"name": name, "arguments": args}))
    proc.stdin.close()
    proc.wait(timeout=10)
    stderr = proc.stderr.read().decode("utf-8", "replace")
    proc.stderr.close()
    proc.stdout.close()
    return results, stderr


def text_of(resp):
    return resp["result"]["content"][0]["text"]


# --- 준비 스크립트 ---------------------------------------------------------------------------
proc = subprocess.run([sys.executable, str(HERE / "prepare.py")], cwd=str(HERE), capture_output=True, timeout=30)
token_file = HERE / "secrets" / "token.txt"
check("prepare.py가 secrets/token.txt(가짜 토큰)를 만든다", proc.returncode == 0 and token_file.read_text(encoding="utf-8").strip().startswith("demo-"))
file_token = token_file.read_text(encoding="utf-8").strip()
subprocess.run([sys.executable, str(HERE / "prepare.py")], cwd=str(HERE), capture_output=True, timeout=30)
check("prepare.py는 여러 번 실행해도 같은 결과(idempotent)", token_file.read_text(encoding="utf-8").strip() == file_token)

# --- opencode.json 모양 ------------------------------------------------------------------------
config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
env_entry, file_entry = config["mcp"]["glossary-env"], config["mcp"]["glossary-file"]
check("opencode.json: {env:DEMO_API_TOKEN}과 {file:./secrets/token.txt}를 environment로 넘긴다",
      env_entry["environment"]["API_TOKEN"] == "{env:DEMO_API_TOKEN}"
      and file_entry["environment"]["API_TOKEN"] == "{file:./secrets/token.txt}"
      and "model" not in config)
check("opencode.json: glossary-env는 켜져 있고 glossary-file은 꺼져 있다", env_entry["enabled"] is True and file_entry["enabled"] is False)

# --- 서버 단독 동작 (opencode 없이) ----------------------------------------------------------------
res, err = stdio_session({}, [("lookup_term", {"term": "SLO"}), ("list_terms", {}), ("server_info", {})])
check("토큰이 없으면 lookup_term이 isError:true로 거절하고 API_TOKEN을 안내한다",
      res[0]["result"]["isError"] is True and "API_TOKEN" in text_of(res[0]), str(res[0]))
check("토큰이 없으면 list_terms도 거절한다", res[1]["result"]["isError"] is True)
check("server_info는 토큰이 없어도 동작하고 '없음'을 보여 준다", res[2]["result"]["isError"] is False and "API_TOKEN=없음" in text_of(res[2]), text_of(res[2]))

res, err = stdio_session({"API_TOKEN": ENV_TOKEN}, [("lookup_term", {"term": "서비스 수준 목표"}), ("server_info", {})])
check("토큰이 있으면 한글 인자(별칭)로 조회하고 한글 정의를 돌려준다", res[0]["result"]["isError"] is False and "서비스가 지키기로 한 내부 목표" in text_of(res[0]), text_of(res[0]))
check("server_info는 토큰 값을 노출하지 않는다 (설정됨만)", "API_TOKEN=설정됨" in text_of(res[1]) and ENV_TOKEN not in text_of(res[1]))
check("서버 로그(stderr)에도 토큰 값이 없다", ENV_TOKEN not in err and "API_TOKEN=설정됨" in err, err)

# 빈 문자열 토큰 = 없는 것으로 취급 ({env:UNSET_VAR}가 빈 문자열로 치환되는 경우)
res, err = stdio_session({"API_TOKEN": ""}, [("lookup_term", {"term": "SLO"})])
check("API_TOKEN이 빈 문자열이어도 '없음'으로 취급해 거절한다", res[0]["result"]["isError"] is True)

with tempfile.TemporaryDirectory() as tmp:
    custom = pathlib.Path(tmp) / "mini.json"
    custom.write_text(json.dumps({"terms": [{"term": "핑퐁", "aliases": [], "definition": "다른 용어집 파일에서 읽은 용어"}]}, ensure_ascii=False), encoding="utf-8")
    res, err = stdio_session({"API_TOKEN": ENV_TOKEN, "GLOSSARY_PATH": str(custom)}, [("lookup_term", {"term": "핑퐁"}), ("server_info", {})])
    check("GLOSSARY_PATH로 다른 용어집을 읽는다", "다른 용어집 파일" in text_of(res[0]) and str(custom) in text_of(res[1]), text_of(res[0]))
    res, err_info = stdio_session({"API_TOKEN": ENV_TOKEN}, [("lookup_term", {"term": "SLO"})])
    res, err_debug = stdio_session({"API_TOKEN": ENV_TOKEN, "LOG_LEVEL": "DEBUG"}, [("lookup_term", {"term": "SLO"})])
    check("LOG_LEVEL=DEBUG이면 stderr에 DEBUG 로그가 더 나온다", "DEBUG" in err_debug and "DEBUG" not in err_info)

# --- opencode가 environment 값을 실제로 서버 프로세스에 넘기는가 -------------------------------------------
# 진짜 서버 대신 "받은 환경 변수를 파일에 적는 스크립트"를 command로 바꿔 끼운 임시 프로젝트를 만든다.
# (opencode debug config는 값을 ***로 가리므로, 실제 전달 여부는 이렇게 확인한다)
with tempfile.TemporaryDirectory() as tmp_name:
    tmp = pathlib.Path(tmp_name)
    (tmp / "secrets").mkdir()
    (tmp / "secrets" / "token.txt").write_text(file_token + "\n", encoding="utf-8")
    (tmp / "sub").mkdir()
    dumper = tmp / "dump_env.py"
    dumper.write_text(
        "import json, os\n"
        "keys = ('API_TOKEN', 'LOG_LEVEL', 'GLOSSARY_PATH')\n"
        "json.dump({k: os.environ.get(k) for k in keys}, open(os.environ['DUMP_OUT'], 'w', encoding='utf-8'))\n",
        encoding="utf-8")
    cfg = json.loads(json.dumps(config))
    for name, entry in cfg["mcp"].items():
        entry["command"] = [sys.executable, str(dumper)]
        entry["enabled"] = True
        entry["environment"]["DUMP_OUT"] = str(tmp / f"{name}.json")
    (tmp / "opencode.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    def dumped(name):
        path = tmp / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    with Sandbox("m3") as sb:
        # 1) 환경 변수가 있을 때, 2) 프로젝트 하위 폴더에서 실행해도 {file:}이 설정 파일 기준으로 풀리는지
        sb.opencode(["mcp", "list"], tmp / "sub", extra_env={"DEMO_API_TOKEN": ENV_TOKEN})
        env_dump, file_dump = dumped("glossary-env"), dumped("glossary-file")
        check("{env:DEMO_API_TOKEN} 값이 서버의 API_TOKEN으로 전달된다", env_dump and env_dump["API_TOKEN"] == ENV_TOKEN, str(env_dump))
        check("{file:./secrets/token.txt} 내용이 API_TOKEN으로 전달된다 (끝 줄바꿈 제거, 설정 파일 기준 상대 경로)",
              file_dump and file_dump["API_TOKEN"] == file_token, str(file_dump))
        check("environment의 일반 값(LOG_LEVEL, GLOSSARY_PATH)도 전달된다",
              env_dump and env_dump["LOG_LEVEL"] == "INFO" and env_dump["GLOSSARY_PATH"] == "glossary.json"
              and file_dump["LOG_LEVEL"] == "DEBUG", str(env_dump))
        # 3) 환경 변수가 정의되지 않으면?
        for name in ("glossary-env", "glossary-file"):
            (tmp / f"{name}.json").unlink(missing_ok=True)
        sb.opencode(["mcp", "list"], tmp, extra_env={"DEMO_API_TOKEN": ""})
        check("환경 변수가 비어 있으면 API_TOKEN은 빈 문자열로 전달된다 ({env:}는 오류가 아니다)",
              dumped("glossary-env") and dumped("glossary-env")["API_TOKEN"] == "", str(dumped("glossary-env")))

    # 설정 파일이 가리키는 {file:}이 없으면 opencode가 아예 시작하지 않는다
    bad = tmp / "bad"
    bad.mkdir()
    (bad / "opencode.json").write_text(json.dumps({"$schema": "https://opencode.ai/config.json", "mcp": {"x": {
        "type": "local", "command": [sys.executable, str(dumper)], "enabled": False,
        "environment": {"API_TOKEN": "{file:./secrets/없는파일.txt}"}}}}, ensure_ascii=False), encoding="utf-8")
    with Sandbox("m3bad") as sb:
        proc = sb.opencode(["debug", "config"], bad)
        out = proc.stdout + proc.stderr
        check("{file:}이 없는 파일을 가리키면 opencode가 'bad file reference' 설정 오류를 낸다 (enabled:false여도)",
              "bad file reference" in out or "does not exist" in out, out[-300:])

# --- 실제 예제 폴더에서 opencode ------------------------------------------------------------------------
with Sandbox("m3b") as sb:
    status = sb.mcp_list(HERE, extra_env={"DEMO_API_TOKEN": ENV_TOKEN})
    check("opencode mcp list: glossary-env connected / glossary-file disabled",
          status.get("glossary-env") == "connected" and status.get("glossary-file") == "disabled", str(status))
    proc = sb.opencode(["debug", "config"], HERE, extra_env={"DEMO_API_TOKEN": ENV_TOKEN})
    shown = proc.stdout
    cfg_shown = json.loads(shown[shown.index("{"):])
    shown_env = cfg_shown["mcp"]["glossary-env"]["environment"]
    check("opencode debug config: API_TOKEN은 ***로 가려지고 값이 출력에 나오지 않는다",
          shown_env["API_TOKEN"] == "***" and ENV_TOKEN not in shown and file_token not in shown, str(shown_env))
    check("opencode debug config: 토큰이 아닌 값(LOG_LEVEL, GLOSSARY_PATH)은 그대로 보인다",
          shown_env["LOG_LEVEL"] == "INFO" and shown_env["GLOSSARY_PATH"] == "glossary.json", str(shown_env))
    # 환경 변수를 정의하지 않아도 서버는 connected (도구가 거절할 뿐)
    status = sb.mcp_list(HERE, extra_env={"DEMO_API_TOKEN": ""})
    check("DEMO_API_TOKEN이 비어 있어도 서버는 connected (거절은 도구 호출 때 일어난다)", status.get("glossary-env") == "connected", str(status))

    out, names, results = scripted_call(sb, HERE, "glossary-env_lookup_term", {"term": "서비스 수준 목표"}, {"DEMO_API_TOKEN": ENV_TOKEN})
    check("(가짜 모델) 토큰이 있으면 glossary-env_lookup_term 결과(한글)가 모델에게 돌아간다; 꺼진 glossary-file 도구는 목록에 없다",
          any("서비스가 지키기로 한 내부 목표" in r for r in results) and "glossary-env_lookup_term" in names
          and not any(n.startswith("glossary-file_") for n in names), f"{names} {results}")
    out, names, results = scripted_call(sb, HERE, "glossary-env_lookup_term", {"term": "SLO"}, {"DEMO_API_TOKEN": ""})
    check("(가짜 모델) 토큰이 없으면 거절 메시지(API_TOKEN 안내)가 모델에게 돌아가고 화면에 ✗로 표시된다",
          any("API_TOKEN" in r and "설정되지 않아" in r for r in results) and "✗ glossary-env_lookup_term" in out, f"{results} / {out[-300:]}")

    overlay = json.dumps({"mcp": {"glossary-env": {"enabled": False}, "glossary-file": {"enabled": True}}})
    status = sb.mcp_list(HERE, extra_env={"OPENCODE_CONFIG_CONTENT": overlay, "DEMO_API_TOKEN": ""})
    check("OPENCODE_CONFIG_CONTENT로 enabled만 덮어쓰면 glossary-file이 켜진다 (설정 병합)",
          status.get("glossary-file") == "connected" and status.get("glossary-env") == "disabled", str(status))

    if model_enabled():
        pwd = {"PWD": str(HERE), "PYTHONUTF8": "0"}  # PYTHONUTF8=0: UTF-8 모드 끄기
        out = sb.run_model("glossary-env 도구로 SLO가 무슨 뜻인지 찾아줘.", HERE, extra_env={**pwd, "DEMO_API_TOKEN": ENV_TOKEN})
        model_check("[토큰 있음] 모델이 glossary-env_lookup_term을 호출하고 정의를 받았다",
                    out, tool_seen(out, "glossary-env_lookup_term") and "내부 목표" in out)
        print(out[-500:])
        out = sb.run_model("glossary-env 도구로 SLO가 무슨 뜻인지 찾아줘.", HERE, extra_env={**pwd, "DEMO_API_TOKEN": ""})
        model_check("[토큰 없음] 도구가 거절하고 API_TOKEN 안내가 transcript에 나온다",
                    out, tool_seen(out, "glossary-env_lookup_term") and "API_TOKEN" in out)
        print(out[-700:])
finish()
