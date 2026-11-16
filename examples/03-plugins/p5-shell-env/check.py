"""p5-shell-env 검증. 모델 없는 검사(훅 단위 테스트, 플러그인 로드, 가짜 인증서 파일)와 --model 검사."""
import json
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fake_llm import FakeLLM  # noqa: E402
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
LOGS = HERE / "logs"


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

    pem = HERE / "certs" / "demo-ca.pem"
    check("certs/demo-ca.pem 은 진짜 인증서가 아닌 자리표시 파일", pem.exists() and "BEGIN" not in read(pem))

    env = {k: v for k, v in os.environ.items() if k not in ("APP_ENV", "REQUESTS_CA_BUNDLE")}
    p = subprocess.run([sys.executable, str(HERE / "show_env.py")], capture_output=True, text=True, encoding="utf-8", env=env)
    check("show_env.py 를 직접 실행하면 APP_ENV=None (주입은 에이전트 셸에서만)", p.returncode == 0 and "APP_ENV=None" in p.stdout, p.stdout + p.stderr)

    node = shutil.which("node")
    check("node 가 있다 (훅 단위 테스트용)", node is not None, "node 가 없어 단위 테스트를 건너뜁니다", soft=True)
    if node:
        t = subprocess.run([node, str(HERE / "tests" / "shell-env.test.mjs")], capture_output=True, text=True, encoding="utf-8")
        check("shell.env 훅 단위 테스트", t.returncode == 0, t.stdout + t.stderr)

    with Sandbox("p5") as sb:
        sb.debug_config(HERE)  # 설정을 읽는 과정에서 플러그인이 로드된다
        check("opencode 가 플러그인을 로드했다 (plugin-load.log)", "shell-env loaded" in read(LOGS / "plugin-load.log"))

        # 가짜 LLM 이 python 한 줄로 APP_ENV 를 출력하는 bash 명령을 실행한다
        shutil.rmtree(LOGS, ignore_errors=True)
        cmd = "python -c \"import os; print('APP_ENV=' + str(os.environ.get('APP_ENV')) + ' CA=' + str(os.environ.get('REQUESTS_CA_BUNDLE')))\""
        out, results, _ = scripted_run(sb, [("tool", "bash", {"command": cmd, "description": "print env"}), "끝"], "APP_ENV 를 출력해줘")
        show("scripted run", out)
        show("tool results the model received", "\n---\n".join(results))
        check("에이전트 셸에서 APP_ENV=dev 가 보임", any("APP_ENV=dev" in r for r in results), "\n".join(results) + out[-500:])
        check("REQUESTS_CA_BUNDLE 이 certs/demo-ca.pem 절대 경로로 보임", any("demo-ca.pem" in r and "CA=None" not in r for r in results), "\n".join(results))
        check("shell-env.log 에 주입 기록", "injected APP_ENV" in read(LOGS / "shell-env.log"))

        if model_enabled():
            shutil.rmtree(LOGS, ignore_errors=True)
            out = sb.run_model(
                "bash 도구로 python 한 줄을 실행해서 환경변수 APP_ENV 의 값을 출력해 주세요. "
                "예: python -c \"import os; print('APP_ENV=' + str(os.environ.get('APP_ENV')))\"",
                HERE,
            )
            show("model run", out)
            model_check("에이전트 셸에서 APP_ENV=dev 가 보임", out, "APP_ENV=dev" in out)
            model_check("shell-env.log 에 주입 기록", out, "injected APP_ENV" in read(LOGS / "shell-env.log"))

    shutil.rmtree(LOGS, ignore_errors=True)
    finish()


if __name__ == "__main__":
    main()
