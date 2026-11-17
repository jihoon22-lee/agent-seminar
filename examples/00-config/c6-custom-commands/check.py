"""C6 검사: 커스텀 명령 두 가지 정의 방식, $ARGUMENTS/$1 동작, frontmatter 키, 명령과 스킬의 차이.

모두 가짜 모델(fake_llm.py)로 모델이 받은 요청을 직접 읽어 확인하므로 인터넷·계정이 필요 없다.
--model 을 주면 실제 모델로 명령을 한 번 실행해 본다 (soft).
"""
import atexit
import json
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from lab import body_of, run_fake, skill_entry, system_text, user_texts  # noqa: E402
from octest import MODEL_UNAVAILABLE, RATE_LIMIT_RE, Sandbox, check, finish, model_check, model_enabled  # noqa: E402

def _cleanup_opencode_dir(had_gitignore: bool) -> None:
    """opencode 가 .opencode/ 안에 자동으로 만드는 파일(플러그인 패키지 설치 시도의 결과)을 지운다."""
    if not had_gitignore:
        (HERE / ".opencode" / ".gitignore").unlink(missing_ok=True)
    for name in ("node_modules", "package.json", "package-lock.json", "bun.lock"):
        p = HERE / ".opencode" / name
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)


_had_gitignore = (HERE / ".opencode" / ".gitignore").exists()
atexit.register(_cleanup_opencode_dir, _had_gitignore)
CMD = HERE / ".opencode/command"
finish_md = (CMD / "finish.md").read_text(encoding="utf-8")
review_md = (CMD / "review.md").read_text(encoding="utf-8")
skill_md = (HERE / ".opencode/skills/finish-plan/SKILL.md").read_text(encoding="utf-8")
cfg = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
MARK = "PR 단위로 나눠서"


def first_user(llm, reqs) -> str:
    return user_texts(llm, reqs[0])[0] if reqs else ""


def run_with_model(sb, args, cwd):
    """실제 모델로 opencode 를 실행. 한도 초과·시간 초과는 MODEL_UNAVAILABLE 로 돌려 model_check 가 '미확인'으로 보고하게 한다."""
    try:
        proc = sb.opencode(args, cwd, timeout=240, extra_env={"PWD": str(cwd)})
    except subprocess.TimeoutExpired:
        return MODEL_UNAVAILABLE + "\n<<timeout>>"
    out = proc.stdout + "\n" + proc.stderr
    return MODEL_UNAVAILABLE + "\n" + out if RATE_LIMIT_RE.search(out) else out


def make_project(root: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return root


# 1. 파일 자체
check("두 가지 정의 방식이 모두 있음: .opencode/command/*.md 와 opencode.json 의 command 키",
      finish_md.startswith("---\n") and review_md.startswith("---\n") and "status" in cfg.get("command", {}))
check("review.md 는 $ARGUMENTS 를 쓰고 finish.md 는 쓰지 않음", "$ARGUMENTS" in review_md and "$ARGUMENTS" not in finish_md)
check("스킬 본문 = /finish 명령 본문 (같은 지시문을 두 방식으로 둔 비교용)",
      body_of(skill_md).strip() == body_of(finish_md).strip())
check("opencode.json 에 model 키 없음 (예제 설정이 사용자 모델 선택을 건드리지 않음)", "model" not in cfg)

with Sandbox("c6") as sb:
    # 2. opencode 가 읽은 명령 목록
    conf = sb.debug_config(HERE, extra_env={"PWD": str(HERE)})
    commands = conf.get("command", {})
    check("debug config: .md 로 정의한 finish, review 와 JSON 으로 정의한 status 가 모두 command 에 있음",
          {"finish", "review", "status"} <= set(commands), str(sorted(commands)))
    check("debug config: .md 의 본문이 template 이 되고 description 이 frontmatter 에서 옴",
          commands["finish"]["template"].replace("\r\n", "\n").strip() == body_of(finish_md).strip()
          and commands["finish"]["description"] == "계획대로 끝까지 진행 (PR 단위, 검사 통과 후 병합)", str(commands.get("finish")))
    check("debug config: JSON 정의의 agent 가 그대로 남음", commands["status"].get("agent") == "plan", str(commands["status"]))

    # 3. 명령 vs 스킬: 아무것도 부르지 않은 요청
    _, llm, reqs = run_fake(sb, HERE, ["안녕"])
    check("가짜 모델이 도구 목록이 붙은 요청을 받음", len(reqs) == 1, str(len(reqs)))
    whole = json.dumps(reqs[0], ensure_ascii=False)
    sysmsg = system_text(llm, reqs[0])
    entry = skill_entry(sysmsg, "finish-plan")
    check("스킬: 이름과 description 이 시스템 프롬프트에 있음 (부르지 않아도)",
          "<name>finish-plan</name>" in entry and "<description>계획대로 끝까지 진행할 때의 규칙" in entry, entry[:200])
    check("스킬: 본문은 요청 어디에도 없음", MARK not in whole)
    check("명령: 부르지 않으면 이름·description·본문 어느 것도 요청에 없음 (finish, review, status 모두)",
          not any(s in whole for s in (MARK, "계획대로 끝까지 진행 (PR", "지정한 대상을 리뷰", "다음 대상을 코드 리뷰", "저장소 상태를 세 줄로")))
    name_desc = "".join(re.findall(r"<(?:name|description)>(.*?)</", entry, re.S))
    check("스킬 항목의 이름+description(103자)은 본문(280자)보다 짧지만 같은 자릿수: 짧은 지시문은 스킬로 둬도 이득이 크지 않음",
          len(name_desc) == 103 and len(body_of(skill_md).strip()) == 280, f"{len(name_desc)} / {len(body_of(skill_md).strip())}")

    # 4. 명령을 부른 요청
    _, llm, reqs = run_fake(sb, HERE, ["--command", "finish"])
    msg = first_user(llm, reqs)
    check("--command finish: 모델의 사용자 메시지 = 명령 본문 그대로 (사용자 메시지 1개)",
          msg.strip() == body_of(finish_md).strip() and len(user_texts(llm, reqs[0])) == 1, msg[:200])
    check("--command finish: 이 요청의 시스템 프롬프트에도 본문은 들어가지 않음", MARK not in system_text(llm, reqs[0]))
    _, llm, reqs = run_fake(sb, HERE, ["--command", "finish"], script=[("tool", "glob", {"pattern": "*.md"}), "DONE"])
    check("명령 본문은 대화 기록에 남아 이후 요청에도 사용자 메시지로 다시 실려 감 (도구를 한 번 부린 뒤의 두 번째 요청에도 있음)",
          len(reqs) == 2 and body_of(finish_md).strip() in "\n".join(user_texts(llm, reqs[1])), str(len(reqs)))
    _, llm, reqs = run_fake(sb, HERE, ["--command", "finish", "issue 12 부터"])
    msg = first_user(llm, reqs)
    check('$ARGUMENTS 가 없는 명령에 인자를 주면 본문 뒤에 빈 줄과 함께 덧붙고, 공백이 있으면 따옴표가 붙음 ("issue 12 부터")',
          msg == body_of(finish_md).strip() + '\n\n"issue 12 부터"' or msg == body_of(finish_md) .rstrip("\n") + '\n\n"issue 12 부터"', repr(msg[-80:]))
    _, llm, reqs = run_fake(sb, HERE, ["--command", "review", "src/app.py"])
    msg = first_user(llm, reqs)
    check("review src/app.py: $ARGUMENTS 자리에 인자가 들어감", "코드 리뷰해 줘: src/app.py\n" in msg and "$ARGUMENTS" not in msg, msg[:120])
    _, llm, reqs = run_fake(sb, HERE, ["--command", "review", "src/my app.py"])
    msg = first_user(llm, reqs)
    check('review "src/my app.py": 공백이 있는 인자는 따옴표가 붙어서 들어감', '코드 리뷰해 줘: "src/my app.py"\n' in msg, msg[:120])
    proc, llm, reqs = run_fake(sb, HERE, ["--command", "status"])
    check("JSON 으로 정의한 status 도 같은 방식으로 template 이 사용자 메시지가 되고 agent: plan 이 적용됨",
          first_user(llm, reqs).startswith(cfg["command"]["status"]["template"]) and "> plan" in proc.stderr)

    # 5. 임시 프로젝트에서 동작을 하나씩 확인
    work = sb.root / "work"
    probe = {
        ".opencode/command/args.md": "---\ndescription: probe\n---\nALL=[$ARGUMENTS] ONE=[$1] TWO=[$2] THREE=[$3]\n",
        ".opencode/command/agentcmd.md": "---\ndescription: a\nagent: plan\n---\nAGENT-BODY\n",
        ".opencode/command/modelcmd.md": "---\ndescription: m\nmodel: fake/other\n---\nMODEL-BODY\n",
        ".opencode/command/subtask.md": "---\ndescription: s\nsubtask: true\n---\nSUBTASK-BODY\n",
        ".opencode/commands/plural.md": "---\ndescription: p\n---\nPLURAL-BODY $ARGUMENTS\n",
        ".opencode/command/dup.md": "---\ndescription: md desc\n---\nMD-TEMPLATE\n",
        "opencode.json": json.dumps({"command": {"dup": {"template": "JSON-TEMPLATE", "description": "json desc"}}}),
    }
    proj = make_project(work, probe)

    def probe_args(*args):
        _, llm, reqs = run_fake(sb, proj, ["--command", "args", *args])
        return first_user(llm, reqs)

    check("인자 하나 x: ALL=[x] ONE=[x] 이고 없는 $2 $3 는 빈 문자열", probe_args("x") == "ALL=[x] ONE=[x] TWO=[] THREE=[]")
    check('인자 두 개 "a b", c: ALL=["a b" c] ONE=[a b] TWO=[c] -- 공백 있는 인자는 따옴표로 묶이고 $1 은 따옴표를 뗀 값',
          probe_args("a b", "c") == 'ALL=["a b" c] ONE=[a b] TWO=[c] THREE=[]')
    check("인자 세 개 이상이면 마지막 번호($3)가 나머지를 모두 받음 (a b c d -> $3 = c d)",
          probe_args("a", "b", "c", "d") == "ALL=[a b c d] ONE=[a] TWO=[b] THREE=[c d]")
    quoted = probe_args('one "two three" four')
    check("인자 안에 큰따옴표가 있으면 $ARGUMENTS 에서 이스케이프되고 $1 은 쪼개짐 (기대하지 말 것: 이 모양을 관찰만 함)",
          quoted.startswith('ALL=["one \\"two three\\" four"]') and "ONE=[one \\]" in quoted, quoted)

    _, llm, reqs = run_fake(sb, proj, ["--command", "plural", "hi"])
    check(".opencode/commands/ (복수형) 폴더의 명령도 읽힘", first_user(llm, reqs) == "PLURAL-BODY hi")

    proc, llm, reqs = run_fake(sb, proj, ["--command", "agentcmd"])
    check("frontmatter agent: plan -> 실행 헤더가 `plan`, 사용자 메시지에 plan 모드 안내가 붙음",
          "> plan" in proc.stderr and "Plan Mode" in first_user(llm, reqs), proc.stderr[:120])
    proc, llm, reqs = run_fake(sb, proj, ["--command", "modelcmd"], extra_models=("other",))
    check("frontmatter model: fake/other -> 모델 요청의 model 이 other (-m fake/echo 보다 우선)",
          reqs and reqs[0].get("model") == "other" and "> build · other" in proc.stderr, proc.stderr[:120])
    proc, llm, reqs = run_fake(sb, proj, ["--command", "subtask"])
    names0 = sorted(t["function"]["name"] for t in reqs[0]["tools"]) if reqs else []
    check("frontmatter subtask: true -> 하위 에이전트 작업으로 실행됨 (실행 기록에 `Build Agent` 하위 작업 줄, 첫 요청의 도구 목록에 task 없음)",
          "Build Agent" in proc.stderr and "task" not in names0 and "bash" in names0, proc.stderr[:200] + str(names0))
    proc, llm, reqs = run_fake(sb, proj, ["--command", "modelcmd"])
    check("frontmatter model 이 가리키는 모델이 설정에 없으면 실행이 실패하고 모델 호출이 없음",
          not reqs and proc.returncode != 0, f"rc={proc.returncode} {proc.stderr[:200]}")

    proc, llm, reqs = run_fake(sb, proj, ["--command", "nosuch", "hi"])
    check("없는 명령 이름: 종료 코드 1, 모델 호출 없음, 메시지는 'UnknownError ... Unexpected server error' 뿐",
          proc.returncode == 1 and not llm.requests and "UnknownError" in proc.stderr, f"rc={proc.returncode} {proc.stderr[:200]}")
    proc, _, _ = run_fake(sb, proj, ["--print-logs", "--log-level", "ERROR", "--command", "nosuch", "hi"])
    check("--print-logs 로도 이름 오타라는 말은 안 나옴 (SessionPrompt.command 에서 UnknownError)",
          "SessionPrompt.command" in proc.stderr and "nosuch" not in proc.stderr.split("cause=")[0], proc.stderr[:300])

    dup = sb.debug_config(proj, extra_env={"PWD": str(proj)})["command"]["dup"]
    check(".opencode/command/dup.md 와 opencode.json 의 command.dup 이 같은 이름이면 .md 가 이김 (층 순서는 C1과 같음)",
          dup["template"] == "MD-TEMPLATE" and dup["description"] == "md desc", str(dup))

    if model_enabled():
        out = run_with_model(sb, ["run", "-m", "opencode/big-pickle", "--command", "review", "README.md"], HERE)
        model_check("실제 모델: /review README.md 가 오류 없이 끝나고 리뷰 형식(`버그 가능성`)이 나옴", out, "버그 가능성" in out)

finish()
