"""C5 검사: permission 규칙이 규칙 목록과 실제 도구 실행에서 어떻게 평가되는지 확인한다.

모델 없이 확인하는 방법: `opencode debug agent build --tool <도구> --params '<JS 객체>'` 는 모델을 거치지 않고
그 에이전트의 권한 규칙을 적용해 도구를 직접 실행한다. (이 호출에서 `ask` 는 자동 승인되므로 ask 와 allow 는 구분되지 않는다.)
--model 을 주면 실제 모델로 `opencode run --auto` 를 한 번 돌려 본다 (soft).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fake_llm import FakeLLM  # noqa: E402
from octest import MODEL_UNAVAILABLE, Sandbox, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SANDBOX = HERE / "sandbox"
HAD_SANDBOX = SANDBOX.exists()  # 사용자가 미리 prepare.py 를 돌렸다면 지우지 않는다
OUTSIDE = pathlib.Path(tempfile.gettempdir()) / "c5-outside"


def rules(sb: Sandbox, cwd: pathlib.Path, permission: str, agent: str = "build", content: dict | None = None):
    extra = {"OPENCODE_CONFIG_CONTENT": json.dumps(content)} if content else None
    proc = sb.opencode(["debug", "agent", agent], cwd, timeout=120, extra_env=extra)
    data = json.loads(proc.stdout[proc.stdout.find("{"):])
    return [(r["pattern"], r["action"]) for r in data["permission"] if r["permission"] == permission]


def try_tool(sb: Sandbox, cwd: pathlib.Path, tool: str, params: dict, agent: str = "build") -> str:
    """도구를 직접 실행하고 'ran' | 'denied' | 'disabled' | 'error' 중 하나를 돌려준다."""
    proc = sb.opencode(["debug", "agent", agent, "--tool", tool, "--params", json.dumps(params)], cwd, timeout=120)
    text = proc.stdout + proc.stderr
    if "prevents you from using this specific tool call" in text:
        return "denied"
    if "is disabled for agent" in text:
        return "disabled"
    return "ran" if proc.returncode == 0 else "error"


def bash(sb: Sandbox, cwd: pathlib.Path, command: str) -> str:
    return try_tool(sb, cwd, "bash", {"command": command, "description": "c5 check"})


def make_project(root: pathlib.Path, config: dict | None = None, git: bool = True) -> pathlib.Path:
    """실험용 임시 프로젝트. victim.txt 는 일부러 git 에 올리지 않는다 (git rm 이 실제로 지우지 못하게)."""
    proj = root / "proj"
    shutil.rmtree(proj, ignore_errors=True)
    proj.mkdir(parents=True)
    text = json.dumps(config) if config is not None else (HERE / "opencode.json").read_text(encoding="utf-8")
    (proj / "opencode.json").write_text(text, encoding="utf-8")
    (proj / "notes.txt").write_text("first line\n", encoding="utf-8")
    (proj / "victim.txt").write_text("victim\n", encoding="utf-8")
    if git:
        subprocess.run(["git", "init", "-q"], cwd=str(proj), check=True, capture_output=True, stdin=subprocess.DEVNULL)
    return proj


def ran(out: str, evidence: str) -> bool:
    """모델이 실제로 응답했고(타임아웃·한도 초과 아님) 해당 시도가 기록에 남았는가."""
    return not out.startswith(("<<timeout>>", MODEL_UNAVAILABLE)) and evidence in out


cfg = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
check("opencode.json: model 키 없음, permission 있음", "model" not in cfg and "permission" in cfg)
check("opencode.json: bash 규칙 순서 = *, git status*, rm * (넓은 것이 먼저)",
      list(cfg["permission"]["bash"]) == ["*", "git status*", "rm *"], str(cfg["permission"]))

try:
    proc = subprocess.run([sys.executable, str(HERE / "prepare.py")], capture_output=True, timeout=120,
                          env={**os.environ, "PYTHONUTF8": "1"}, stdin=subprocess.DEVNULL)
    check("prepare.py 정상 종료", proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace"))
    check("prepare.py: sandbox 에 git 저장소, opencode.json, victim.txt",
          (SANDBOX / ".git").exists() and (SANDBOX / "opencode.json").exists() and (SANDBOX / "victim.txt").exists())
    check("prepare.py: sandbox/opencode.json == 예제 opencode.json",
          (SANDBOX / "opencode.json").read_text(encoding="utf-8") == (HERE / "opencode.json").read_text(encoding="utf-8"))

    with Sandbox("c5") as sb:
        # 1. 규칙 목록 (debug agent build 가 평가에 쓰는 평탄한 목록)
        bash_rules = rules(sb, SANDBOX, "bash")
        check("bash 규칙이 설정 순서대로 목록에 들어감",
              bash_rules == [("*", "ask"), ("git status*", "allow"), ("rm *", "deny")], str(bash_rules))
        edit = rules(sb, SANDBOX, "edit")
        check("edit: * -> ask", edit[-1] == ("*", "ask"), str(edit))
        ext = rules(sb, SANDBOX, "external_directory")
        check("external_directory: 기본 ask 뒤에 내 설정 deny 가 옴 (마지막 * 규칙이 deny)",
              ("*", "ask") in ext and [r for r in ext if r[0] == "*"][-1] == ("*", "deny"), str(ext))
        base = sb.opencode(["debug", "agent", "build"], SANDBOX, timeout=120)
        head = json.loads(base.stdout[base.stdout.find("{"):])["permission"][0]
        check("내장 기본 규칙 `* allow` 가 맨 앞에 있고 내 규칙은 그 뒤에 쌓임",
              head == {"permission": "*", "action": "allow", "pattern": "*"}, str(head))

        plain = sb.root / "plain"
        plain.mkdir()
        wrong = rules(sb, plain, "bash", content={"permission": {"bash": {"git status*": "allow", "*": "ask"}}})
        check("뒤집힌 순서: 목록도 git status* 가 먼저, * 가 마지막", wrong == [("git status*", "allow"), ("*", "ask")], str(wrong))

        team = sb.root / "team.json"
        team.write_text(json.dumps({"permission": {"bash": {"git status*": "allow"}}}), encoding="utf-8")
        (plain / "opencode.json").write_text(json.dumps({"permission": {"bash": {"*": "ask"}}}), encoding="utf-8")
        proc = sb.opencode(["debug", "agent", "build"], plain, timeout=120, extra_env={"OPENCODE_CONFIG": str(team)})
        data = json.loads(proc.stdout[proc.stdout.find("{"):])
        layered = [(r["pattern"], r["action"]) for r in data["permission"] if r["permission"] == "bash"]
        check("층이 나뉘어도 목록은 '낮은 층 규칙 -> 높은 층 규칙' 순서 (높은 층의 * 가 마지막)",
              layered == [("git status*", "allow"), ("*", "ask")], str(layered))
        (plain / "opencode.json").unlink()

        # 2. 모델 없이 도구를 직접 실행해서 allow / deny 와 평가 순서를 확인
        OUTSIDE.mkdir(exist_ok=True)
        (OUTSIDE / "note.txt").write_text("outside-secret-777\n", encoding="utf-8")
        proj = make_project(sb.root)
        check("allow: `git status` 는 규칙 `git status*` 로 실행됨", bash(sb, proj, "git status") == "ran")
        check("ask: `echo hello` 는 (자동 승인되어) 실행됨 -- ask 와 allow 는 이 호출에서 구분되지 않음",
              bash(sb, proj, "echo hello") == "ran")
        check("deny: `rm victim.txt` 거부", bash(sb, proj, "rm victim.txt") == "denied")
        check("deny: `rm -f victim.txt` 도 같은 패턴(`rm *`)에 걸려 거부", bash(sb, proj, "rm -f victim.txt") == "denied")
        check("deny: 복합 명령 `echo x && rm victim.txt` 도 거부 (명령을 나눠서 각각 평가)",
              bash(sb, proj, "echo x && rm victim.txt") == "denied")
        check("deny: `git status && rm victim.txt` 도 거부 (앞이 allow 여도 rm 부분이 deny)",
              bash(sb, proj, "git status && rm victim.txt") == "denied")
        check("패턴의 한계: `git rm -f victim.txt` 는 `rm *` 에 걸리지 않음 (거부 아님)",
              bash(sb, proj, "git rm -f victim.txt") == "ran")
        check("deny 된 명령이 실제로 아무것도 지우지 못함", (proj / "victim.txt").exists())
        check("external_directory deny: 프로젝트 밖 파일 read 거부",
              try_tool(sb, proj, "read", {"filePath": str(OUTSIDE / "note.txt")}) == "denied")
        check("프로젝트 안 파일 read 는 실행됨", try_tool(sb, proj, "read", {"filePath": str(proj / "notes.txt")}) == "ran")

        # 3. 평가 순서: 마지막으로 맞는 규칙이 이긴다
        first_allow = make_project(sb.root / "o1", {"permission": {"bash": {"echo order*": "allow", "*": "deny"}}})
        check("순서 [allow, * deny]: 마지막 `*` deny 가 이겨서 bash 도구 자체가 비활성화됨",
              bash(sb, first_allow, "echo order-test") == "disabled")
        last_allow = make_project(sb.root / "o2", {"permission": {"bash": {"*": "deny", "echo order*": "allow"}}})
        check("순서 [* deny, allow]: `echo order-test` 는 실행됨", bash(sb, last_allow, "echo order-test") == "ran")
        check("순서 [* deny, allow]: 그 밖의 명령 `echo other` 는 거부", bash(sb, last_allow, "echo other") == "denied")

        # 4. edit: deny 는 도구를 끄고, plan 에이전트는 기본 deny 인데 내 `edit: ask` 가 그 위에 쌓인다
        edit_deny = make_project(sb.root / "e1", {"permission": {"edit": "deny"}})
        patch = {"filePath": "", "oldString": "first line", "newString": "second line"}
        check("edit: deny 이면 edit 도구가 비활성화됨",
              try_tool(sb, edit_deny, "edit", {**patch, "filePath": str(edit_deny / "notes.txt")}) == "disabled")
        no_cfg = make_project(sb.root / "e2", {})
        check("plan 에이전트는 기본값에서 edit 거부",
              try_tool(sb, no_cfg, "edit", {**patch, "filePath": str(no_cfg / "notes.txt")}, agent="plan") == "denied")
        edit_ask = make_project(sb.root / "e3", {"permission": {"edit": "ask"}})
        check("내 `edit: ask` 가 있으면 plan 에이전트의 기본 deny 가 사라지고 (ask 로) 실행됨",
              try_tool(sb, edit_ask, "edit", {**patch, "filePath": str(edit_ask / "notes.txt")}, agent="plan") == "ran")

        # 5. `opencode run` 전체 경로 (가짜 모델이 도구 호출을 스크립트대로 흉내 냄 -- 모델 없이, 결과가 항상 같음)
        def run_call(project, tool, args, auto, extra_content=None):
            with FakeLLM(script=[("tool", tool, args), "DONE"]) as llm:
                cmd = ["run", "-m", "fake/echo"] + (["--auto"] if auto else []) + ["go"]
                res = sb.opencode(cmd, project, timeout=180,
                                  extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config()), "PWD": str(project)})
                followup = [llm.message_text(m) for r in llm.main_requests() for m in r["messages"] if m.get("role") == "tool"]
                names = FakeLLM.tool_names(llm.main_requests()[0]) if llm.main_requests() else []
            return res.stdout + res.stderr, followup, names

        run_proj = make_project(sb.root / "r1")
        marker = {"command": "echo ask-demo > ask-marker.txt", "description": "c5 check"}
        text, _, _ = run_call(run_proj, "bash", marker, auto=False)
        check("ask + --auto 없음: 승인할 사람이 없어 'auto-rejecting' 으로 거절되고 실행 안 됨",
              "auto-rejecting" in text and not (run_proj / "ask-marker.txt").exists(), text[-300:])
        text, _, _ = run_call(run_proj, "bash", marker, auto=True)
        check("ask + --auto: 자동 승인되어 실행됨 (ask-marker.txt 생성)", (run_proj / "ask-marker.txt").exists(), text[-300:])
        text, followup, _ = run_call(run_proj, "bash", {"command": "git status", "description": "c5 check"}, auto=False)
        check("allow: --auto 없이도 `git status` 가 바로 실행되어 결과가 모델에게 돌아감",
              any("On branch" in f for f in followup) and "auto-rejecting" not in text, str(followup)[:300])
        text, followup, _ = run_call(run_proj, "bash", {"command": "rm victim.txt", "description": "c5 check"}, auto=True)
        check("deny + --auto: `rm *` 는 --auto 로도 막혀 victim.txt 가 남고 거부 사유가 모델에게 돌아감",
              (run_proj / "victim.txt").exists() and any("prevents you" in f for f in followup), str(followup)[:300])
        text, followup, _ = run_call(run_proj, "read", {"filePath": str(OUTSIDE / "note.txt")}, auto=True)
        check("external_directory deny + --auto: 프로젝트 밖 파일 내용이 모델에게 가지 않음",
              followup and not any("outside-secret-777" in f for f in followup), str(followup)[:300])
        text, _, _ = run_call(run_proj, "edit", {"filePath": str(run_proj / "notes.txt"), "oldString": "first line", "newString": "second line"}, auto=False)
        check("edit ask + --auto 없음: 거절되어 파일이 바뀌지 않음",
              "auto-rejecting" in text and (run_proj / "notes.txt").read_text(encoding="utf-8").startswith("first line"), text[-300:])
        text, _, _ = run_call(run_proj, "edit", {"filePath": str(run_proj / "notes.txt"), "oldString": "first line", "newString": "second line"}, auto=True)
        check("edit ask + --auto: 승인되어 파일이 바뀜", (run_proj / "notes.txt").read_text(encoding="utf-8").startswith("second line"), text[-300:])

        # 순서: [git status* allow, * ask] 로 뒤집으면 git status 도 ask 가 되어 --auto 없이는 거절된다
        wrong_proj = make_project(sb.root / "r2", {"permission": {"bash": {"git status*": "allow", "*": "ask"}}})
        text, followup, _ = run_call(wrong_proj, "bash", {"command": "git status", "description": "c5 check"}, auto=False)
        check("순서 [git status* allow, * ask]: 마지막 `*` ask 가 이겨서 git status 도 거절됨 (마지막 일치가 이김)",
              "auto-rejecting" in text and not any("On branch" in f for f in followup), text[-300:])
        # 도구 목록: bash 가 통째로 deny 면 모델이 받는 도구 목록에서 사라진다
        off_proj = make_project(sb.root / "r3", {"permission": {"bash": {"echo order*": "allow", "*": "deny"}}})
        _, _, names = run_call(off_proj, "read", {"filePath": str(off_proj / "notes.txt")}, auto=True)
        check("마지막 `*` deny 이면 모델이 받는 도구 목록에서 bash 가 사라짐", names and "bash" not in names, str(names))
        _, _, names = run_call(run_proj, "read", {"filePath": str(run_proj / "notes.txt")}, auto=True)
        check("기본 설정(ask/allow 혼합)에서는 bash 가 도구 목록에 있음", "bash" in names, str(names))

        # 6. 실제 모델 (soft, 한 번)
        if model_enabled():
            proj = make_project(sb.root / "m1")
            out = sb.run_model(
                "bash 도구로 다음 두 명령을 정확히, 이 순서로 하나씩 실행하세요. 거부되면 사유만 알려 주세요.\n"
                "(1) echo ask-demo > ask-marker.txt\n(2) rm victim.txt", proj, auto=True)
            model_check("실제 모델 + --auto: ask 명령은 실행되고 `rm *` 는 막힘", out,
                        ran(out, "victim.txt") and (proj / "ask-marker.txt").exists() and (proj / "victim.txt").exists())
finally:
    if not HAD_SANDBOX:
        shutil.rmtree(SANDBOX, ignore_errors=True)
    shutil.rmtree(OUTSIDE, ignore_errors=True)
finish()
