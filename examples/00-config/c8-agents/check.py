"""C8 검사: 에이전트 정의(.md 와 JSON)가 권한 규칙, 모델이 받는 도구 목록, 시스템 프롬프트로 이어지는지 확인한다.

가짜 모델(fake_llm.py)로 모델이 받은 요청을 직접 읽으므로 인터넷·계정이 필요 없다.
파일을 실제로 고치는 검사는 prepare.py 로 임시 폴더에 만든 git 저장소에서 한다. --model 이면 실제 모델로 reviewer 를 한 번 돌려 본다 (soft).
"""
import atexit
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import prepare  # noqa: E402
from lab import body_of, run_fake, system_text, user_texts  # noqa: E402
from octest import MODEL_UNAVAILABLE, RATE_LIMIT_RE, Sandbox, check, finish, model_check, model_enabled  # noqa: E402

_had_gitignore = (HERE / ".opencode" / ".gitignore").exists()


def _cleanup() -> None:
    """opencode 가 .opencode/ 안에 자동으로 만드는 파일(플러그인 패키지 설치 시도의 결과)을 지운다."""
    if not _had_gitignore:
        (HERE / ".opencode" / ".gitignore").unlink(missing_ok=True)
    for name in ("node_modules", "package.json", "package-lock.json", "bun.lock"):
        p = HERE / ".opencode" / name
        shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)


atexit.register(_cleanup)

reviewer_md = (HERE / ".opencode/agent/reviewer.md").read_text(encoding="utf-8")
researcher_md = (HERE / ".opencode/agent/researcher.md").read_text(encoding="utf-8")
cfg = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
ALL_TOOLS = ["bash", "edit", "glob", "grep", "read", "skill", "task", "todowrite", "webfetch", "write"]


def tools_of(request) -> list[str]:
    return sorted(t["function"]["name"] for t in request["tools"])


def rules(sb, cwd, agent, perms=("edit", "bash", "task")):
    proc = sb.opencode(["debug", "agent", agent], cwd, timeout=120, extra_env={"PWD": str(cwd)})
    data = json.loads(proc.stdout[proc.stdout.find("{"):])
    return data, [(r["permission"], r["pattern"], r["action"]) for r in data["permission"] if r["permission"] in perms]


def direct(sb, cwd, agent, tool, params) -> str:
    """모델 없이 그 에이전트의 권한 규칙으로 도구를 직접 실행. 'ran' | 'denied' | 'disabled' | 'error'."""
    proc = sb.opencode(["debug", "agent", agent, "--tool", tool, "--params", json.dumps(params)], cwd, timeout=120,
                       extra_env={"PWD": str(cwd)})
    text = proc.stdout + proc.stderr
    if "prevents you from using this specific tool call" in text:
        return "denied"
    if "is disabled for agent" in text:
        return "disabled"
    return "ran" if proc.returncode == 0 else "error"


def run_with_model(sb, args, cwd):
    """실제 모델로 opencode 를 실행. 한도 초과·시간 초과는 MODEL_UNAVAILABLE 로 돌려 model_check 가 '미확인'으로 보고하게 한다."""
    try:
        proc = sb.opencode(args, cwd, timeout=240, extra_env={"PWD": str(cwd)})
    except subprocess.TimeoutExpired:
        return MODEL_UNAVAILABLE + "\n<<timeout>>"
    out = proc.stdout + "\n" + proc.stderr
    return MODEL_UNAVAILABLE + "\n" + out if RATE_LIMIT_RE.search(out) else out


def make_copy(root: pathlib.Path, name: str, extra: dict[str, str] | None = None) -> pathlib.Path:
    """prepare.py 로 만든 git 저장소 사본 (파일을 고치는 검사용). extra 는 {상대경로: 내용} 으로 덮어쓰거나 추가한다."""
    dest = prepare.build(root / name)
    for rel, text in (extra or {}).items():
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return dest


# 1. 파일 자체
check("reviewer.md: mode primary, edit/bash/task 모두 deny",
      all(s in reviewer_md for s in ("mode: primary", "edit: deny", "bash: deny", "task: deny")))
check("researcher.md: mode subagent", "mode: subagent" in researcher_md)
check("opencode.json: agent.docs 를 JSON 으로 정의 (mode, prompt, 경로별 edit 규칙)",
      cfg["agent"]["docs"]["mode"] == "primary" and cfg["agent"]["docs"]["prompt"]
      and cfg["agent"]["docs"]["permission"]["edit"] == {"*": "deny", "docs/**": "allow"})
check("opencode.json 에 model 키 없음", "model" not in cfg)

with Sandbox("c8") as sb:
    # 2. 권한 규칙 (debug agent)
    rev, rev_rules = rules(sb, HERE, "reviewer")
    check("debug agent reviewer: mode primary, edit/bash/task 가 `*` deny",
          rev["mode"] == "primary" and rev_rules == [("edit", "*", "deny"), ("bash", "*", "deny"), ("task", "*", "deny")], str(rev_rules))
    check("debug agent reviewer: prompt 가 .md 본문과 같음", rev["prompt"].replace("\r\n", "\n").strip() == body_of(reviewer_md).strip())
    check("debug agent reviewer: tools 요약에서 edit·write·bash·task 는 false, read·grep·glob 은 true",
          all(rev["tools"][t] is False for t in ("edit", "write", "bash", "task")) and all(rev["tools"][t] for t in ("read", "grep", "glob")), str(rev["tools"]))
    docs, docs_rules = rules(sb, HERE, "docs")
    check("debug agent docs(JSON 정의): edit 규칙이 `* deny` 다음에 `docs/** allow` 순서 (마지막 일치가 이기므로 docs/ 만 허용)",
          docs_rules == [("edit", "*", "deny"), ("edit", "docs/**", "allow"), ("bash", "*", "deny"), ("task", "*", "deny")], str(docs_rules))
    check("debug agent docs: JSON 의 prompt 가 그대로 들어감, edit·write 는 true 로 남음",
          docs["prompt"] == cfg["agent"]["docs"]["prompt"] and docs["tools"]["edit"] and docs["tools"]["write"] and not docs["tools"]["bash"])
    res, res_rules = rules(sb, HERE, "researcher")
    check("debug agent researcher: mode subagent, edit/bash deny", res["mode"] == "subagent" and res_rules[:2] == [("edit", "*", "deny"), ("bash", "*", "deny")], str(res_rules))

    # md 와 JSON 은 같은 정의 방식: reviewer 를 JSON 으로 옮긴 사본이 같은 규칙·프롬프트를 낳는가
    body = body_of(reviewer_md).strip()
    json_twin = make_copy(sb.root, "twin", {"opencode.json": json.dumps({"agent": {"reviewer-json": {
        "mode": "primary", "description": "x", "prompt": body,
        "permission": {"edit": "deny", "bash": "deny", "task": "deny"}}}}, ensure_ascii=False)})
    twin, twin_rules = rules(sb, json_twin, "reviewer-json")
    check("같은 정의를 opencode.json 의 agent 키로 쓰면 권한 규칙·prompt·mode 가 .md 와 같음",
          twin_rules == rev_rules and twin["prompt"].strip() == body and twin["mode"] == "primary", str(twin_rules))

    # 3. 모델이 받는 도구 목록과 시스템 프롬프트
    _, llm, reqs = run_fake(sb, HERE, ["--agent", "build", "안녕"])
    build_tools = tools_of(reqs[0])
    check("기본 build 에이전트: 도구 목록에 bash, edit, write, task 모두 있음", build_tools == ALL_TOOLS, str(build_tools))
    proc, llm, reqs = run_fake(sb, HERE, ["--agent", "reviewer", "안녕"])
    check("--agent reviewer: 실행 헤더가 reviewer", "> reviewer" in proc.stderr, proc.stderr[:100])
    check("reviewer 가 받는 도구 목록에서 bash, edit, write, task 가 아예 빠짐 (deny 한 도구는 목록에 없음)",
          tools_of(reqs[0]) == ["glob", "grep", "read", "skill", "todowrite", "webfetch"], str(tools_of(reqs[0])))
    check("reviewer 의 .md 본문이 모델의 시스템 프롬프트에 들어감", "파일을 읽기만 하고 절대 고치지 않습니다" in system_text(llm, reqs[0]))
    proc, llm, reqs = run_fake(sb, HERE, ["--agent", "docs", "안녕"])
    check("docs 가 받는 도구 목록: edit·write 는 있고 bash·task 는 없음 (경로 규칙이 있어도 도구 자체는 목록에 남음)",
          tools_of(reqs[0]) == ["edit", "glob", "grep", "read", "skill", "todowrite", "webfetch", "write"], str(tools_of(reqs[0])))
    check("docs 의 JSON prompt 가 모델의 시스템 프롬프트에 들어감", "docs/ 아래의 마크다운만 고칩니다" in system_text(llm, reqs[0]))

    # 4. 목록에 없는 도구를 모델이 부르면
    work = make_copy(sb.root, "work")
    before = (work / "src/calc.py").read_text(encoding="utf-8")
    proc, llm, reqs = run_fake(sb, work, ["--agent", "reviewer", "고쳐 줘"], script=[
        ("tool", "edit", {"filePath": str(work / "src/calc.py"), "oldString": "a + b", "newString": "a - b"}), "DONE"])
    msgs = [llm.message_text(m) for m in reqs[1]["messages"] if m["role"] == "tool"] if len(reqs) > 1 else []
    check("reviewer 가 없는 도구 edit 를 부르면: 모델이 받는 결과는 \"Model tried to call unavailable tool 'edit'. Available tools: ...\"",
          any("Model tried to call unavailable tool 'edit'. Available tools: glob, grep, invalid, read, skill, todowrite, webfetch." in m for m in msgs), str(msgs))
    check("그래도 실행은 비정상 종료 없이 이어지고(종료 코드 0) 파일은 그대로", proc.returncode == 0 and (work / "src/calc.py").read_text(encoding="utf-8") == before)
    proc, llm, reqs = run_fake(sb, work, ["--agent", "reviewer", "실행해 줘"],
                               script=[("tool", "bash", {"command": "echo hi > hacked.txt", "description": "x"}), "DONE"])
    check("reviewer 가 bash 를 불러도 실행되지 않음 (hacked.txt 없음)", not (work / "hacked.txt").exists())

    # 5. 경로별 edit 권한 (docs): 모델 없이 직접, 그리고 run 전체 경로
    ok_edit = {"filePath": str(work / "docs/guide.md"), "oldString": "처음 쓰는 사람", "newString": "새로 온 사람"}
    check("docs: docs/guide.md 수정은 실행됨", direct(sb, work, "docs", "edit", ok_edit) == "ran")
    check("docs: 새 파일 docs/new.md 와 하위 폴더 docs/sub/x.md 쓰기도 실행됨",
          direct(sb, work, "docs", "write", {"filePath": str(work / "docs/new.md"), "content": "n"}) == "ran"
          and direct(sb, work, "docs", "write", {"filePath": str(work / "docs/sub/x.md"), "content": "n"}) == "ran")
    check("docs: src/calc.py 수정은 거부", direct(sb, work, "docs", "edit", {
        "filePath": str(work / "src/calc.py"), "oldString": "a + b", "newString": "a - b"}) == "denied")
    check("docs: 새 파일 src/new.py 쓰기도 거부", direct(sb, work, "docs", "write",
                                                   {"filePath": str(work / "src/new.py"), "content": "n"}) == "denied")
    check("reviewer: edit 는 도구가 꺼진 상태 (Tool edit is disabled for agent reviewer)",
          direct(sb, work, "reviewer", "edit", ok_edit) == "disabled")
    check("모델 없이 실행한 결과가 실제 파일에 반영됨: docs/guide.md 는 바뀌고 src/calc.py 는 그대로",
          "새로 온 사람" in (work / "docs/guide.md").read_text(encoding="utf-8")
          and (work / "src/calc.py").read_text(encoding="utf-8") == before)
    # 경로 규칙은 git 저장소 루트 기준이다: 같은 파일 구성이라도 .git 이 없으면 docs/guide.md 도 거부된다
    nogit = make_copy(sb.root, "nogit")
    shutil.rmtree(nogit / ".git", onerror=prepare._force_remove)
    check("docs/** 는 git 루트 기준 상대 경로: .git 이 없는 같은 폴더에서는 docs/guide.md 수정도 거부됨",
          direct(sb, nogit, "docs", "edit", {"filePath": str(nogit / "docs/guide.md"), "oldString": "처음 쓰는 사람",
                                              "newString": "x"}) == "denied")
    work2 = make_copy(sb.root, "work2")
    proc, llm, reqs = run_fake(sb, work2, ["--agent", "docs", "고쳐 줘"], script=[
        ("tool", "edit", {"filePath": str(work2 / "src/calc.py"), "oldString": "a + b", "newString": "a - b"}), "DONE"])
    msgs = [llm.message_text(m) for m in reqs[1]["messages"] if m["role"] == "tool"] if len(reqs) > 1 else []
    check("run 전체 경로: docs 에이전트가 src/calc.py 를 고치려 하면 거부 사유가 모델에게 돌아가고 파일은 그대로",
          any("prevents you from using this specific tool call" in m for m in msgs)
          and (work2 / "src/calc.py").read_text(encoding="utf-8") == before, str(msgs)[:300])
    proc, llm, reqs = run_fake(sb, work2, ["--agent", "docs", "고쳐 줘"], script=[
        ("tool", "edit", {"filePath": str(work2 / "docs/guide.md"), "oldString": "처음 쓰는 사람", "newString": "새로 온 사람"}), "DONE"])
    check("run 전체 경로: docs 에이전트가 docs/guide.md 를 고치면 묻지 않고(--auto 없이) 바로 반영됨",
          "새로 온 사람" in (work2 / "docs/guide.md").read_text(encoding="utf-8"), proc.stderr[-200:])

    # 6. mode: primary / subagent
    proc, llm, reqs = run_fake(sb, HERE, ["--agent", "researcher", "안녕"])
    check("--agent 로 subagent 를 고르면 경고 후 기본 build 로 실행됨 ('is a subagent, not a primary agent. Falling back to default agent')",
          'agent "researcher" is a subagent, not a primary agent. Falling back to default agent' in proc.stderr
          and "> build" in proc.stderr and tools_of(reqs[0]) == ALL_TOOLS, proc.stderr[:200])
    proc, llm, reqs = run_fake(sb, HERE, ["--agent", "nosuch", "안녕"])
    check("없는 에이전트 이름도 경고 후 build 로 실행됨 ('not found. Falling back to default agent', 종료 코드 0)",
          'agent "nosuch" not found. Falling back to default agent' in proc.stderr and proc.returncode == 0 and "> build" in proc.stderr, proc.stderr[:200])
    task_desc = next(t["function"]["description"] for t in reqs[0]["tools"] if t["function"]["name"] == "task")
    check("build 의 task 도구 설명에 subagent 목록이 있음: researcher(예제), explore, general. primary 인 reviewer·docs 는 없음",
          all(f"- {n}:" in task_desc for n in ("researcher", "explore", "general"))
          and "- reviewer:" not in task_desc and "- docs:" not in task_desc and "코드가 어디에 있는지" in task_desc)
    proc, llm, reqs = run_fake(sb, HERE, ["안녕"], script=[
        ("tool", "task", {"description": "조사", "prompt": "calc 가 어디 있나", "subagent_type": "researcher"}), "child done", "parent done"])
    check("build 가 task 로 researcher 를 부르면 하위 작업이 돌고 (3번 요청), 하위 작업은 researcher 의 프롬프트와 도구 목록(edit·bash·task 없음)을 받음",
          len(reqs) == 3 and "코드 조사원" in system_text(llm, reqs[1])
          and not {"edit", "bash", "task"} & set(tools_of(reqs[1])), str([tools_of(r) for r in reqs]))

    # 7. 함정: task 를 막지 않은 읽기 전용 에이전트는 하위 에이전트로 우회할 수 있다
    leaky_md = reviewer_md.replace("  task: deny\n", "")
    leaky = make_copy(sb.root, "leaky", {".opencode/agent/reviewer.md": leaky_md})
    proc, llm, reqs = run_fake(sb, leaky, ["--agent", "reviewer", "고쳐 줘"], script=[
        ("tool", "task", {"description": "수정", "prompt": "calc 고쳐", "subagent_type": "general"}),
        ("tool", "edit", {"filePath": str(leaky / "src/calc.py"), "oldString": "a + b", "newString": "a - b"}), "child done", "parent done"])
    check("task: deny 가 없는 reviewer 는 edit 이 목록에 없어도 general 하위 에이전트를 시켜 파일을 고칠 수 있음 (우회)",
          "a - b" in (leaky / "src/calc.py").read_text(encoding="utf-8") and "task" in tools_of(reqs[0]), proc.stderr[-300:])
    check("shipped reviewer 는 task 도구도 없어서 같은 우회가 불가능 (목록에 task 없음)", "task" not in tools_of(run_fake(sb, HERE, ["--agent", "reviewer", "x"])[2][0]))

    # 8. bash 를 통째로 끄지 않고 일부만 허용하면 도구는 목록에 남는다
    some = make_copy(sb.root, "some", {".opencode/agent/reviewer.md": reviewer_md.replace(
        "  bash: deny\n", "  bash:\n    \"*\": deny\n    \"git diff*\": allow\n")})
    proc, llm, reqs = run_fake(sb, some, ["--agent", "reviewer", "x"])
    check("bash 를 {'*': deny, 'git diff*': allow} 로 두면 bash 도구는 목록에 남음 (마지막 규칙이 `*` deny 일 때만 사라짐)",
          "bash" in tools_of(reqs[0]) and "edit" not in tools_of(reqs[0]), str(tools_of(reqs[0])))

    if model_enabled():
        mw = make_copy(sb.root, "model")
        out = run_with_model(sb, ["run", "-m", "opencode/big-pickle", "--agent", "reviewer",
                                  "src/calc.py 의 add 를 subtract 로 고쳐 줘"], mw)
        model_check("실제 모델: reviewer 에게 수정을 시켜도 파일이 바뀌지 않음", out,
                    (mw / "src/calc.py").read_text(encoding="utf-8") == before)

prep_root = pathlib.Path(tempfile.mkdtemp(prefix="c8-prep-"))
prep = prepare.build(prep_root / "s")
check("prepare.py 가 만든 sandbox 는 git 저장소이고 docs/guide.md, src/calc.py, .opencode/agent, opencode.json 이 있음",
      all((prep / rel).exists() for rel in (".git", "docs/guide.md", "src/calc.py", ".opencode/agent/reviewer.md", "opencode.json")))
shutil.rmtree(prep_root, onerror=prepare._force_remove)
finish()
