"""p9-format-on-save 검증. 모델 없는 검사(단위 테스트, 스크립트, 가짜 모델로 formatter+플러그인)와 --model 검사."""
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
IGNORE = shutil.ignore_patterns("logs", "__pycache__", "node_modules", "package.json", "package-lock.json", "bun.lock", ".gitignore")


def show(label: str, text: str) -> None:
    """CHECK_VERBOSE=1 이면 모델 대화 기록을 그대로 출력한다 (README 의 '기대 결과' 수집용)."""
    if os.environ.get("CHECK_VERBOSE") == "1":
        print(f"--- {label} ---\n{text.strip()}\n--- end ---", flush=True)


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def make_work(sb: Sandbox, name: str) -> pathlib.Path:
    """예제 폴더를 임시 폴더로 복사한다. 가짜 모델이 파일을 쓰는 곳이라 저장소를 더럽히지 않게 하려는 것."""
    work = sb.root / name
    shutil.copytree(HERE, work, ignore=IGNORE)
    return work


def scripted_run(sb, work, script, prompt="go", timeout=240):
    """가짜 LLM 이 정해진 도구 호출을 하게 하고 opencode run 을 실행한다.
    반환: (stdout+stderr, 모델이 받은 도구 결과 문장들(순서대로, 중복 제거 없음))."""
    with FakeLLM(script=script) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
        proc = sb.opencode(["run", "-m", "fake/echo", "--auto", prompt], work, timeout=timeout, extra_env=env)
        last = llm.main_requests()[-1] if llm.main_requests() else {}
        results = [FakeLLM.message_text(m) for m in last.get("messages", []) if m.get("role") == "tool"]
        return proc.stdout + "\n" + proc.stderr, results


def main() -> None:
    node = shutil.which("node")
    check("node 가 있다 (훅 단위 테스트용)", node is not None, "node 가 없어 단위 테스트를 건너뜁니다", soft=True)
    if node:
        t = subprocess.run([node, str(HERE / "tests" / "after.test.mjs")], capture_output=True, text=True, encoding="utf-8")
        check("tool.execute.after 단위 테스트", t.returncode == 0, t.stdout + t.stderr)

    # 스크립트 자체 (모델 없이)
    with Sandbox("p9") as sb:
        scratch = sb.root / "scratch"
        scratch.mkdir()
        (scratch / "x.json").write_text('{"b":1,"a":{"z":1,"y":2}}', encoding="utf-8")
        p = subprocess.run([sys.executable, str(HERE / "scripts" / "fmt_json.py"), str(scratch / "x.json")], capture_output=True, text=True)
        text = read(scratch / "x.json")
        check("fmt_json.py: 키 정렬 + 2칸 들여쓰기 + 끝 줄바꿈", p.returncode == 0 and text.index('"a"') < text.index('"b"') and '\n  "a": {\n    "y": 2' in text and text.endswith("}\n"), text)
        (scratch / "bad.json").write_text('{"a": 1,}', encoding="utf-8")
        p = subprocess.run([sys.executable, str(HERE / "scripts" / "fmt_json.py"), str(scratch / "bad.json")], capture_output=True, text=True)
        check("fmt_json.py: 깨진 JSON 은 건드리지 않고 종료 코드 1", p.returncode == 1 and read(scratch / "bad.json") == '{"a": 1,}')
        p = subprocess.run([sys.executable, str(HERE / "scripts" / "check_file.py"), str(HERE / "sample" / "lint_me.py")], capture_output=True, text=True, encoding="utf-8")
        check("check_file.py: sample/lint_me.py 의 쓰지 않는 import(os) 를 찾고 종료 코드 1", p.returncode == 1 and p.stdout.strip() == "1행: 쓰지 않는 import: os", p.stdout + p.stderr)

        # --- 설정에서 formatter 가 읽히고 플러그인이 로드된다
        work = make_work(sb, "work1")
        cfg = sb.debug_config(work)
        check("opencode.json 의 formatter 설정이 반영됨", cfg.get("formatter", {}).get("json-sorted", {}).get("extensions") == [".json"], json.dumps(cfg.get("formatter")))
        check("opencode 가 플러그인을 로드했다 (format-check.log)", "format-check loaded" in read(work / "logs" / "format-check.log"))

        # --- 가짜 모델: write → edit → (린트 결과를 보고) 고치기
        a = work / "a.json"
        lint = work / "lint.py"
        broken = work / "broken.json"
        only_write = work / "only_write.json"
        script = [
            ("tool", "write", {"filePath": str(a), "content": '{"b": 1, "a": {"z": 1, "y": 2}}'}),
            ("tool", "edit", {"filePath": str(a), "oldString": '"a": {', "newString": '"zz": {'}),
            ("tool", "write", {"filePath": str(lint), "content": "import os\nimport sys\n\nprint(sys.argv)\n"}),
            ("tool", "edit", {"filePath": str(lint), "oldString": "import os\n", "newString": ""}),
            ("tool", "write", {"filePath": str(broken), "content": '{"b": 1,}'}),
            ("tool", "write", {"filePath": str(only_write), "content": '{"b": 1, "a": 2}'}),
            "끝",
        ]
        out, results = scripted_run(sb, work, script)
        show("scripted run", out)
        show("tool results the model received", "\n---\n".join(results))
        after_edit = read(a)
        check("[Part A] write 직후 내장 formatter 가 실행됨 (write 만 한 파일이 정렬돼 있음)",
              read(only_write) == '{\n  "a": 2,\n  "b": 1\n}\n', read(only_write))
        check("[Part A] edit 직후에도 formatter 가 실행됨 (zz 가 맨 뒤로 정렬)", after_edit.index('"b"') < after_edit.index('"zz"') and after_edit.endswith("}\n"), after_edit)
        check("write 결과 뒤에 린트 결과가 붙고 그것이 모델 요청에 실제로 들어감 (쓰지 않는 import)",
              len(results) >= 3 and "Wrote file successfully." in results[2] and "[린트 결과] lint.py: 문제 발견" in results[2] and "1행: 쓰지 않는 import: os" in results[2], "\n---\n".join(results))
        check("모델이 고친 뒤(edit) 다시 검사하면 '문제 없음'", len(results) >= 4 and "Edit applied successfully." in results[3] and results[3].endswith("[린트 결과] lint.py: 문제 없음"), "\n---\n".join(results))
        check("json write/edit 결과에도 '문제 없음'이 붙음", all("[린트 결과] a.json: 문제 없음" in r for r in results[:2]), "\n---\n".join(results[:2]))
        check("깨진 JSON: formatter 는 조용히 건너뛰고(파일 그대로) 플러그인이 모델에게 알림",
              read(broken) == '{"b": 1,}' and len(results) >= 5 and "JSON 문법 오류" in results[4], read(broken) + "\n" + "\n".join(results[4:]))
        log = read(work / "logs" / "format-check.log")
        check("기록: FOUND 와 OK 가 남음", "FOUND lint.py: 1건" in log and "OK a.json" in log, log)

        # --- 검사기가 없으면 편집은 그대로 성립하고 모델 결과에는 아무것도 붙지 않는다
        work2 = make_work(sb, "work2")
        (work2 / "scripts" / "check_file.py").unlink()
        lint2 = work2 / "lint.py"
        out, results = scripted_run(sb, work2, [("tool", "write", {"filePath": str(lint2), "content": "import os\n"}), "끝"])
        check("검사기가 없어도 write 는 성공하고 결과는 원문 그대로", read(lint2) == "import os\n" and results == ["Wrote file successfully."], str(results) + out[-300:])
        check("검사기가 없으면 SKIP 만 기록", "SKIP lint.py: 검사기 없음" in read(work2 / "logs" / "format-check.log"))

        # --- 검사기가 실패(종료 코드 3)해도 마찬가지
        work3 = make_work(sb, "work3")
        (work3 / "scripts" / "check_file.py").write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
        lint3 = work3 / "lint.py"
        out, results = scripted_run(sb, work3, [("tool", "write", {"filePath": str(lint3), "content": "import os\n"}), "끝"])
        check("검사기가 실패해도 write 는 성공하고 결과는 원문 그대로", read(lint3) == "import os\n" and results == ["Wrote file successfully."], str(results) + out[-300:])
        check("검사기 실패는 FAIL 로 기록", "FAIL lint.py: 검사기 종료 코드=3" in read(work3 / "logs" / "format-check.log"))

        # --- 참고 실측: after 훅이 throw 하면 어떻게 되나 (임시 복사본에만 throw 하는 플러그인을 넣어 확인)
        work5 = make_work(sb, "work5")
        (work5 / ".opencode" / "plugins" / "format-check.js").write_text(
            'export const Thrower = async () => ({ "tool.execute.after": async () => { throw new Error("THROWN-IN-AFTER"); } });\n', encoding="utf-8")
        w5 = work5 / "thrown.json"
        out, results = scripted_run(sb, work5, [("tool", "write", {"filePath": str(w5), "content": '{"b": 1, "a": 2}'}), "끝"])
        check("after 훅에서 throw 하면: 파일은 이미 써지고 포맷됐는데 모델은 '도구 실패' 메시지만 받음",
              read(w5) == '{\n  "a": 2,\n  "b": 1\n}\n' and results == ["THROWN-IN-AFTER"], read(w5) + str(results))

        if model_enabled():
            work4 = make_work(sb, "work4")
            out = sb.run_model("sample/lint_me.py 맨 아래에 print('done') 한 줄을 추가하고, 도구 결과에 린트 결과가 나오면 그 문제를 고쳐 주세요.", work4)
            show("model run", out)
            fixed = read(work4 / "sample" / "lint_me.py")
            model_check("모델이 린트 결과(쓰지 않는 import os)를 보고 스스로 고침", out, "import os" not in fixed and "done" in fixed)

    finish()


if __name__ == "__main__":
    main()
