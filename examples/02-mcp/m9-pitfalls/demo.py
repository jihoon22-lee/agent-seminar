"""m9 디버깅 갤러리 — 고장 난 MCP 서버 4종을 진단한다 (표준 라이브러리만 사용).

    python demo.py            (Linux 에서 python 이 없으면 python3 demo.py)

하는 일
  1. `opencode mcp list` 로 서버마다 connected / failed 와 실패 사유를 읽는다.
  2. 같은 서버를 직접 띄워 JSON-RPC 를 손으로 보내 본다("probe"). opencode 가 보는 것과 똑같은 바이트를 우리가 본다.
  3. 도구 호출 때 모델/사용자에게 무엇이 보이는지 확인한다(가짜 LLM 이 도구를 호출하는 척한다 — 모델 불필요).
  4. 원인 진단 표와 opencode 로그 위치를 출력한다.

`opencode mcp list` 만으로는 안 보이는 고장(인코딩, 호출 시 크래시)이 있다는 것이 핵심이다.
옵션: --simulate-cp949  Linux 에서도 한국어 Windows 의 cp949 상황을 흉내 낸다 (PYTHONIOENCODING=cp949)
"""
import argparse
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
KOREAN_NAME = "홍길동"
EXPECTED = f"안녕하세요, {KOREAN_NAME}님!"


# --- 1. opencode mcp list ------------------------------------------------------------------
def mcp_list(opencode, env=None, cwd=HERE, timeout=240):
    """{서버: {"status": "connected"|"failed"|..., "reason": str, "seconds": float}} — 전체 목록을 한 번에 읽는다."""
    run_env = dict(env or os.environ, PWD=str(cwd))
    started = time.time()
    proc = subprocess.run([opencode, "mcp", "list"], cwd=str(cwd), env=run_env, stdin=subprocess.DEVNULL,
                          capture_output=True, timeout=timeout)
    seconds = time.time() - started
    text = ANSI.sub("", proc.stdout.decode("utf-8", errors="replace"))
    result, current = {}, None
    for line in text.splitlines():
        m = re.search(r"[✓✗○⚠]\s+(\S+)\s+(\S+)\s*$", line)
        if m:
            current = result[m.group(1)] = {"status": m.group(2), "reason": "", "seconds": seconds}
        elif current is not None and line[:1] in ("│", "|") and line.strip("│| ") and not re.match(r"^[│|]\s+(python|node|npx)", line):
            current["reason"] = (current["reason"] + " " + line.strip("│| ")).strip()  # Windows 콘솔은 │ 대신 | 로 그린다
    return result


# --- 2. probe: 서버를 직접 띄워 JSON-RPC 를 손으로 ----------------------------------------------
def server_command(entry):
    command = list(entry["command"])
    if command[0] in ("python", "python3"):
        command[0] = sys.executable
    return command


def probe(entry, simulate_cp949=False, startup_limit=12.0, call_limit=6.0):
    """서버를 띄우고 initialize → tools/list → tools/call(greet, 한글 이름)을 보낸다. 바이트 그대로 관찰한다."""
    env = dict(os.environ)
    env.pop("PYTHONUTF8", None)  # 우리 환경의 UTF-8 모드가 고장을 가리지 않게 (config 의 environment 는 다시 적용된다)
    env.pop("PYTHONIOENCODING", None)
    env.update(entry.get("environment", {}))
    if simulate_cp949:
        env["PYTHONIOENCODING"] = "cp949"
    out = {"first_line": None, "first_line_is_json": False, "init_seconds": None, "tools": None, "utf8_valid": True,
           "greet_text": None, "alive_after_call": None, "exit_code": None, "stderr": ""}
    proc = subprocess.Popen(server_command(entry), cwd=str(HERE), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    stderr_chunks = []
    threading.Thread(target=lambda: stderr_chunks.append(proc.stderr.read()), daemon=True).start()
    lines = []
    reader_done = threading.Event()

    def read_stdout():
        for raw in proc.stdout:
            lines.append((time.time(), raw))
        reader_done.set()

    threading.Thread(target=read_stdout, daemon=True).start()

    def send(obj):
        try:
            proc.stdin.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
            proc.stdin.flush()
        except OSError:
            pass

    def wait_response(mid, limit):
        deadline = time.time() + limit
        while time.time() < deadline:
            for _, raw in list(lines):
                try:
                    msg = json.loads(raw.decode("utf-8", errors="replace"))
                except ValueError:
                    continue
                if isinstance(msg, dict) and msg.get("id") == mid:
                    return msg, raw
            if proc.poll() is not None and reader_done.wait(0.2):
                break
            time.sleep(0.05)
        return None, None

    started = time.time()
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}}})
    init, raw = wait_response(1, startup_limit)
    if lines:
        out["first_line"] = lines[0][1].decode("utf-8", errors="replace").rstrip("\n")
        try:
            json.loads(out["first_line"])
            out["first_line_is_json"] = True
        except ValueError:
            pass
    if init is None:
        out["stderr"] = _finish(proc, stderr_chunks)
        out["exit_code"] = proc.poll()
        return out
    out["init_seconds"] = round(lines[-1][0] - started if lines else time.time() - started, 1)
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools, raw = wait_response(2, call_limit)
    if tools:
        out["tools"] = [t["name"] for t in tools["result"]["tools"]]
        out["utf8_valid"] = _is_utf8(raw)
    send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "greet", "arguments": {"name": KOREAN_NAME}}})
    call, raw = wait_response(3, call_limit)
    if call is not None:
        out["utf8_valid"] = out["utf8_valid"] and _is_utf8(raw)
        try:
            out["greet_text"] = call["result"]["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            out["greet_text"] = json.dumps(call, ensure_ascii=False)
    time.sleep(0.3)
    out["alive_after_call"] = proc.poll() is None
    out["exit_code"] = proc.poll()
    out["stderr"] = _finish(proc, stderr_chunks)
    return out


def _is_utf8(raw):
    try:
        raw.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _finish(proc, stderr_chunks):
    try:
        proc.kill()
    except OSError:
        pass
    proc.wait()
    time.sleep(0.2)
    return (stderr_chunks[0] if stderr_chunks else b"").decode("utf-8", errors="replace").strip()


# --- 3. 도구 호출 때 모델에게 보이는 것 (가짜 LLM) -------------------------------------------------
def call_experiment(opencode, server, tool, args, times=2, env=None, cwd=HERE):
    """가짜 모델이 `server_tool` 을 times 번 호출한다. (사용자 화면 출력, 모델이 돌려받은 tool 결과 목록)을 돌려준다."""
    with FakeLLM(script=[("tool", f"{server}_{tool}", args)] * times + ["DONE"]) as llm:
        run_env = dict(env or os.environ)
        run_env.update({"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "PWD": str(cwd)})
        proc = subprocess.run([opencode, "run", "-m", "fake/echo", "--auto", "go"], cwd=str(cwd), env=run_env,
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=240)
        screen = ANSI.sub("", (proc.stdout + proc.stderr).decode("utf-8", errors="replace"))
        results = [llm.message_text(m) for r in llm.main_requests() for m in r["messages"][-1:] if m.get("role") == "tool"]
    return screen, results


# --- 4. 로그 위치 ---------------------------------------------------------------------------------
def log_dir(opencode, env=None):
    proc = subprocess.run([opencode, "debug", "paths"], capture_output=True, env=env or os.environ, stdin=subprocess.DEVNULL)
    for line in ANSI.sub("", proc.stdout.decode("utf-8", errors="replace")).splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0] == "log":
            return parts[1].strip()
    return None


def diagnose(name, listed, probed, timeout_ms=None):
    """사람이 읽을 진단 한 줄."""
    if probed["first_line"] is not None and not probed["first_line_is_json"]:
        return f"stdout 에 JSON 이 아닌 글자가 섞임: {probed['first_line'][:48]!r} → 로그는 stderr 로"
    if probed["init_seconds"] is None:
        return "initialize 에 응답이 없음 (시작이 느리거나 종료됨) → timeout 늘리기 / 시작 작업 줄이기"
    if timeout_ms and probed["init_seconds"] * 1000 > timeout_ms:
        return f"initialize 까지 {probed['init_seconds']}초 > timeout {timeout_ms}ms → timeout 늘리거나 시작을 가볍게"
    if not probed["utf8_valid"] or (probed["greet_text"] and probed["greet_text"] != EXPECTED):
        return f"UTF-8 아님/한글 불일치: {probed['greet_text']!r} → reconfigure(encoding='utf-8')"
    if probed["alive_after_call"] is False:
        last = probed["stderr"].splitlines()[-1] if probed["stderr"] else ""
        return f"tools/call 중 프로세스 종료(exit {probed['exit_code']}): {last} → try/except 후 isError 반환"
    return "문제 없음"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate-cp949", action="store_true", help="Linux 에서도 cp949 인코딩 상황을 흉내 낸다")
    args = ap.parse_args()
    opencode = shutil.which("opencode")
    if not opencode:
        raise SystemExit("opencode 를 PATH 에서 찾을 수 없습니다.")
    config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))["mcp"]
    version = subprocess.run([opencode, "--version"], capture_output=True, text=True).stdout.strip()
    print(f"플랫폼 {platform.system()} / Python {platform.python_version()} / opencode {version}")
    print(f"stdout 인코딩 기본값(이 Python): {sys.stdout.encoding}  PYTHONUTF8={os.environ.get('PYTHONUTF8')}\n")

    print("== 1. opencode mcp list (서버 6개를 한 번에 연결해 본다)")
    listed = mcp_list(opencode)
    for name in config:
        info = listed.get(name, {"status": "?", "reason": ""})
        print(f"  {name:<16} {info['status']:<10} {info['reason']}")
    print(f"  (걸린 시간 {next(iter(listed.values()))['seconds']:.1f}초)\n")

    print("== 2. probe: 서버를 직접 띄워 한글 인사를 요청해 본다")
    probes = {}
    for name, entry in config.items():
        probes[name] = probe(entry, simulate_cp949=args.simulate_cp949)
        p = probes[name]
        print(f"  {name:<16} init={p['init_seconds'] if p['init_seconds'] is not None else '-'} json첫줄={p['first_line_is_json']} utf8={p['utf8_valid']} "
              f"greet={p['greet_text']!r} 호출후생존={p['alive_after_call']}")
    print()

    print("== 3. 도구 호출 때 모델에게 보이는 것 (가짜 모델이 도구를 호출)")
    for server, tool, arg, times in (("broken_encoding", "greet", {"name": KOREAN_NAME}, 1),
                                     ("crash_on_call", "greet", {"name": KOREAN_NAME}, 2),
                                     ("fixed_server", "greet", {"name": "boom"}, 2)):
        screen, results = call_experiment(opencode, server, tool, arg, times=times)
        print(f"  [{server}] 사용자 화면:")
        for line in screen.splitlines():
            if line.startswith(("✗", "⚙", "Error")):
                print("      " + line)
        for i, r in enumerate(results, 1):
            print(f"  [{server}] 모델이 받은 결과 {i}: {r[:110]!r}")
    print()

    print("== 4. 진단 표")
    print(f"  {'서버':<16} {'mcp list':<10} 진단")
    for name, entry in config.items():
        status = listed.get(name, {}).get("status", "?")
        print(f"  {name:<16} {status:<10} {diagnose(name, listed, probes[name], entry.get('timeout'))}")
    print()

    print("== 5. 로그는 어디에?")
    d = log_dir(opencode)
    print(f"  opencode 로그 폴더: {d}")
    print("  이번 실행의 로그를 화면으로: opencode run --print-logs --log-level DEBUG \"...\"")
    print("  MCP 서버 자신의 stderr(트레이스백)는 opencode 로그에 남지 않는다 → 서버를 직접 실행해서 보라 (위 probe 가 하는 일)")


if __name__ == "__main__":
    main()
