"""m9 검증: 고장 난 서버 4종이 opencode 1.19.5 에서 어떻게 보이는가, 고친 서버는 정상인가.

모두 모델 없이 확인한다 (가짜 LLM 이 도구를 호출하는 척한다). --model 이면 실제 모델도 한 번 호출한다.
"""
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import MODEL_UNAVAILABLE, Sandbox, check, finish, model_check, model_enabled, tool_called  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import demo  # noqa: E402

config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
servers = config["mcp"]
check("opencode.json: 서버 6개, 'model' 키 없음", len(servers) == 6 and "model" not in config)
check("opencode.json: 타임아웃은 서버별 timeout(ms) 키 — slow_start 3000 / slow_start_ok 15000",
      servers["slow_start"]["timeout"] == 3000 and servers["slow_start_ok"]["timeout"] == 15000)


def with_env(entry, **env):
    e = dict(entry)
    e["environment"] = dict(entry.get("environment", {}), **env)
    return e


# --- 1. 서버를 직접 띄워 본다 (opencode 없이, probe) ------------------------------------------------
p = demo.probe(servers["broken_stdout"])
check("broken_stdout(partial): 첫 줄이 JSON 이 아님 — 배너가 응답 앞에 붙음, initialize 응답을 못 읽음",
      not p["first_line_is_json"] and p["first_line"].startswith("My MCP Server") and p["init_seconds"] is None, str(p))
p = demo.probe(with_env(servers["broken_stdout"], STDOUT_MODE="line"))
check("broken_stdout(line): 배너가 별도 한 줄이라 그 줄만 JSON 이 아니고 이후 응답은 정상 (opencode 는 이를 건너뜀)",
      not p["first_line_is_json"] and p["init_seconds"] is not None and p["greet_text"] == demo.EXPECTED, str(p))

p = demo.probe(with_env(servers["slow_start"], SLOW_START_SECONDS="2"))
check("slow_start: initialize 응답이 SLOW_START_SECONDS 만큼 늦음", p["init_seconds"] is not None and p["init_seconds"] >= 1.8, str(p))

p = demo.probe(servers["crash_on_call"])
check("crash_on_call: initialize/tools/list 는 정상, tools/call 에서 프로세스 종료(exit 1) + traceback 은 stderr",
      p["tools"] == ["greet"] and p["alive_after_call"] is False and p["exit_code"] == 1 and "database connection lost" in p["stderr"], str(p))

p = demo.probe(servers["fixed_server"])
check("fixed_server: 한글 인사 정상, 호출 후에도 살아 있음, stderr 에만 로그",
      p["first_line_is_json"] and p["utf8_valid"] and p["greet_text"] == demo.EXPECTED and p["alive_after_call"] and "started" in p["stderr"], str(p))

p = demo.probe(servers["broken_encoding"], simulate_cp949=True)
check("broken_encoding + PYTHONIOENCODING=cp949(한국어 Windows 흉내): UTF-8 이 아닌 바이트 또는 한글 불일치",
      (not p["utf8_valid"]) or p["greet_text"] != demo.EXPECTED or p["alive_after_call"] is False, str(p))
p = demo.probe(servers["fixed_server"], simulate_cp949=True)
check("fixed_server 는 cp949 환경에서도 정상 (reconfigure 덕분)", p["utf8_valid"] and p["greet_text"] == demo.EXPECTED, str(p))
acp = subprocess.run([sys.executable, "-X", "utf8=0", "-c", "import locale;print(locale.getpreferredencoding(False))"],
                     capture_output=True, text=True).stdout.strip()
p = demo.probe(servers["broken_encoding"])
if os.name == "nt" and acp.lower().replace("-", "") != "utf8":
    check(f"[Windows 실측, 로케일 {acp}] broken_encoding 은 그대로도 한글 응답이 깨진다", p["greet_text"] != demo.EXPECTED, str(p))
else:
    check(f"[{os.name}, 로케일 {acp}] UTF-8 로케일에서는 broken_encoding 도 멀쩡하다 (그래서 Linux 에서는 발견하기 어렵다)",
          p["greet_text"] == demo.EXPECTED, str(p))

# --- 2. opencode 가 보는 모습 ------------------------------------------------------------------------
with Sandbox("m9") as sb:
    listed = demo.mcp_list(sb.bin, sb.env)
    st = {k: v["status"] for k, v in listed.items()}
    check("mcp list: broken_stdout / slow_start 는 failed, 나머지는 connected",
          st == {"broken_stdout": "failed", "broken_encoding": "connected", "slow_start": "failed",
                 "slow_start_ok": "connected", "crash_on_call": "connected", "fixed_server": "connected"}, str(st))
    check("mcp list: 실패 사유가 'Operation timed out after <timeout>ms' 로 나옴",
          "timed out after 5000ms" in listed["broken_stdout"]["reason"] and "timed out after 3000ms" in listed["slow_start"]["reason"],
          str({k: v["reason"] for k, v in listed.items()}))
    check("mcp list: crash_on_call 은 호출 전까지는 connected (그래서 mcp list 만으로는 못 찾는다)", st["crash_on_call"] == "connected")

    log = sb.root / "data" / "opencode" / "log"
    text = "".join(f.read_text(encoding="utf-8", errors="replace") for f in log.glob("*.log")) if log.exists() else ""
    check("로그 파일(<XDG_DATA_HOME>/opencode/log)에 'server unavailable key=slow_start … status=failed' 경고가 남음",
          "server unavailable" in text and "key=slow_start " in text and "status=failed" in text, text[-500:])
    check("opencode debug paths 가 로그 폴더를 알려 줌", (demo.log_dir(sb.bin, sb.env) or "").replace("\\", "/").endswith("opencode/log"),
          str(demo.log_dir(sb.bin, sb.env)))

    # 호출 시점: 모델(가짜)이 도구를 호출했을 때 사용자·모델에게 보이는 것
    screen, results = demo.call_experiment(sb.bin, "crash_on_call", "greet", {"name": demo.KOREAN_NAME}, times=2, env=sb.env)
    check("crash_on_call: 모델이 받는 결과는 'MCP error -32000: Connection closed'", results[:1] == ["MCP error -32000: Connection closed"], str(results))
    check("crash_on_call: 한 번 죽으면 도구 자체가 목록에서 사라져 두 번째 호출은 'unavailable tool'",
          len(results) > 1 and "unavailable tool" in results[1], str(results))
    check("crash_on_call: 사용자 화면에도 failed + Connection closed", "failed" in screen and "Connection closed" in screen, screen[-400:])

    screen, results = demo.call_experiment(sb.bin, "fixed_server", "greet", {"name": "boom"}, times=2, env=sb.env)
    check("fixed_server(isError): 오류 내용이 모델에게 전달되고 서버는 살아 있어 두 번째 호출도 같은 방식으로 응답",
          results == ["도구 실행 실패: database connection lost"] * 2, str(results))
    screen, results = demo.call_experiment(sb.bin, "fixed_server", "greet", {"name": demo.KOREAN_NAME}, times=1, env=sb.env)
    check("fixed_server: 정상 호출", results == [demo.EXPECTED], str(results))

    # 타임아웃 키 실험: 새 서버 항목을 OPENCODE_CONFIG_CONTENT 로 얹는다
    def overlay(name, entry, extra=None):
        cfg = {"mcp": {name: dict({"type": "local", "command": ["python", "slow_start.py"]}, **entry)}}
        cfg.update(extra or {})
        return cfg

    def list_with(cfg):
        return demo.mcp_list(sb.bin, dict(sb.env, OPENCODE_CONFIG_CONTENT=json.dumps(cfg)))

    only = {"mcp": {k: {"enabled": False} for k in servers}}  # 기존 6개는 끄고 실험 항목만 본다

    def exp(name, entry, extra=None):
        cfg = overlay(name, entry, extra)
        cfg["mcp"].update(only["mcp"])
        return list_with(cfg)[name]

    r = exp("t_default", {"environment": {"SLOW_START_SECONDS": "4"}})
    check("timeout 키 없이 4초 걸리는 서버: 기본 제한 시간 안이라 connected", r["status"] == "connected", str(r))
    r = exp("t_short", {"environment": {"SLOW_START_SECONDS": "4"}, "timeout": 1500})
    check("mcp.<서버>.timeout=1500 이면 같은 서버가 failed (Operation timed out after 1500ms)",
          r["status"] == "failed" and "1500ms" in r["reason"], str(r))
    r = exp("t_exp", {"environment": {"SLOW_START_SECONDS": "4"}}, {"experimental": {"mcp_timeout": 1500}})
    check("experimental.mcp_timeout=1500 은 시작(연결) 제한이 아니므로 4초 걸리는 서버도 connected", r["status"] == "connected", str(r))

    def call_with(cfg, name, call_secs):
        from fake_llm import FakeLLM
        with FakeLLM(script=[("tool", f"{name}_greet", {"name": "a"}), "DONE"]) as llm:
            c = dict(llm.provider_config(), **cfg)
            c["mcp"].update(only["mcp"])
            sb.opencode(["run", "-m", "fake/echo", "--auto", "go"], HERE, timeout=120,
                        extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps(c), "PWD": str(HERE)})
            return [llm.message_text(m) for r_ in llm.main_requests() for m in r_["messages"][-1:] if m.get("role") == "tool"]

    res = call_with(overlay("t_call", {"environment": {"SLOW_START_SECONDS": "0", "SLOW_CALL_SECONDS": "5"}},
                            {"experimental": {"mcp_timeout": 2000}}), "t_call", 5)
    check("experimental.mcp_timeout=2000 이면 5초 걸리는 도구 호출은 'MCP error -32001: Request timed out'",
          res and "Request timed out" in res[0], str(res))
    res = call_with(overlay("t_call", {"environment": {"SLOW_START_SECONDS": "0", "SLOW_CALL_SECONDS": "5"}}), "t_call", 5)
    check("기본 제한에서는 같은 5초 호출이 성공", res and res[0] == demo.EXPECTED.replace("홍길동", "a"), str(res))

    if model_enabled():
        try:
            out = sb.run_model("fixed_server 의 greet 도구로 홍길동에게 인사해 줘.", HERE, extra_env={"PWD": str(HERE)})
        except Exception as exc:  # 모델 대기열 시간 초과 등은 '검증 불가'로 보고
            out = MODEL_UNAVAILABLE + f" {exc}"
        model_check("실제 모델이 fixed_server_greet 를 호출", out, tool_called(out, "fixed_server_greet"))

finish()
