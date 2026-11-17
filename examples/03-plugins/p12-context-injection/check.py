"""p12-context-injection 검증. 모델 없는 검사(단위 테스트)와 가짜 모델 실행(모델 요청의 시스템 프롬프트/도구 설명), --model 검사.

experimental.chat.system.transform 은 이름이 experimental 입니다. 이 파일의 검사들이 1.19.5 의 동작을 고정해 두므로,
opencode 를 올린 뒤 여기서 FAIL 이 나면 이 훅의 동작이 바뀐 것입니다.
"""
import datetime
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
MARK = "## 지금 상황"
RULE = "프로젝트 규칙: 명령은 한 줄로 쓰고, 여러 명령은 &&(PowerShell 5.1 에서는 ;)로 잇습니다. heredoc 이나 줄바꿈이 든 명령은 쓰지 않습니다."


def show(label: str, text: str) -> None:
    """CHECK_VERBOSE=1 이면 결과를 그대로 출력한다 (README 의 '기대 결과' 수집용)."""
    if os.environ.get("CHECK_VERBOSE") == "1":
        print(f"--- {label} ---\n{text.strip()}\n--- end ---", flush=True)


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def git(cwd: pathlib.Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    return (p.stdout + p.stderr).strip()


def make_repo(sb: Sandbox, name: str, branch: str, plugins: bool = True) -> pathlib.Path:
    """예제 폴더(플러그인, now.md 포함)를 복사해 git 저장소로 만든다. plugins=False 면 플러그인을 뺀 대조군."""
    repo = sb.root / name
    shutil.copytree(HERE, repo, ignore=IGNORE)
    if not plugins:
        shutil.rmtree(repo / ".opencode" / "plugins")
    git(repo, "init", "-q", "-b", branch)
    git(repo, "config", "user.name", "demo")
    git(repo, "config", "user.email", "demo.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / ".gitignore").write_text("logs/\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def bash(command: str) -> tuple:
    return ("tool", "bash", {"command": command, "description": "demo"})


def scripted_run(sb, cwd, script, extra_env=None, timeout=240):
    """가짜 LLM 이 정해진 도구 호출을 하게 하고 opencode run 을 실행한다. 반환: (화면, 모델이 받은 요청 본문 전체 목록)."""
    with FakeLLM(script=script) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
        env.update(extra_env or {})
        proc = sb.opencode(["run", "-m", "fake/echo", "--auto", "go"], cwd, timeout=timeout, extra_env=env)
        return proc.stdout + "\n" + proc.stderr, list(llm.requests)


def systems(request: dict) -> list:
    return [FakeLLM.message_text(m) for m in request.get("messages", []) if m.get("role") == "system"]


def blocks(request: dict) -> list:
    return [t for t in systems(request) if MARK in t]


def descriptions(request: dict) -> dict:
    return {t["function"]["name"]: t["function"].get("description", "") for t in request.get("tools", [])}


def norm(text: str, repo: pathlib.Path) -> str:
    """기본 프롬프트에 든 작업 폴더 경로를 OS 와 표기(역슬래시, 슬래시, 이중 역슬래시)에 상관없이 <DIR> 로 바꾼다."""
    for form in {str(repo), repo.as_posix(), str(repo).replace("\\", "\\\\"), str(repo).replace("\\", "/")}:
        text = text.replace(form, "<DIR>")
    return text


def diff_hint(a: str, b: str) -> str:
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return f"길이 {len(a)} vs {len(b)}, 첫 차이 위치 {i}: {a[max(0, i - 40):i + 60]!r} <-> {b[max(0, i - 40):i + 60]!r}"


def mains(requests: list) -> list:
    return [r for r in requests if r.get("tools")]


def main() -> None:
    node = shutil.which("node")
    has_git = shutil.which("git") is not None
    check("node 가 있다 (훅 단위 테스트용)", node is not None, "node 가 없어 단위 테스트를 건너뜁니다", soft=True)
    check("git 이 있다 (임시 저장소 검사용)", has_git, "git 이 없어 저장소를 쓰는 검사를 건너뜁니다", soft=True)
    if node and has_git:
        t = subprocess.run([node, str(HERE / "tests" / "hooks.test.mjs")], capture_output=True, text=True, encoding="utf-8")
        check("훅 단위 테스트 (system.transform + tool.definition)", t.returncode == 0, t.stdout + t.stderr)
    if not has_git:
        finish()

    today = datetime.date.today()
    weekday = "월화수목금토일"[today.weekday()]
    script = [bash("echo x > new.txt"), bash("echo done"), "끝"]

    with Sandbox("p12") as sb:
        # --- 대조군: 플러그인 없음
        ctrl = make_repo(sb, "ctrl", "feat/alpha", plugins=False)
        out, reqs = scripted_run(sb, ctrl, script)
        cm = mains(reqs)
        check("[대조군] 플러그인이 없으면 시스템 프롬프트에 '지금 상황'이 없음", len(cm) == 3 and not any(blocks(r) for r in reqs), str(len(cm)))
        ctrl_desc = descriptions(cm[0]) if cm else {}
        ctrl_base = norm(systems(cm[0])[0], ctrl) if cm else ""  # 기본 프롬프트에는 작업 폴더 경로가 들어 있어 정규화한다

        # --- A: 플러그인 켬, 브랜치 feat/alpha (기본 TTL 5초)
        repo = make_repo(sb, "alpha", "feat/alpha")
        check("opencode 가 두 플러그인을 로드했다", (sb.debug_config(repo), "context-injection loaded" in read(repo / "logs" / "context-injection.log"))[1])
        # 기본 TTL(5초)은 느린 컴퓨터(Windows 에서 요청 사이가 5초를 넘음)에서 결과가 달라지므로, 이 시나리오는 TTL 을 길게(10분) 고정한다.
        # 기본값 5초 자체의 동작은 단위 테스트(tests/hooks.test.mjs)가 확인한다.
        out, reqs = scripted_run(sb, repo, script, extra_env={"CONTEXT_TTL_MS": "600000"})
        am = mains(reqs)
        check("모델 요청이 도구 호출 단계마다 한 번씩, 모두 3번 (도구 2번 + 마지막 답)", len(am) == 3, str(len(am)))
        first = blocks(am[0])
        show("A: 첫 요청의 주입 블록", first[0] if first else "(없음)")
        check("모든 주요 요청의 시스템 프롬프트에 블록이 정확히 하나씩 들어감", all(len(blocks(r)) == 1 for r in am), str([len(blocks(r)) for r in am]))
        b = first[0] if first else ""
        check("블록 내용: 오늘 날짜(요일), 브랜치, 깨끗한 작업 트리, now.md",
              f"- 오늘: {today.isoformat()} ({weekday})" in b and "- git 브랜치: feat/alpha" in b and "- 작업 트리: 깨끗함" in b and "로그인 화면의 오류 메시지를 한국어로 바꾸는 중" in b, b)
        check("블록은 별도 system 메시지로 맨 끝에 붙고, 앞의 기본 시스템 프롬프트는 대조군과 완전히 같음", all(systems(r)[-1] == b and norm(systems(r)[0], repo) == ctrl_base for r in am) and len(ctrl_base) > 1000, diff_hint(ctrl_base, norm(systems(am[0])[0], repo)) if am else "")
        check("블록 크기가 작다 (now.md 2줄 포함 500자 미만, 기본 시스템 프롬프트 대비 5% 미만)", 0 < len(b) < 500 and len(b) < len(ctrl_base) * 0.05, f"{len(b)}자 / 기본 {len(ctrl_base)}자")
        print(f"       (측정: 주입 블록 {len(b)}자, 기본 시스템 프롬프트 {len(ctrl_base)}자)", flush=True)
        check("제목 생성 같은 보조 요청(도구 없음)에도 같은 블록이 들어감 (훅은 모든 모델 요청에서 불림)", all(len(blocks(r)) == 1 for r in reqs) and len(reqs) > len(am), f"전체 {len(reqs)}, 주요 {len(am)}")
        stale = [("변경" in blocks(r)[0]) for r in am]
        check("TTL 안에서는(여기서는 10분으로 고정) 도구가 파일을 만들어도 두 번째 요청 이후에도 '깨끗함' (캐시된 오래된 값)", not any(stale), str(stale))
        log = read(repo / "logs" / "context-injection.log")
        check("기록: 요청 수만큼 inject 가 남고 첫 번째만 git 을 실제로 조회(gitCached=false)", log.count("inject ") == len(reqs) and log.count("gitCached=false") == 1, log)

        # --- tool.definition: bash 설명 끝에만 규칙 한 줄
        desc = [descriptions(r) for r in am]
        check("tool.definition: bash 설명 = 원래 설명 + 빈 줄 + 규칙 한 줄, 모든 요청에서 한 번만 (누적 없음)",
              all(d["bash"] == ctrl_desc["bash"] + "\n\n" + RULE and d["bash"].count("프로젝트 규칙") == 1 for d in desc), desc[0]["bash"][-200:] if desc else "")
        check("tool.definition: bash 이외 도구의 설명은 대조군과 완전히 같음",
              all({k: v for k, v in d.items() if k != "bash"} == {k: v for k, v in ctrl_desc.items() if k != "bash"} for d in desc) and len(ctrl_desc) >= 8, str(sorted(ctrl_desc)))
        show("A: bash 설명 끝부분", desc[0]["bash"][-250:] if desc else "")

        # --- 브랜치가 바뀌면 다음 실행의 블록이 바뀐다
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "wip")
        git(repo, "switch", "-q", "-c", "feat/beta")
        out, reqs = scripted_run(sb, repo, [bash("echo hi"), "끝"])
        bm = mains(reqs)
        bb = blocks(bm[0])[0] if bm and blocks(bm[0]) else ""
        check("브랜치를 바꾼 뒤 새 실행의 블록에는 feat/beta 가 있고 feat/alpha 는 없음", "- git 브랜치: feat/beta" in bb and "feat/alpha" not in bb, bb)
        show("브랜치 변경 후 블록", bb)

        # --- TTL 0: 요청마다 새로 조회하면 변경이 다음 요청부터 반영된다
        repo2 = make_repo(sb, "ttl0", "main")
        out, reqs = scripted_run(sb, repo2, [bash("echo x > new.txt"), bash("echo done"), "끝"], extra_env={"CONTEXT_TTL_MS": "0"})
        tm = mains(reqs)
        seen = [blocks(r)[0].split("- 작업 트리: ")[1].splitlines()[0] if blocks(r) else "" for r in tm]
        check("CONTEXT_TTL_MS=0: 첫 요청은 '깨끗함', 파일이 만들어진 뒤의 요청들은 '변경 있음' (기본 flag)", seen == ["깨끗함", "커밋되지 않은 변경 있음", "커밋되지 않은 변경 있음"], str(seen))
        # 작업 트리 상태가 바뀌면 시스템 프롬프트가 바뀐다 -> 프롬프트 캐시 접두부가 달라짐
        check("작업 트리가 바뀐 요청부터 시스템 프롬프트 본문이 달라짐 (프롬프트 캐시 접두부가 달라지는 지점)", len({systems(r)[-1] for r in tm}) == 2 and len({systems(r)[0] for r in tm}) == 1, str(len({systems(r)[-1] for r in tm})))

        # --- CONTEXT_DIRTY=count (선택): 개수가 들어간다
        repo5 = make_repo(sb, "count", "main")
        out, reqs = scripted_run(sb, repo5, [bash("echo x > new.txt"), "끝"], extra_env={"CONTEXT_TTL_MS": "0", "CONTEXT_DIRTY": "count"})
        cm2 = mains(reqs)
        check("CONTEXT_DIRTY=count: 파일이 만들어진 뒤 '커밋되지 않은 변경 1개'", len(cm2) == 2 and "커밋되지 않은 변경 1개" in blocks(cm2[1])[0], str([blocks(r) for r in cm2]))

        # --- now.md 가 없고 git 저장소도 아닌 곳: 날짜만 들어가고 아무것도 깨지지 않음
        plain = sb.root / "plain"
        shutil.copytree(HERE, plain, ignore=IGNORE)
        (plain / ".opencode" / "now.md").unlink()
        out, reqs = scripted_run(sb, plain, [bash("echo hi"), "끝"])
        pm = mains(reqs)
        pb = blocks(pm[0])[0] if pm and blocks(pm[0]) else ""
        check("git 저장소가 아니고 now.md 도 없으면 날짜만 들어감", f"- 오늘: {today.isoformat()}" in pb and "git" not in pb and "지금 하는 일" not in pb, pb)

        if model_enabled():
            repo3 = make_repo(sb, "model", "feat/alpha")
            out = sb.run_model("도구를 쓰지 말고 답해 주세요: 지금 git 브랜치 이름과 오늘 날짜가 뭔가요?", repo3)
            show("model run", out)
            model_check("실제 모델이 시스템 프롬프트의 블록을 보고 브랜치와 날짜를 답함", out, "feat/alpha" in out and today.isoformat() in out)

    finish()


if __name__ == "__main__":
    main()
