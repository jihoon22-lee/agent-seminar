"""p4-notify-on-idle 검증. 모델 없는 검사(이벤트 훅 단위 테스트, 플러그인 로드, 설정)와 --model 검사."""
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fake_llm import FakeLLM  # noqa: E402
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
LOGS = HERE / "logs"
# 검사 중에는 소리·토스트를 실제로 내지 않고 notify.log 에만 기록한다. 이벤트 type 도 모두 남긴다.
TEST_ENV = {"NOTIFY_DRY_RUN": "1", "NOTIFY_LOG_ALL_EVENTS": "1"}


def show(label: str, text: str) -> None:
    """CHECK_VERBOSE=1 이면 모델 대화 기록을 그대로 출력한다 (README 의 '기대 결과' 수집용)."""
    if os.environ.get("CHECK_VERBOSE") == "1":
        print(f"--- {label} ---\n{text.strip()}\n--- end ---", flush=True)


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def scripted_run(sb, script, prompt, extra_env=None, timeout=240):
    """진짜 모델 대신 가짜 LLM(fake_llm.py)이 정해진 도구 호출을 하게 해서 opencode run 을 실행한다.
    반환: (stdout+stderr, 모델이 받은 도구 결과 문장들). 결과는 항상 같고 모델 한도를 쓰지 않는다."""
    with FakeLLM(script=script) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
        env.update(extra_env or {})
        proc = sb.opencode(["run", "-m", "fake/echo", "--auto", prompt], HERE, timeout=timeout, extra_env=env)
        results: list[str] = []
        for req in llm.main_requests():
            for msg in req.get("messages", []):
                if msg.get("role") == "tool":
                    text = FakeLLM.message_text(msg)
                    if text not in results:
                        results.append(text)
        return proc.stdout + "\n" + proc.stderr, results, json.dumps(llm.requests, ensure_ascii=False)


def main() -> None:
    shutil.rmtree(LOGS, ignore_errors=True)  # 다른 OS에서 복사돼 온 로그가 판정을 오염시키지 않게

    node = shutil.which("node")
    check("node 가 있다 (이벤트 훅 단위 테스트용)", node is not None, "node 가 없어 단위 테스트를 건너뜁니다", soft=True)
    if node:
        t = subprocess.run([node, str(HERE / "tests" / "notify.test.mjs")], capture_output=True, text=True, encoding="utf-8")
        check("이벤트 훅 단위 테스트 (idle/permission/중복/서브에이전트)", t.returncode == 0, t.stdout + t.stderr)

    with Sandbox("p4") as sb:
        cfg = sb.debug_config(HERE, extra_env=TEST_ENV)  # 설정을 읽는 과정에서 플러그인이 로드된다
        check("opencode 가 플러그인을 로드했다 (plugin-load.log)", "notify-on-idle loaded" in read(LOGS / "plugin-load.log"))
        check("permission.bash 가 ask 로 설정됨 (승인 알림 시연용)", cfg.get("permission", {}).get("bash") == "ask", str(cfg.get("permission")))

        # 가짜 LLM 이 bash 를 호출 → permission.bash=ask 라서 permission.asked 이벤트 발생 → 끝나면 session.idle
        shutil.rmtree(LOGS, ignore_errors=True)
        out, results, _ = scripted_run(sb, [("tool", "bash", {"command": "echo notify-demo", "description": "demo"}), "끝"], "echo 를 실행해줘", extra_env=TEST_ENV)
        show("scripted run", out)
        notify = read(LOGS / "notify.log")
        events = read(LOGS / "events.log")
        show("notify.log", notify)
        show("event types", "\n".join(sorted({line.split("\t")[1] for line in events.splitlines() if "\t" in line})))
        check("permission.asked 이벤트를 받아 notify.log 에 기록", "\tpermission\t" in notify, notify + out[-500:])
        check("session.idle 이벤트를 받아 notify.log 에 기록 (1회)", notify.count("\tidle\t") == 1, notify + out[-500:])
        check("events.log 에 session.idle / permission.asked type 이 남음", "session.idle" in events and "permission.asked" in events)

        if os.environ.get("NOTIFY_REAL_CHECK") == "1" and sys.platform == "win32":
            # 선택 검사: DRY_RUN 없이 실제로 소리·토스트 명령을 실행한다 (소리가 한 번 납니다).
            # opencode run 은 응답이 끝나자마자 종료되면서 알림 프로세스도 같이 끊기므로(TUI 와 다른 점),
            # TUI 처럼 오래 사는 서버(opencode serve)에 붙어서 실행한다.
            shutil.rmtree(LOGS, ignore_errors=True)
            with FakeLLM(script=["끝"]) as llm:
                cfg = json.dumps(llm.provider_config())
                with socket.socket() as s:
                    s.bind(("127.0.0.1", 0))
                    port = s.getsockname()[1]
                env = dict(sb.env, OPENCODE_CONFIG_CONTENT=cfg, PWD=str(HERE), NOTIFY_LOG_ALL_EVENTS="1")
                server = subprocess.Popen([sb.bin, "serve", "--port", str(port), "--hostname", "127.0.0.1"], cwd=str(HERE), env=env,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
                try:
                    for _ in range(60):
                        try:
                            socket.create_connection(("127.0.0.1", port), timeout=1).close()
                            break
                        except OSError:
                            time.sleep(1)
                    sb.opencode(["run", "--attach", f"http://127.0.0.1:{port}", "-m", "fake/echo", "--auto", "안녕"], HERE, timeout=120, extra_env={"OPENCODE_CONFIG_CONTENT": cfg})
                    time.sleep(5)
                finally:
                    server.terminate()
            notify = read(LOGS / "notify.log")
            show("notify.log (real notification)", notify)
            check("PowerShell 알림 프로세스가 시작됨", "powershell started" in notify, notify)
            check("소리 재생 단계가 끝까지 실행됨 (sound ok)", "sound ok" in notify, notify)
            check("토스트 표시 단계가 오류 없이 실행됨 (toast ok)", "toast ok" in notify, notify)

        if model_enabled():
            shutil.rmtree(LOGS, ignore_errors=True)
            # --auto 로 실행해도 ask 규칙의 permission.asked 이벤트는 발생한다.
            out = sb.run_model("bash 도구로 `echo notify-demo` 를 실행하고 결과를 알려주세요.", HERE, extra_env=TEST_ENV)
            show("model run", out)
            notify = read(LOGS / "notify.log")
            events = read(LOGS / "events.log")
            model_check("session.idle 이벤트를 받아 notify.log 에 기록", out, "\tidle\t" in notify)
            model_check("permission.asked 이벤트를 받아 notify.log 에 기록", out, "\tpermission\t" in notify)
            model_check("events.log 에 session.idle / permission.asked type 이 남음", out, "session.idle" in events and "permission.asked" in events)

    shutil.rmtree(LOGS, ignore_errors=True)
    finish()


if __name__ == "__main__":
    main()
