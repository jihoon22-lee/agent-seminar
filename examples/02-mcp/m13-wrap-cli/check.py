"""M13 check: git을 감싼 읽기 전용 MCP 서버의 정상 호출, 방어(옵션 주입·경로 이탈·출력 제한·시간 제한·오류), opencode 연결."""
import importlib.util
import json
import os
import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402

SANDBOX = HERE / "sandbox"
SERVER = HERE / "server.py"


def clean_env():
    return {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}


class StdioClient:
    """server.py를 cwd 폴더에서 띄워 JSON 줄을 주고받는 최소 클라이언트."""

    def __init__(self, cwd):
        self.proc = subprocess.Popen([sys.executable, str(SERVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, cwd=str(cwd), env=clean_env())
        self.n = 0
        self.rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}})

    def rpc(self, method, params=None):
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method, **({"params": params} if params is not None else {})}
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False).encode("utf-8") + b"\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline().decode("utf-8"))

    def call(self, name, **arguments):
        """도구를 부르고 (isError, 텍스트)를 돌려준다."""
        r = self.rpc("tools/call", {"name": name, "arguments": arguments})
        res = r["result"]
        return res["isError"], res["content"][0]["text"]

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc.stderr.read()
        self.proc.stderr.close()
        self.proc.stdout.close()
        return self.proc.returncode


def git(*args, cwd=SANDBOX):
    return subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=str(cwd), capture_output=True, encoding="utf-8")


# --- 준비 ------------------------------------------------------------------------------
config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
check("opencode.json은 v1 형식(mcp.repo.type/command)이고 model 키가 없다",
      config["mcp"]["repo"]["type"] == "local" and isinstance(config["mcp"]["repo"]["command"], list)
      and "model" not in config and config.get("$schema") == "https://opencode.ai/config.json")

if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
    check("git이 설치되어 있다 (없으면 이 예제는 건너뜀)", False, soft=True)
    finish()

p = subprocess.run([sys.executable, str(HERE / "prepare.py")], cwd=str(HERE), capture_output=True, timeout=120)
check("prepare.py가 sandbox/ 저장소를 만든다", p.returncode == 0 and (SANDBOX / ".git").exists(), p.stderr.decode("utf-8", "replace"))
authors = set(git("log", "--format=%an").stdout.split())
n_commits = len(git("log", "--format=%h").stdout.split())
check("이력: 커밋 7개, 작성자 dev-alpha / dev-beta 두 명", n_commits == 7 and authors == {"dev-alpha", "dev-beta"}, f"{n_commits} {authors}")
head1 = git("rev-parse", "HEAD").stdout
subprocess.run([sys.executable, str(HERE / "prepare.py")], cwd=str(HERE), capture_output=True, timeout=120)
check("prepare.py는 다시 실행해도 같은 커밋 해시 (결정적, 고정 날짜·작성자)", git("rev-parse", "HEAD").stdout == head1)
check("sandbox/에 server.py와 opencode.json이 복사되고 git 이력에는 들어가지 않는다",
      (SANDBOX / "server.py").exists() and (SANDBOX / "opencode.json").exists()
      and "server.py" not in git("ls-tree", "-r", "--name-only", "HEAD").stdout)

# --- 정상 호출 3개 ------------------------------------------------------------------------
c = StdioClient(SANDBOX)
tools = c.rpc("tools/list")["result"]["tools"]
check("tools/list: git_log, git_blame, git_diff_stat (모두 description과 inputSchema 있음)",
      [t["name"] for t in tools] == ["git_log", "git_blame", "git_diff_stat"]
      and all(t["description"] and t["inputSchema"]["type"] == "object" for t in tools))

err, text = c.call("git_log", max_count=3)
lines = text.splitlines()
check("git_log: 최근 3개를 '해시  날짜  작성자  제목' 한 줄씩, 한글 제목 그대로",
      not err and len(lines) == 3 and "dev-alpha" in lines[0] and "README에 설계 메모 안내 추가" in lines[0], text)
err, text = c.call("git_log", path="docs/설계.md")
check("git_log + path: 그 파일을 건드린 커밋만 (한글 파일명 인자 OK)", not err and len(text.splitlines()) == 1 and "설계 메모 추가" in text, text)
err, text = c.call("git_blame", file="src/pricing.py", start_line=14, end_line=16)
check("git_blame: 줄 범위의 작성자·날짜 (16번 줄은 세금 반올림을 고친 dev-alpha)",
      not err and len(text.splitlines()) == 3 and "dev-alpha 2026-03-06" in text.splitlines()[2], text)
err, text = c.call("git_diff_stat", **{"from": "HEAD~4", "to": "HEAD"})
check("git_diff_stat: 파일별 변경량 요약, 한글 파일명이 이스케이프되지 않는다 (core.quotepath=false)",
      not err and "docs/설계.md" in text and "3 files changed" in text and "\\354" not in text, text)
default_quoted = subprocess.run(["git", "diff", "--name-only", "HEAD~4", "HEAD"], cwd=str(SANDBOX), capture_output=True,
                                encoding="utf-8").stdout
check("(대조) 옵션 없이 git을 직접 부르면 한글 파일명이 \\354\\204... 로 이스케이프된다", "\\354" in default_quoted, default_quoted)

# --- 방어 1: 옵션 주입 --------------------------------------------------------------------
before = {p.name for p in SANDBOX.iterdir()}
err, text = c.call("git_diff_stat", **{"from": "--output=pwned.txt", "to": "HEAD"})
check("옵션 주입 거부: from='--output=pwned.txt' -> isError, 파일이 만들어지지 않는다",
      err and "'-'로 시작" in text and not (SANDBOX / "pwned.txt").exists(), text)
err, text = c.call("git_log", path="--all")
check("옵션 주입 거부: path='--all'", err and "'-'로 시작" in text, text)
err, text = c.call("git_blame", file="--help")
check("옵션 주입 거부: file='--help'", err and "'-'로 시작" in text, text)
err, text = c.call("git_diff_stat", **{"from": "HEAD~1\n--output=x", "to": "HEAD"})
check("줄바꿈이 든 값 거부", err and "제어 문자" in text, text)
# 방어가 왜 필요한지: 거르지 않고 git에 그대로 넘기면 실제로 파일이 써진다
raw = subprocess.run(["git", "diff", "--stat", "--output=pwned.txt", "HEAD~1", "HEAD", "--"], cwd=str(SANDBOX), capture_output=True)
wrote = (SANDBOX / "pwned.txt").exists()
if wrote:
    (SANDBOX / "pwned.txt").unlink()
check("(대조) 검증 없이 git에 직접 넘긴 --output=...은 읽기 전용 명령인데도 파일을 쓴다", wrote, str(raw))
check("거부된 호출 뒤 sandbox/에 새 파일이 없다", {p.name for p in SANDBOX.iterdir()} == before)

# --- 방어 2: 저장소 밖 경로 ------------------------------------------------------------------
err, text = c.call("git_blame", file="../prepare.py")
check("저장소 밖 경로 거부: ../prepare.py", err and "저장소 밖" in text, text)
err, text = c.call("git_log", path="src/../../server.py")
check("저장소 밖 경로 거부: src/../../server.py (중간의 ..도 풀어서 본다)", err and "저장소 밖" in text, text)
abs_path = str(SERVER)
err, text = c.call("git_log", path=abs_path)
check("절대 경로 거부", err and "절대 경로" in text, text)

# --- 방어 3: 출력 제한 ------------------------------------------------------------------------
err, text = c.call("git_blame", file="src/pricing.py", start_line=1, end_line=60)
lines = text.splitlines()
check("긴 출력은 40줄로 자르고 '…(N줄 생략)'을 붙인다",
      not err and len(lines) == 41 and lines[-1] == "…(13줄 생략)", f"{len(lines)}줄, 끝: {lines[-1]!r}")
err, text = c.call("git_blame", file="src/pricing.py", start_line=1, end_line=40)
check("40줄 이하는 자르지 않는다 (표시 없음)", not err and len(text.splitlines()) == 40 and "생략" not in text)
err, text = c.call("git_log", max_count=500)
check("max_count 범위를 넘으면 거부 (1~50)", err and "1~50" in text, text)

# --- 방어 4: 실패는 isError + stderr ---------------------------------------------------------------
err, text = c.call("git_diff_stat", **{"from": "no-such-rev", "to": "HEAD"})
check("없는 리비전 -> isError:true 이고 git의 stderr 문장이 그대로 들어 있다",
      err and "종료 코드 128" in text and "bad revision 'no-such-rev'" in text, text)
err, text = c.call("git_blame", file="src/없는파일.py")
check("없는 파일 -> isError:true (서버는 죽지 않는다)", err and "no such path" in text, text)
r = c.rpc("tools/call", {"name": "git_log", "arguments": {}})
check("오류 뒤에도 서버가 계속 응답한다", r["result"]["isError"] is False)
r = c.rpc("tools/call", {"name": "git_push", "arguments": {}})
check("모르는 도구 이름은 -32602", r.get("error", {}).get("code") == -32602, str(r))
check("서버는 stdin을 닫으면 정상 종료(0)한다", c.close() == 0)

# 저장소가 아닌 폴더에서 실행하면 오류 문장으로 알린다
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory(prefix="m13-nogit-") as tmp:
    env = {"GIT_CEILING_DIRECTORIES": str(pathlib.Path(tmp).parent)}
    os.environ.update(env)
    c2 = StdioClient(tmp)
    err, text = c2.call("git_log")
    check("git 저장소가 아닌 폴더에서는 isError:true + git의 안내 문장", err and "not a git repository" in text, text)
    c2.close()
    del os.environ["GIT_CEILING_DIRECTORIES"]

# --- 심볼릭 링크로 저장소를 빠져나가는 경로 (Windows에서 권한이 없으면 건너뜀) ---------------------
with tempfile.TemporaryDirectory(prefix="m13-link-") as tmp:
    tmp = pathlib.Path(tmp)
    repo = tmp / "repo"
    repo.mkdir()
    (tmp / "outside.txt").write_text("secret\n", encoding="utf-8")
    try:
        os.symlink(tmp / "outside.txt", repo / "link.txt")
        linked = True
    except (OSError, NotImplementedError):
        linked = False
    if linked:
        subprocess.run(["git", "init", "-q"], cwd=str(repo), capture_output=True)
        c3 = StdioClient(repo)
        err, text = c3.call("git_blame", file="link.txt")
        check("심볼릭 링크로 저장소 밖을 가리키는 경로 거부", err and "저장소 밖" in text, text)
        c3.close()
    else:
        check("심볼릭 링크 시험은 권한이 없어 건너뜀", False, soft=True)

# --- 저장소 설정에 적힌 외부 프로그램이 실행되지 않는다 -----------------------------------------------------
# 저장소의 .git/config 와 .gitattributes 는 저장소를 받은 사람이 고를 수 없는 입력이다. textconv, 외부 diff, fsmonitor 에
# 프로그램을 적어 두면 읽기 전용 명령처럼 보이는 git blame 도 그 프로그램을 실행한다. 표식 파일을 남기는 프로그램으로 확인한다.
with tempfile.TemporaryDirectory(prefix="m13-hooks-") as tmp:
    tmp = pathlib.Path(tmp)
    repo = tmp / "repo"
    repo.mkdir()
    marks = tmp / "marks"
    marks.mkdir()
    probe = tmp / "probe.py"
    probe.write_text("import sys, pathlib\npathlib.Path(sys.argv[1]).write_text('ran', encoding='utf-8')\n"
                     "if len(sys.argv) > 2 and pathlib.Path(sys.argv[2]).is_file():\n"
                     "    sys.stdout.write(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))\n", encoding="utf-8")

    def program(name):
        """git 설정에 적을 명령: 파이썬으로 probe.py 를 실행해 marks/<name> 을 만든다 (git 이 sh 로 실행하므로 슬래시 표기)."""
        return f'"{pathlib.Path(sys.executable).as_posix()}" "{probe.as_posix()}" "{(marks / name).as_posix()}"'

    ident = {"GIT_AUTHOR_NAME": "demo", "GIT_AUTHOR_EMAIL": "", "GIT_COMMITTER_NAME": "demo", "GIT_COMMITTER_EMAIL": ""}
    gitenv = {**clean_env(), **ident}

    def hgit(*args):
        return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, encoding="utf-8", env=gitenv)

    hgit("init", "-q")
    (repo / ".gitattributes").write_text("*.txt diff=x\n", encoding="utf-8")
    (repo / "f.txt").write_text("a\nb\n", encoding="utf-8")
    hgit("add", ".")
    hgit("commit", "-qm", "one")
    (repo / "f.txt").write_text("a\nb\nc\n", encoding="utf-8")
    hgit("commit", "-qam", "two")
    hgit("config", "diff.x.textconv", program("textconv"))
    hgit("config", "diff.external", program("extdiff"))
    hgit("config", "core.fsmonitor", program("fsmonitor"))

    # 대조: 막지 않은 git 은 저장소 설정의 프로그램을 실제로 실행한다 (이게 안 되면 아래 검사가 아무것도 증명하지 못한다)
    hgit("blame", "-L", "1,2", "--", "f.txt")
    hgit("diff", "HEAD~1", "HEAD", "--")
    ran = {m.name for m in marks.iterdir()}
    check("(대조) 막지 않은 git blame 은 textconv 와 fsmonitor 를, git diff 는 외부 diff 를 실행한다", {"textconv", "fsmonitor", "extdiff"} <= ran, str(sorted(ran)), soft=True)
    for m in marks.iterdir():
        m.unlink()

    c4 = StdioClient(repo)
    err_blame, text_blame = c4.call("git_blame", file="f.txt")
    err_log, _ = c4.call("git_log")
    err_diff, _ = c4.call("git_diff_stat", **{"from": "HEAD~1", "to": "HEAD"})
    check("저장소에 textconv·외부 diff·fsmonitor 가 설정되어 있어도 세 도구가 정상 동작한다", not (err_blame or err_log or err_diff) and "demo" in text_blame, text_blame)
    check("git_blame/git_log/git_diff_stat 어느 것도 저장소 설정의 외부 프로그램(textconv, 외부 diff, fsmonitor)을 실행하지 않는다 (--no-textconv, --no-ext-diff, core.fsmonitor=false)",
          not any(marks.iterdir()), str(sorted(m.name for m in marks.iterdir())))
    c4.close()

# --- 시간 제한: git 대신 5초 자는 프로그램을 끼워서 1초 제한으로 시험 ----------------------------------------
spec = importlib.util.spec_from_file_location("m13_server", SERVER)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
sleeper = [sys.executable, "-c", "import time; time.sleep(5)"]
import time  # noqa: E402
t0 = time.time()
try:
    mod.run_git([], timeout=1, git_cmd=sleeper)
    msg = "예외 없음"
except mod.ToolError as exc:
    msg = str(exc)
elapsed = time.time() - t0
check("시간 제한: 5초 걸리는 프로세스를 1초 제한으로 부르면 ToolError, 약 1초 만에 끝난다",
      "1초 안에 끝나지 않아" in msg and elapsed < 4, f"{msg} ({elapsed:.1f}s)")
src = SERVER.read_text(encoding="utf-8")
check("서버 소스에 shell=True가 없다 (인자 리스트로만 실행)", "shell=True" not in src and "os.system" not in src)

# --- opencode ------------------------------------------------------------------------------
with Sandbox("m13") as sb:
    status = sb.mcp_list(SANDBOX)
    check("opencode mcp list (sandbox/에서): repo connected", status.get("repo") == "connected", str(status))

    with FakeLLM(script=[("tool", "repo_git_log", {"path": "src/pricing.py", "max_count": 5}),
                         ("tool", "repo_git_blame", {"file": "src/pricing.py", "start_line": 14, "end_line": 16}),
                         "DONE"]) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
        proc = sb.opencode(["run", "-m", "fake/echo", "--auto", "go"], SANDBOX, timeout=120, extra_env=env)
        out = proc.stdout + proc.stderr
        requests = llm.main_requests()
        names = llm.tool_names(requests[0]) if requests else []
        results = []
        for request in requests:
            for message in request["messages"]:
                text = llm.message_text(message)
                if message.get("role") == "tool" and text not in results:
                    results.append(text)
    check("모델에게 제공되는 도구 이름: repo_git_log, repo_git_blame, repo_git_diff_stat",
          {"repo_git_log", "repo_git_blame", "repo_git_diff_stat"} <= set(names), str(names))
    check("가짜 모델이 git_log -> git_blame 순서로 부르고 두 결과가 모델에게 돌아간다",
          "⚙ repo_git_log" in out and "⚙ repo_git_blame" in out and len(results) == 2
          and "세금 계산을 반올림으로 수정" in results[0] and "dev-alpha 2026-03-06" in results[1], f"{results}\n{out[-400:]}")
    if model_enabled():
        out = sb.run_model("이 저장소에서 src/pricing.py의 tax 함수 반올림 수정은 누가 언제 했는지 알려줘.", SANDBOX)
        model_check("모델이 repo_git_* 도구를 호출했다", out, "repo_git_" in out)
        model_check("답에 dev-alpha가 나온다", out, "dev-alpha" in out)
finish()
