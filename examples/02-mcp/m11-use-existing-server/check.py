"""M11 check: 남이 만든 서버(파일 서버 npx, 시간 서버 uvx)를 "살펴보고 -> 제한해서" 쓰는 흐름을 확인한다.

npm/PyPI 레지스트리(또는 미러)가 필요한 부분은 3초 안에 닿지 않으면 WARN 으로 건너뛴다.
서버 실행은 예제 폴더의 sandbox/ (prepare.py 가 만듦)만 대상으로 하고, 쓰기 시험은 임시 폴더에서만 한다.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402
import show_tools  # noqa: E402

WRITE_TOOLS = ["write_file", "append_file", "edit_file", "create_directory", "move_file", "copy_file"]
READ_TOOLS = ["read_file", "read_text_file", "read_media_file", "read_multiple_files", "list_directory",
              "list_directory_with_sizes", "directory_tree", "search_files", "get_file_info", "list_allowed_directories"]


class NetSkip(Exception):
    """레지스트리 확인은 통과했지만 서버를 받는 도중 네트워크가 끊겼다 — 남은 검사를 WARN 으로 건너뛴다."""


def npm_registry_reachable():
    return show_tools.npm_registry_reachable()


def index_reachable():
    """uv 가 실제로 쓰는 인덱스 확인 (UV_DEFAULT_INDEX / UV_INDEX_URL / uv.toml). pip 설정은 uv 가 읽지 않으므로 보지 않는다."""
    return show_tools.uv_index_reachable()


def listed(command):
    """show_tools.list_server_tools 를 부르되, 네트워크 문제로 시작하지 못했으면 NetSkip."""
    tools, err = show_tools.list_server_tools(command)
    if err and show_tools.network_failure(err):
        raise NetSkip(err)
    return tools, err


def scripted_call(sb, cwd, tool, args):
    """가짜 모델이 `tool`을 `args`로 부르게 한다. 반환: (출력, 모델에게 제공된 도구 이름들, 모델에게 돌아간 도구 결과들)."""
    with FakeLLM(script=[("tool", tool, args), "DONE"]) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
        proc = sb.opencode(["run", "-m", "fake/echo", "--auto", "go"], cwd, timeout=180, extra_env=env)
        requests = llm.main_requests()
        names = [t["function"]["name"] for t in requests[0]["tools"]] if requests else []
        results = []
        for request in requests:
            for message in request["messages"]:
                text = llm.message_text(message)
                if message.get("role") == "tool" and text not in results:
                    results.append(text)
    return proc.stdout + proc.stderr, sorted(names), results


def tool_seen(transcript, name):
    return any(name in line for line in transcript.splitlines() if line.lstrip().startswith(("⚙", "✗", "→")))


class Raw:
    """서버를 직접 띄워 JSON-RPC 를 주고받는 최소 클라이언트."""

    def __init__(self, command, cwd=HERE):
        self.proc = subprocess.Popen([shutil.which(command[0]) or command[0], *command[1:]], cwd=str(cwd), stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # Windows의 npx는 npx.cmd라 전체 경로가 필요
        self.n = 0

    def rpc(self, method, params=None):
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method, **({"params": params} if params is not None else {})}
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False).encode("utf-8") + b"\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline().decode("utf-8")
            if not line:
                err = self.proc.stderr.read().decode("utf-8", "replace")  # npm 은 원인을 앞쪽 줄에 쓴다: 전체로 판정하고 끝부분만 보여 준다
                raise (NetSkip if show_tools.network_failure(err) else RuntimeError)(err[-300:])
            msg = json.loads(line)
            if msg.get("id") == self.n:
                return msg

    def start(self):
        self.rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "check", "version": "0"}})
        self.proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        self.proc.stdin.flush()
        return self

    def call(self, name, arguments):
        return self.rpc("tools/call", {"name": name, "arguments": arguments})["result"]

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc.stderr.close()
        self.proc.stdout.close()


# --- 설정 파일 (네트워크 없이) ------------------------------------------------------------------
config = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
files_cmd = config["mcp"]["files"]["command"]
clock_cmd = config["mcp"]["clock"]["command"]
check("opencode.json: 파일 서버 버전을 @2.3.0 으로 고정하고 허용 폴더 인자는 sandbox", files_cmd[:2] == ["npx", "-y"]
      and files_cmd[2] == "@modelcontextprotocol/server-filesystem@2.3.0" and files_cmd[-1] == "sandbox", str(files_cmd))
check("opencode.json: --confine-roots 가 있다 (없으면 opencode 의 프로젝트 폴더가 허용 폴더를 대신한다 — 아래 검사 참고)", "--confine-roots" in files_cmd)
check("opencode.json: 시간 서버(uvx)도 버전을 == 로 고정한다", clock_cmd[0] == "uvx" and re.fullmatch(r"mcp-server-time==\d+\.\d+\.\d+", clock_cmd[1]) is not None, str(clock_cmd))
deny = {k for k, v in config["permission"].items() if v == "deny"}
check("opencode.json: 쓰기 도구 6개(files_write_file 등)를 permission deny 로 막는다 (M8 방식)",
      deny == {f"files_{t}" for t in WRITE_TOOLS} and "model" not in config, str(deny))
check("이 예제의 .gitignore 가 sandbox/ 를 거른다", "sandbox/" in (HERE / ".gitignore").read_text(encoding="utf-8").split())

proc = subprocess.run([sys.executable, str(HERE / "prepare.py")], cwd=str(HERE), capture_output=True, timeout=60)
sandbox_dir = HERE / "sandbox"
check("prepare.py: sandbox/ 에 연습 파일 4개를 만든다 (인터넷 불필요)", proc.returncode == 0 and (sandbox_dir / "notes" / "todo.txt").is_file()
      and (sandbox_dir / "data" / "members.csv").is_file() and (sandbox_dir / "README.txt").is_file() and (sandbox_dir / "notes" / "meeting-2026-11-10.md").is_file())

npm_ok, npm_url = npm_registry_reachable()
idx_ok, idx_url = index_reachable()
print(f"[info] npm 레지스트리 {npm_url} -> {'3초 안에 응답' if npm_ok else '응답 없음/도구 없음'}; uv 인덱스 {idx_url} -> {'3초 안에 응답' if idx_ok else '응답 없음/도구 없음'}")

with Sandbox("m11") as sb:
    # --- 파일 서버 (npx) -----------------------------------------------------------------------
    if not npm_ok:
        check("WARN: node/npx 가 없거나 npm 레지스트리에 닿지 않아 파일 서버 검사를 건너뜁니다 (패키지 미러가 필요: `npm config set registry <미러 주소>`)", False, soft=True)
    else:
        try:
            # 1) 서버를 직접: 내놓는 도구, 읽기, 허용 폴더 밖 거절
            tools, err = listed(files_cmd)
            names = [t["name"] for t in tools]
            check("tools/list: 도구 16개 (읽기 10 + 쓰기 6) — 서버는 쓰기 도구도 기본으로 내놓는다", sorted(names) == sorted(READ_TOOLS + WRITE_TOOLS), err or str(names))
            flags = {t["name"]: (t.get("annotations") or {}).get("readOnlyHint") for t in tools}
            check("서버가 붙인 readOnlyHint 로 읽기/쓰기 구분이 된다 (쓰기 6개만 readOnlyHint:false)",
                  {n for n, v in flags.items() if v is False} == set(WRITE_TOOLS) and all(flags[n] is True for n in READ_TOOLS), str(flags))
            total = sum(show_tools.size({"name": t["name"], "description": t.get("description", ""), "parameters": t.get("inputSchema", {})}) for t in tools)
            print(f"[info] 파일 서버: 도구 {len(tools)}개, 이름+설명+스키마 {total}자 (≈ {total // 4} 토큰)")
            raw = Raw(files_cmd).start()
            got = raw.call("read_text_file", {"path": "notes/todo.txt"})
            check("읽기 도구: 허용 폴더(sandbox) 안의 파일을 읽는다 (상대 경로는 허용 폴더 기준)", "배포 체크리스트" in got["content"][0]["text"] and not got.get("isError"), str(got))
            got = raw.call("read_text_file", {"path": str(HERE / "prepare.py")})
            check("허용 폴더 밖의 파일(예제 폴더의 prepare.py)은 서버가 'Access denied' 로 거절한다 (isError:true)",
                  got.get("isError") is True and "Access denied" in got["content"][0]["text"], str(got))
            got = raw.call("read_text_file", {"path": "../prepare.py"})
            check("'../' 로 빠져나가는 경로도 거절한다", got.get("isError") is True and "Access denied" in got["content"][0]["text"], str(got))
            got = raw.call("list_allowed_directories", {})
            check("list_allowed_directories 가 sandbox 의 절대 경로를 알려 준다 (상대 인자 'sandbox' 는 서버의 작업 폴더 기준)",
                  pathlib.Path(got["content"][0]["text"].splitlines()[-1]).resolve() == sandbox_dir.resolve(), str(got))
            raw.close()

            # 2) 서버 쪽 --read-only: 쓰기 도구를 서버가 아예 등록하지 않는다
            ro_tools, err = listed(files_cmd[:-1] + ["--read-only", "sandbox"])
            check("(보강) 서버 옵션 --read-only: 쓰기 도구 6개가 tools/list 에서 사라진다 (읽기 10개만)", sorted(t["name"] for t in ro_tools) == sorted(READ_TOOLS), err or str([t["name"] for t in ro_tools]))

            # 3) opencode 연결과 모델에게 가는 도구
            status = sb.mcp_list(HERE)
            check("opencode mcp list: files connected", status.get("files") == "connected", str(status))
            out, names, results = scripted_call(sb, HERE, "files_list_allowed_directories", {})
            check("opencode 로 붙으면 허용 폴더가 여전히 sandbox 다 (--confine-roots 덕분)",
                  any(pathlib.Path(r.splitlines()[-1]).resolve() == sandbox_dir.resolve() for r in results if r.startswith("Allowed")), str(results))
            files_names = {n for n in names if n.startswith("files_")}
            check("모델에게 가는 files_* 는 읽기 도구 10개뿐 — 쓰기 6개는 permission deny 로 빠진다",
                  files_names == {f"files_{t}" for t in READ_TOOLS}, str(sorted(files_names)))
            out, names, results = scripted_call(sb, HERE, "files_read_text_file", {"path": "notes/todo.txt"})
            check("(가짜 모델) files_read_text_file 이 sandbox 파일을 읽어 모델에게 돌려준다", any("배포 체크리스트" in r for r in results) and "⚙ files_read_text_file" in out, f"{results} {out[-200:]}")
            out, names, results = scripted_call(sb, HERE, "files_read_text_file", {"path": str(HERE / "prepare.py")})
            check("(가짜 모델) 허용 폴더 밖 경로는 opencode 를 거쳐도 Access denied 가 모델에게 돌아간다", any("Access denied" in r for r in results), str(results))
            out, names, results = scripted_call(sb, HERE, "files_write_file", {"path": "hacked.txt", "content": "x"})
            check("(가짜 모델) 막은 files_write_file 을 억지로 부르면 'unavailable tool' 오류이고 파일은 생기지 않는다",
                  any("unavailable tool 'files_write_file'" in r for r in results) and not (sandbox_dir / "hacked.txt").exists(), str(results))

            # 4) 제한을 풀거나 옵션을 빼면 어떻게 되는지 (임시 폴더에서만)
            tmp = pathlib.Path(tempfile.mkdtemp(prefix="m11-variant-"))
            try:
                shutil.copytree(sandbox_dir, tmp / "sandbox")
                nolimit = json.loads(json.dumps(config))
                nolimit.pop("permission")
                nolimit["mcp"].pop("clock")
                (tmp / "opencode.json").write_text(json.dumps(nolimit), encoding="utf-8")
                out, names, results = scripted_call(sb, tmp, "files_write_file", {"path": "made-by-model.txt", "content": "hello"})
                check("(제한 없음) permission 규칙을 빼면 files_* 16개가 모두 전달되고 모델이 sandbox 에 파일을 만들 수 있다",
                      len({n for n in names if n.startswith("files_")}) == 16 and (tmp / "sandbox" / "made-by-model.txt").read_text(encoding="utf-8") == "hello",
                      f"{[n for n in names if n.startswith('files_')]} {results}")
                noconfine = json.loads(json.dumps(nolimit))
                noconfine["mcp"]["files"]["command"] = [a for a in files_cmd if a != "--confine-roots"]
                (tmp / "opencode.json").write_text(json.dumps(noconfine), encoding="utf-8")
                out, names, results = scripted_call(sb, tmp, "files_list_allowed_directories", {})
                allowed = [r.splitlines()[-1] for r in results if r.startswith("Allowed")]
                check("(--confine-roots 없음) opencode 의 프로젝트 폴더가 허용 폴더가 되어 인자 'sandbox' 를 대신한다 (허용 폴더가 sandbox 가 아니라 프로젝트 폴더)",
                      len(allowed) == 1 and pathlib.Path(allowed[0]).resolve() == tmp.resolve(), str(results))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        except NetSkip as exc:
            check("WARN: 레지스트리 확인은 통과했지만 파일 서버를 받는 도중 네트워크가 끊겨 파일 서버 검사를 건너뜁니다 (패키지 미러 필요)", False, str(exc).strip()[-300:], soft=True)

    # --- 시간 서버 (uvx) ------------------------------------------------------------------------
    if not idx_ok:
        check("WARN: uv 가 없거나 패키지 인덱스(PyPI/미러)에 닿지 않아 uvx 시간 서버 검사를 건너뜁니다 (미러가 필요: 환경 변수 UV_DEFAULT_INDEX=<미러 주소> 또는 uv.toml 의 index-url. pip.conf·PIP_INDEX_URL 은 uv 가 읽지 않습니다)", False, soft=True)
    else:
        try:
            tools, err = listed(clock_cmd)
            check("uvx mcp-server-time: 도구 3개 (get_current_time, convert_time, get_time_ago), 모두 readOnlyHint:true",
                  sorted(t["name"] for t in tools) == ["convert_time", "get_current_time", "get_time_ago"]
                  and all((t.get("annotations") or {}).get("readOnlyHint") is True for t in tools), err or str([t["name"] for t in tools]))
            total = sum(show_tools.size({"name": t["name"], "description": t.get("description", ""), "parameters": t.get("inputSchema", {})}) for t in tools)
            print(f"[info] 시간 서버: 도구 {len(tools)}개, 이름+설명+스키마 {total}자 (≈ {total // 4} 토큰)")
            raw = Raw(clock_cmd).start()
            got = raw.call("get_current_time", {"timezone": "Asia/Seoul"})
            check("get_current_time(Asia/Seoul) 호출 성공", '"timezone": "Asia/Seoul"' in got["content"][0]["text"] and not got.get("isError"), str(got))
            got = raw.call("get_current_time", {"timezone": "Nope/Zone"})
            check("없는 시간대는 isError:true 결과", got.get("isError") is True, str(got))
            raw.close()
            status = sb.mcp_list(HERE)
            check("opencode mcp list: clock connected", status.get("clock") == "connected", str(status))
            out, names, results = scripted_call(sb, HERE, "clock_get_current_time", {"timezone": "Asia/Seoul"})
            check("(가짜 모델) clock_get_current_time 이 호출되어 결과가 모델에게 돌아간다", any('"timezone": "Asia/Seoul"' in r for r in results), f"{results} {out[-200:]}")
        except NetSkip as exc:
            check("WARN: 인덱스 확인은 통과했지만 시간 서버를 받는 도중 네트워크가 끊겨 uvx 시간 서버 검사를 건너뜁니다 (미러 필요: UV_DEFAULT_INDEX)", False, str(exc).strip()[-300:], soft=True)

    if model_enabled() and npm_ok:
        out = sb.run_model("files 서버로 notes/todo.txt 를 읽어서 할 일이 몇 개인지 알려줘.", HERE, extra_env={"PWD": str(HERE)})
        model_check("모델이 files_read_text_file 을 호출했다", out, tool_seen(out, "files_"))
        model_check("답변에 할 일 3개가 반영됐다", out, "3" in out or "세" in out)
        print(out[-500:])
finish()
