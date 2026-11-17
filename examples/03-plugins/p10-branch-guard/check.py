"""p10-branch-guard 검증. 모델 없는 검사(임시 git 저장소를 쓰는 단위 테스트)와 가짜 모델 실행, --model 검사."""
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


def git(cwd: pathlib.Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    return (p.stdout + p.stderr).strip()


def make_repo(sb: Sandbox, name: str, branch: str) -> pathlib.Path:
    """예제 폴더(플러그인 포함)를 복사해 git 저장소로 만든다. 가짜 모델이 커밋을 시도하는 샌드박스 저장소."""
    repo = sb.root / name
    shutil.copytree(HERE, repo, ignore=IGNORE)
    git(repo, "init", "-q", "-b", branch)
    git(repo, "config", "user.name", "demo")
    git(repo, "config", "user.email", "demo.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / ".gitignore").write_text("logs/\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def scripted_run(sb, cwd, script, prompt="go", timeout=240):
    """가짜 LLM 이 정해진 도구 호출을 하게 하고 opencode run 을 실행한다. 반환: (stdout+stderr, 모델이 받은 도구 결과들)."""
    with FakeLLM(script=script) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
        proc = sb.opencode(["run", "-m", "fake/echo", "--auto", prompt], cwd, timeout=timeout, extra_env=env)
        last = llm.main_requests()[-1] if llm.main_requests() else {}
        results = [FakeLLM.message_text(m) for m in last.get("messages", []) if m.get("role") == "tool"]
        return proc.stdout + "\n" + proc.stderr, results


def bash(command: str) -> tuple:
    return ("tool", "bash", {"command": command, "description": "demo"})


def write(path: pathlib.Path, content: str = "hi\n") -> tuple:
    """파일은 write 도구로 만든다 (셸의 리디렉션은 PowerShell 5.1 에서 UTF-16 으로 써서 OS 마다 달라진다)."""
    return ("tool", "write", {"filePath": str(path), "content": content})


def main() -> None:
    node = shutil.which("node")
    has_git = shutil.which("git") is not None
    check("node 가 있다 (훅 단위 테스트용)", node is not None, "node 가 없어 단위 테스트를 건너뜁니다", soft=True)
    check("git 이 있다 (임시 저장소 검사용)", has_git, "git 이 없어 저장소를 쓰는 검사를 건너뜁니다", soft=True)
    if node and has_git:
        t = subprocess.run([node, str(HERE / "tests" / "guard.test.mjs")], capture_output=True, text=True, encoding="utf-8")
        check("tool.execute.before 단위 테스트 (임시 git 저장소)", t.returncode == 0, t.stdout + t.stderr)
    if not has_git:
        finish()

    with Sandbox("p10") as sb:
        repo = make_repo(sb, "repo-main", "main")
        check("opencode 가 플러그인을 로드했다 (branch-guard.log)", (sb.debug_config(repo), "branch-guard loaded" in read(repo / "logs" / "branch-guard.log"))[1])

        # --- main 브랜치: 커밋 시도는 막히고, 모델이 안내대로 브랜치를 만든 뒤에는 커밋된다
        # 두 셸(bash, PowerShell 5.1)에서 똑같이 동작하도록 명령은 한 줄에 하나씩 따로 호출한다. (`&&` 복합 형태는 단위 테스트가 확인)
        script = [
            write(repo / "x.txt"),
            bash("git add x.txt"),
            bash('git commit -m "add x"'),
            bash("git switch -c feat/x"),
            bash('git commit -m "add x"'),
            "끝",
        ]
        out, results = scripted_run(sb, repo, script)
        show("scripted run (main)", out)
        show("tool results the model received", "\n---\n".join(results))
        check("main 에서 git commit 이 막히고 한국어 안내(브랜치 이름, switch -c)가 모델에게 전달됨",
              len(results) >= 3 and "[branch-guard:protected-branch]" in results[2] and "'main'" in results[2] and "git switch -c <type>/<name>" in results[2], "\n".join(results))
        check("이어서 브랜치 생성 명령이 정상 실행됨", len(results) >= 4 and "feat/x" in results[3] and "branch-guard" not in results[3], "\n".join(results))
        check("안내대로 브랜치를 만들고 다시 커밋하면 실제로 커밋됨", git(repo, "log", "--format=%s", "feat/x").splitlines() == ["add x", "init"] and git(repo, "branch", "--show-current") == "feat/x", git(repo, "log", "--all", "--oneline"))
        check("main 브랜치에는 커밋이 늘지 않음", git(repo, "log", "--format=%s", "main").splitlines() == ["init"], git(repo, "log", "--all", "--oneline"))
        log = read(repo / "logs" / "branch-guard.log")
        check("차단 기록(BLOCKED)이 한 번만 남음", log.count("BLOCKED rule=protected-branch") == 1, log)

        # --- && 로 이은 복합 형태 (Linux 만: PowerShell 5.1 은 && 를 문법 오류로 거부한다)
        # 차단되면 명령 전체가 실행되지 않는다: echo 도 git add 도 돌지 않아 x.txt 가 없다.
        if os.name == "nt":
            print("[SKIP] && 복합 명령 실행 검사: Windows PowerShell 5.1 은 &&  를 받지 않아 건너뜀 (훅 판정은 단위 테스트가 확인)", flush=True)
        else:
            repo_c = make_repo(sb, "repo-compound", "main")
            compound = "echo hi > x.txt && git add x.txt && git commit -m 'add x'"
            out, results = scripted_run(sb, repo_c, [bash(compound), bash("git switch -c feat/x"), bash(compound), "끝"])
            show("scripted run (compound)", out)
            check("[복합] main 에서 && 로 이은 커밋 명령이 통째로 차단됨", len(results) >= 1 and "[branch-guard:protected-branch]" in results[0], "\n".join(results))
            check("[복합] 이어서 브랜치를 만든 뒤 같은 명령이 통과해 feat/x 에 커밋됨",
                  len(results) >= 3 and "branch-guard" not in results[2] and git(repo_c, "log", "--format=%s", "feat/x").splitlines() == ["add x", "init"], "\n".join(results) + git(repo_c, "log", "--all", "--oneline"))
            check("[복합] main 에는 커밋이 늘지 않음", git(repo_c, "log", "--format=%s", "main").splitlines() == ["init"])
            # 차단된 첫 시도에서는 x.txt 가 만들어지지 않았다: 첫 시도와 둘째 시도 사이에 파일이 없었음을 새 저장소에서 따로 확인
            repo_n = make_repo(sb, "repo-compound2", "main")
            out, results = scripted_run(sb, repo_n, [bash("echo hi > only.txt && git add only.txt && git commit -m 'add only'"), "끝"])
            check("[복합] 차단된 명령에서는 앞의 echo > 파일 도 실행되지 않음 (only.txt 없음)",
                  "[branch-guard:protected-branch]" in "".join(results) and not (repo_n / "only.txt").exists(), "\n".join(results))
            # 같은 줄에서 브랜치를 바꾸는 명령: 차단 메시지가 권하는 절차를 한 줄로 쓰면 통과, 반대로 main 으로 전환하는 줄은 막힘
            repo_s = make_repo(sb, "repo-switch", "main")
            git(repo_s, "branch", "feat/start")
            out, results = scripted_run(sb, repo_s, [bash("git switch -c feat/one && echo hi > one.txt && git add one.txt && git commit -m 'add one'"),
                                                      bash("git switch main && echo hi > two.txt && git add two.txt && git commit -m 'add two'"), "끝"])
            show("scripted run (switch in one line)", out)
            check("[전환] main 에서 'git switch -c … && … git commit' 한 줄은 통과해 새 브랜치에 커밋됨",
                  len(results) >= 1 and "branch-guard" not in results[0] and git(repo_s, "log", "--format=%s", "feat/one").splitlines() == ["add one", "init"], "\n".join(results))
            check("[전환] feat/one 에서 'git switch main && … git commit' 한 줄은 차단되고 브랜치도 바뀌지 않음",
                  len(results) >= 2 and "[branch-guard:protected-branch]" in results[1] and git(repo_s, "branch", "--show-current") == "feat/one" and not (repo_s / "two.txt").exists(), "\n".join(results) + git(repo_s, "branch", "--show-current"))
            repo_w = make_repo(sb, "repo-wrapped", "main")
            out, results = scripted_run(sb, repo_w, [bash('bash -lc "git commit --allow-empty -m wrapped"'), "끝"])
            check("[껍데기] main 에서 bash -lc \"git commit …\" 도 차단됨", len(results) >= 1 and "[branch-guard:protected-branch]" in results[0] and git(repo_w, "log", "--format=%s", "main").splitlines() == ["init"], "\n".join(results))

        # --- main 에서 push 와 draft PR (gh 가 없어도 가드가 먼저 막으므로 결과 문구로 구분된다)
        repo2 = make_repo(sb, "repo-main2", "main")
        out, results = scripted_run(sb, repo2, [bash("git push origin HEAD"), bash("gh pr create --draft --title x --body y"), bash("git push --dry-run"), "끝"])
        show("scripted run (push/draft)", out)
        show("tool results the model received (push/draft)", "\n---\n".join(results))
        check("main 에서 git push 가 push-to-protected 로 막힘", len(results) >= 1 and "[branch-guard:push-to-protected]" in results[0], "\n".join(results))
        check("gh pr create --draft 가 draft-pr 로 막히고 대안(--draft 없이)이 전달됨", len(results) >= 2 and "[branch-guard:draft-pr]" in results[1] and "gh pr create --title" in results[1], "\n".join(results))
        check("git push --dry-run 은 가드를 통과해 git 이 직접 답함 (원격이 없다는 git 의 메시지)", len(results) >= 3 and "branch-guard" not in results[2], "\n".join(results))

        # --- feature 브랜치에서 시작: 가드는 아무것도 하지 않는다
        repo3 = make_repo(sb, "repo-feat", "feat/start")
        out, results = scripted_run(sb, repo3, [write(repo3 / "y.txt"), bash("git add y.txt"), bash('git commit -m "add y"'), "끝"])
        show("scripted run (feature)", out)
        check("feature 브랜치에서는 첫 시도에 커밋이 됨", git(repo3, "log", "--format=%s").splitlines() == ["add y", "init"] and not any("branch-guard" in r for r in results), "\n".join(results) + git(repo3, "log", "--oneline"))
        check("차단 기록이 없음", "BLOCKED" not in read(repo3 / "logs" / "branch-guard.log"))

        # --- git 저장소가 아닌 곳: 허용하고 이유를 기록
        plain = sb.root / "plain"
        shutil.copytree(HERE, plain, ignore=IGNORE)
        out, results = scripted_run(sb, plain, [bash("git commit -m x"), "끝"])
        show("scripted run (not a repo)", out)
        check("저장소가 아니면 가드는 허용 (git 자신의 오류가 그대로 모델에게 감)", len(results) == 1 and "branch-guard" not in results[0] and "not a git repository" in results[0], "\n".join(results))
        check("허용 이유(not-a-repo)가 기록됨", "ALLOW not-a-repo" in read(plain / "logs" / "branch-guard.log"), read(plain / "logs" / "branch-guard.log"))

        if model_enabled():
            repo4 = make_repo(sb, "repo-model", "main")
            out = sb.run_model("README.md 를 만들고(내용은 한 줄) 'docs: add readme' 메시지로 커밋해 주세요. 커밋이 막히면 안내에 따라 해결하세요.", repo4)
            show("model run", out)
            model_check("모델이 main 이 아닌 브랜치에 커밋함", out, git(repo4, "log", "--format=%s", "main").splitlines() == ["init"] and "docs: add readme" in git(repo4, "log", "--all", "--format=%s"))

    finish()


if __name__ == "__main__":
    main()
