"""p3-audit-log 검증. 모델 없는 검사(훅 단위 테스트, 요약 스크립트, 플러그인 로드)와 --model 검사."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

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


def records() -> list[dict]:
    return [json.loads(line) for line in read(LOGS / "audit.jsonl").splitlines() if line.strip()]


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
    check("node 가 있다 (훅 단위 테스트용)", node is not None, "node 가 없어 단위 테스트를 건너뜁니다", soft=True)
    if node:
        out_dir = pathlib.Path(tempfile.mkdtemp(prefix="p3-audit-"))
        try:
            t = subprocess.run([node, str(HERE / "tests" / "audit.test.mjs"), str(out_dir)], capture_output=True, text=True, encoding="utf-8")
            check("훅 단위 테스트 (요약·가림·로테이션)", t.returncode == 0, t.stdout + t.stderr)
            s = subprocess.run(
                [sys.executable, str(HERE / "summarize_audit.py"), "--file", str(out_dir / "logs" / "audit.jsonl")],
                capture_output=True, text=True, encoding="utf-8",
            )
            check("summarize_audit.py 가 도구별 횟수와 타임라인을 출력", s.returncode == 0 and "도구별 호출 횟수" in s.stdout and "타임라인" in s.stdout and "bash" in s.stdout, s.stdout + s.stderr)
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    s = subprocess.run([sys.executable, str(HERE / "summarize_audit.py")], capture_output=True, text=True, encoding="utf-8")
    check("기록이 없을 때 안내 메시지와 종료 코드 1", s.returncode == 1 and "기록 파일이 없습니다" in s.stdout)

    with Sandbox("p3") as sb:
        sb.debug_config(HERE)  # 설정을 읽는 과정에서 플러그인이 로드된다
        check("opencode 가 플러그인을 로드했다 (plugin-load.log)", "audit-log loaded" in read(LOGS / "plugin-load.log"))

        # 가짜 LLM 이 notes.txt 읽기 → echo 실행 → 새 파일 쓰기를 순서대로 시도한다
        shutil.rmtree(LOGS, ignore_errors=True)
        out, results, _ = scripted_run(
            sb,
            [
                ("tool", "read", {"filePath": str(HERE / "notes.txt")}),
                ("tool", "bash", {"command": "echo audit-demo", "description": "demo"}),
                ("tool", "write", {"filePath": str(HERE / "logs" / "scratch.txt"), "content": "WRITE-BODY-SENTINEL-777"}),
                "끝",
            ],
            "notes.txt 를 읽고 echo 를 실행한 뒤 파일을 하나 써줘",
        )
        show("scripted run", out)
        recs = records()
        show("audit.jsonl", read(LOGS / "audit.jsonl"))
        tools = [r["tool"] for r in recs]
        check("audit.jsonl 에 read, bash, write 가 순서대로 기록됨", tools == ["read", "bash", "write"], str(tools) + out[-400:])
        read_rec = next((r for r in recs if r["tool"] == "read"), {})
        check("read 기록에 notes.txt 경로가 남음", "notes.txt" in str(read_rec.get("args", {}).get("filePath", "")))
        raw = read(LOGS / "audit.jsonl")
        check("파일 내용(SENTINEL)과 write 본문은 로그에 없음", bool(raw) and "SENTINEL-CONTENT-4242" not in raw and "WRITE-BODY-SENTINEL-777" not in raw)
        check("모델은 notes.txt 내용을 실제로 받았음 (로그에만 없는 것)", any("SENTINEL-CONTENT-4242" in r for r in results))
        s = subprocess.run([sys.executable, str(HERE / "summarize_audit.py")], capture_output=True, text=True, encoding="utf-8")
        show("summarize_audit.py", s.stdout)
        check("summarize_audit.py 가 실제 기록을 요약", s.returncode == 0 and "read" in s.stdout and "write" in s.stdout, s.stdout + s.stderr)

        if model_enabled():
            shutil.rmtree(LOGS, ignore_errors=True)
            out = sb.run_model(
                "read 도구로 notes.txt 를 읽고, 그다음 bash 도구로 `echo audit-demo` 를 실행하세요. 읽은 내용은 한 줄로 요약해 주세요.",
                HERE,
            )
            show("model run", out)
            recs = records()
            tools = {r["tool"] for r in recs}
            model_check("audit.jsonl 에 read 와 bash 호출이 기록됨", out, {"read", "bash"} <= tools)
            read_rec = next((r for r in recs if r["tool"] == "read"), {})
            model_check("read 기록에 notes.txt 경로가 남음", out, "notes.txt" in str(read_rec.get("args", {}).get("filePath", "")))
            model_check("파일 내용(SENTINEL)은 로그에 없음", out, bool(recs) and "SENTINEL-CONTENT-4242" not in read(LOGS / "audit.jsonl"))
            s = subprocess.run([sys.executable, str(HERE / "summarize_audit.py")], capture_output=True, text=True, encoding="utf-8")
            model_check("summarize_audit.py 가 실제 기록을 요약", out, s.returncode == 0 and "read" in s.stdout)

    shutil.rmtree(LOGS, ignore_errors=True)
    finish()


if __name__ == "__main__":
    main()
