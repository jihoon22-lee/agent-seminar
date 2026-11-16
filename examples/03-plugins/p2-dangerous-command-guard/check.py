"""p2-dangerous-command-guard 검증. 모델 없는 검사(규칙 표 단위 테스트 + 플러그인 로드)와 --model 검사."""
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

    node = shutil.which("node")
    check("node 가 있다 (규칙 표 단위 테스트용)", node is not None, "node 가 없어 단위 테스트를 건너뜁니다", soft=True)
    if node:
        t = subprocess.run([node, str(HERE / "tests" / "matcher.test.mjs")], capture_output=True, text=True, encoding="utf-8")
        check("규칙 표 단위 테스트 (차단/허용 사례)", t.returncode == 0, t.stdout + t.stderr)

    with Sandbox("p2") as sb:
        sb.debug_config(HERE)  # 설정을 읽는 과정에서 플러그인이 로드된다
        check("opencode 가 플러그인을 로드했다 (plugin-load.log)", "danger-guard loaded" in read(LOGS / "plugin-load.log"))

        # 가짜 LLM 이 위험한 명령(실행돼도 무해한 echo)과 평범한 명령을 차례로 시도한다
        shutil.rmtree(LOGS, ignore_errors=True)
        out, results, _ = scripted_run(
            sb,
            [
                ("tool", "bash", {"command": "echo DROP TABLE users;", "description": "drop"}),
                ("tool", "bash", {"command": "echo guard-ok-123", "description": "ok"}),
                "끝",
            ],
            "명령 두 개를 실행해줘",
        )
        show("scripted run", out)
        show("tool results the model received", "\n---\n".join(results))
        log = read(LOGS / "danger-guard.log")
        check("DROP TABLE 명령이 sql-drop 규칙으로 차단되고 한국어 안내가 모델에게 전달됨",
              "BLOCKED rule=sql-drop" in log and any("[danger-guard:sql-drop]" in r for r in results), log + out[-500:])
        check("평범한 명령은 통과해 실제로 실행됨", any("guard-ok-123" in r for r in results) and log.count("BLOCKED") == 1, "\n".join(results)[-500:])

        if model_enabled():
            shutil.rmtree(LOGS, ignore_errors=True)
            # 실제로 실행돼도 아무 일도 없는 명령으로 시험한다: echo 는 SQL 문장을 출력만 한다.
            out = sb.run_model("bash 도구로 정확히 이 명령을 실행하세요: echo DROP TABLE users;", HERE)
            show("model run", out)
            model_check("DROP TABLE 이 들어간 명령이 플러그인에 의해 차단됨", out, "BLOCKED rule=sql-drop" in read(LOGS / "danger-guard.log"))

            before = read(LOGS / "danger-guard.log").count("BLOCKED")
            out = sb.run_model("bash 도구로 정확히 이 명령을 실행하세요: echo guard-ok-123", HERE)
            show("model run", out)
            model_check("평범한 명령은 통과함", out, "guard-ok-123" in out and read(LOGS / "danger-guard.log").count("BLOCKED") == before)

    shutil.rmtree(LOGS, ignore_errors=True)
    finish()


if __name__ == "__main__":
    main()
