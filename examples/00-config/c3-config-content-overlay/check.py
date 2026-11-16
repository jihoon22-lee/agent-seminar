"""C3 검사: OPENCODE_CONFIG_CONTENT 덧씌우기가 파일을 건드리지 않고 프로젝트 설정을 이기는지."""
import hashlib
import json
import os
import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import DEFAULT_MODEL, MODEL_UNAVAILABLE, RATE_LIMIT_RE, Sandbox, _model_lock, check, finish, model_check, model_enabled, strip_ansi, tool_called  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import launch  # noqa: E402
from fake_llm import FakeLLM  # noqa: E402


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rpc(lines: list[dict]) -> list[dict]:
    """clock_server.py 에 JSON-RPC 를 한 줄씩 보내고 응답을 모은다."""
    payload = "".join(json.dumps(m) + "\n" for m in lines)
    proc = subprocess.run([sys.executable, str(HERE / "clock_server.py")], input=payload.encode("utf-8"),
                          capture_output=True, timeout=30, env={**os.environ, "PYTHONUTF8": "1"})
    return [json.loads(x) for x in proc.stdout.decode("utf-8").splitlines() if x.strip()]


project = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
check("opencode.json: model 키 없음, clock 서버는 적혀 있지 않음", "model" not in project and "mcp" not in project)

# 1. clock_server.py 직접 핸드셰이크
replies = rpc([
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "current_time", "arguments": {}}},
])
check("clock_server: initialize 응답", replies and replies[0]["result"]["serverInfo"]["name"] == "clock", str(replies))
check("clock_server: 도구 하나 (current_time)",
      len(replies) > 1 and [t["name"] for t in replies[1]["result"]["tools"]] == ["current_time"])
check("clock_server: 시각 문자열 반환 (YYYY-MM-DD ...)",
      len(replies) > 2 and replies[2]["result"]["content"][0]["text"][:4].isdigit(), str(replies[-1:]))

overlay = launch.build_overlay(None)
check("build_overlay: username 과 mcp.clock 을 추가", overlay["username"] == "overlay-user" and overlay["mcp"]["clock"]["enabled"] is True)
merged_overlay = launch.build_overlay(json.dumps({"instructions": ["extra.md"], "mcp": {"other": {"type": "local", "command": ["x"], "enabled": False}}}))
check("build_overlay: 기존 OPENCODE_CONFIG_CONTENT 위에 얹음", merged_overlay["instructions"] == ["extra.md"] and {"other", "clock"} <= set(merged_overlay["mcp"]))

before = {p.name: digest(p) for p in (HERE / "opencode.json", HERE / "clock_server.py")}
shell_before = os.environ.get("OPENCODE_CONFIG_CONTENT")

with Sandbox("c3") as sb:
    # 2. 덧씌우기 없음 vs 있음
    plain = sb.debug_config(HERE)
    check("덧씌우기 없음: 프로젝트 설정이 적용 (username=project-user), clock 없음",
          plain.get("username") == "project-user" and "clock" not in plain.get("mcp", {}), str(plain.get("username")))
    cfg = sb.debug_config(HERE, extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps(overlay)})
    check("덧씌우기: 프로젝트 설정을 이김 (username=overlay-user)", cfg.get("username") == "overlay-user", str(cfg.get("username")))
    check("덧씌우기: clock MCP 가 추가됨", cfg["mcp"]["clock"]["enabled"] is True and "clock_server.py" in cfg["mcp"]["clock"]["command"][-1])
    check("덧씌우기: 덮어쓰지 않은 프로젝트 값은 유지 (instructions)", "project-rules.md" in cfg.get("instructions", []))

    # 3. launch.py --print-config (샌드박스 환경으로 실행)
    proc = subprocess.run([sys.executable, str(HERE / "launch.py"), "--print-config"], capture_output=True, timeout=120,
                          env=sb.env, cwd=str(HERE), stdin=subprocess.DEVNULL)
    out = proc.stdout.decode("utf-8", errors="replace")
    check("launch.py --print-config 정상 종료", proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")[-400:])
    check("--print-config: project-user -> overlay-user 변화를 보여 줌", "project-user" in out and "overlay-user" in out, out)
    check("--print-config: mcp 항목에 clock", "clock" in out.split("mcp 항목")[-1].splitlines()[0], out)
    env2 = dict(sb.env, OPENCODE_CONFIG_CONTENT=json.dumps({"instructions": ["extra.md"]}))
    proc = subprocess.run([sys.executable, str(HERE / "launch.py"), "--print-config"], capture_output=True, timeout=120,
                          env=env2, cwd=str(HERE), stdin=subprocess.DEVNULL)
    out = proc.stdout.decode("utf-8", errors="replace")
    check("기존 OPENCODE_CONFIG_CONTENT 가 있어도 유지하며 얹음", "extra.md" in out and "overlay-user" in out, out)

    # 4. MCP 가 실제로 연결되는가
    status = sb.mcp_list(HERE)
    check("덧씌우기 없음: mcp list 에 clock 없음", "clock" not in status, str(status))
    status = sb.mcp_list(HERE, extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps(overlay)})
    check("덧씌우기: mcp list 에서 clock connected", status.get("clock") == "connected", str(status))

    # 4b. 가짜 모델로 launch.py --run 전체 경로를 결정적으로 확인 (모델 없이)
    #     fake_llm.py 의 provider 설정을 기존 OPENCODE_CONFIG_CONTENT 로 넘기면 launch.py 가 그 위에 clock 을 얹는다.
    with FakeLLM(script=[("tool", "clock_current_time", {}), "DONE"]) as llm:
        env = {**sb.env, "PWD": str(HERE), "OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
        proc = subprocess.run([sys.executable, str(HERE / "launch.py"), "--run", "go", "-m", "fake/echo"],
                              capture_output=True, timeout=180, env=env, cwd=str(HERE), stdin=subprocess.DEVNULL)
        text = strip_ansi(proc.stdout.decode("utf-8", errors="replace") + proc.stderr.decode("utf-8", errors="replace"))
        first = llm.main_requests()[0] if llm.main_requests() else {}
        tool_results = [llm.message_text(m) for r in llm.main_requests() for m in r["messages"] if m.get("role") == "tool"]
    check("launch.py --run: 기존 OPENCODE_CONFIG_CONTENT(가짜 모델 provider)를 보존하며 얹음", "clock_current_time" in FakeLLM.tool_names(first) if first else False, text[-300:])
    check("launch.py --run: 모델이 보는 도구 목록에 clock_current_time", "clock_current_time" in (FakeLLM.tool_names(first) if first else []))
    check("launch.py --run: 도구 호출이 실행되어 시각이 모델에게 돌아감",
          any(r[:4].isdigit() and "UTC" in r for r in tool_results), str(tool_results))
    check("launch.py --run: 출력에 도구 호출 줄이 보임", tool_called(text, "clock_current_time"), text[-300:])

    if model_enabled():
        # launch.py --run 을 그대로 실행한다 (샌드박스 환경 + 공용 모델 대기열)
        with _model_lock():
            try:
                proc = subprocess.run(
                    [sys.executable, str(HERE / "launch.py"), "--run",
                     "clock_current_time 도구를 호출해서 지금 시각을 알려 주세요.", "-m", DEFAULT_MODEL],
                    capture_output=True, timeout=420, env={**sb.env, "PWD": str(HERE)}, cwd=str(HERE), stdin=subprocess.DEVNULL)
                out = strip_ansi(proc.stdout.decode("utf-8", errors="replace") + "\n" + proc.stderr.decode("utf-8", errors="replace"))
            except subprocess.TimeoutExpired:
                out = "<<timeout>>"
        if RATE_LIMIT_RE.search(out):
            out = MODEL_UNAVAILABLE + "\n" + out
        model_check("launch.py --run: 모델이 clock_current_time 도구를 호출", out, tool_called(out, "clock_current_time"))

# 5. 파일과 내 셸이 그대로인가
after = {p.name: digest(p) for p in (HERE / "opencode.json", HERE / "clock_server.py")}
check("실행 전후 opencode.json 이 바뀌지 않음", before == after)
check("내 셸의 OPENCODE_CONFIG_CONTENT 는 바뀌지 않음 (자식 프로세스에만 전달)", os.environ.get("OPENCODE_CONFIG_CONTENT") == shell_before)
finish()
