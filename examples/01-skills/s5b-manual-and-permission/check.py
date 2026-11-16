"""s5b 검증: 스킬을 자동 사용에서 빼는 방법과 직접 부르는 방법.

하드 체크(모델 없음, 가짜 모델 사용): 목록 노출 여부, permission deny/ask, 에이전트별 규칙, --command, 서버 /command.
모델 체크(--model): 실제 모델에게 `--command deploy-checklist` 를 시켜 본문이 전달되는지 본다.
"""
import json
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
sys.path.insert(0, str(HERE))

from octest import MODEL_UNAVAILABLE, RATE_LIMIT_RE, DEFAULT_MODEL, Sandbox, check, finish, model_check, model_enabled

import demo
import lab


class Box:
    """octest.Sandbox 를 lab/mock_llm 이 기대하는 모양으로 감싼다 (opencode run 이 PWD 를 보기 때문에 PWD 를 맞춰 준다)."""

    def __init__(self, sb: Sandbox) -> None:
        self.sb = sb
        self.bin = sb.bin
        self.env = sb.env
        self.root = sb.root

    def opencode(self, args, cwd, overlay=None, timeout=180, extra_env=None):
        return lab.run_opencode(self.bin, self.env, args, cwd, overlay=overlay, timeout=timeout,
                                extra_env=extra_env, scratch=self.root)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def server_commands(box: Box) -> list[dict]:
    """opencode serve 를 잠깐 띄워 GET /command 를 읽는다."""
    port = free_port()
    env = dict(box.env, PWD=str(HERE))
    proc = subprocess.Popen([box.bin, "serve", "--port", str(port), "--hostname", "127.0.0.1"], cwd=str(HERE), env=env,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = f"http://127.0.0.1:{port}/command?directory={urllib.parse.quote(str(HERE))}"
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception:
                time.sleep(1)
        return []
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


with Sandbox("s5b") as sb:
    box = Box(sb)

    # -- 설정과 스킬 발견 ---------------------------------------------------------------
    cfg = sb.debug_config(HERE)
    rules = cfg.get("permission", {}).get("skill")
    check("opencode.json 의 permission.skill 이 '*' 다음에 'deploy-*' 순서로 병합됨",
          isinstance(rules, dict) and list(rules) == ["*", "deploy-*"] and rules["deploy-*"] == "deny", str(rules))
    skills = {s["name"]: s for s in box.sb.debug_skills(HERE)}
    for name in ("deploy-checklist", "team-glossary", "nightly-cleanup", "scratch-notes"):
        check(f"debug skill 에 {name} 이 보임", name in skills)
    check("deny 건 스킬도 debug skill 에는 그대로 보임 (debug skill 은 '모델 목록'이 아님)", "deploy-checklist" in skills)
    check("description 이 없는 스킬은 debug skill 에서 description 키가 없음", "description" not in skills.get("scratch-notes", {"description": 1}))

    # -- 가짜 모델로 전체 시나리오 ---------------------------------------------------------
    r = demo.run_all(box, verbose=False)

    check("모델 요청에 skill 도구가 들어 있음", "skill" in r["plain"].tool_names, str(r["plain"].tool_names))
    check("system 프롬프트에는 이름·description·위치만 있고 본문은 없음",
          "TEAM-GLOSSARY-BODY" not in r["plain"].system_prompt and "<description>" in r["plain"].system_prompt)
    check("아무 제한 없는 스킬은 목록에 보이고 로드됨", "team-glossary" in r["plain"].listed and r["plain"].skill_loaded("team-glossary"))
    check("[실패 확인] disable-model-invocation / metadata 플래그는 효과가 없음 (목록에 그대로 보이고 로드됨)",
          "nightly-cleanup" in r["flags"].listed and r["flags"].skill_loaded("nightly-cleanup"))
    check("description 이 없는 스킬은 목록에서 빠지지만 이름을 알면 로드됨",
          "scratch-notes" not in r["nodesc"].listed and r["nodesc"].skill_loaded("scratch-notes"))
    check("permission deny: 목록에서 빠지고 skill 도구로도 못 불러옴",
          "deploy-checklist" not in r["deny"].listed and r["deny"].skill_failed("deploy-checklist")
          and "prevents you from using" in r["deny"].transcript)
    check("agent 파일(release)이 deploy-* 를 다시 허용하면 목록에 보이고 로드됨",
          "deploy-checklist" in r["agent_release"].listed and r["agent_release"].skill_loaded("deploy-checklist"))
    check("agent.build 에만 deny: build 는 막히고 plan 은 로드됨",
          r["agent_build_deny"].skill_failed("deploy-checklist") and r["agent_plan_ok"].skill_loaded("deploy-checklist"))
    check("[실패 확인] 규칙 순서를 거꾸로 쓰면(deny 뒤에 '*' allow) deny 가 무효: 마지막 일치 규칙이 이김",
          r["wrong_order"].skill_loaded("deploy-checklist"))
    check("ask + opencode run --auto: 자동 승인되어 로드됨", r["ask_auto"].skill_loaded("deploy-checklist"))
    check("ask + opencode run (--auto 없음): 자동 거절됨",
          "auto-rejecting" in r["ask_noauto"].transcript and r["ask_noauto"].skill_failed("deploy-checklist"))
    cmd = r["command"]
    check("run --command deploy-checklist: deny 여도 스킬 본문이 사용자 메시지로 전달됨",
          "DEPLOY-CHECKLIST-V3" in cmd.first_user_text and cmd.first_user_text.rstrip().endswith("프로덕션 v2.3"), cmd.first_user_text[:300])
    check("--command 로 부르면 skill 도구 호출 없이 끝남", "→ Skill" not in cmd.transcript)

    # -- 서버의 /command 목록 (TUI 의 /skills 선택창이 쓰는 것과 같은 소스) ------------------------
    commands = server_commands(box)
    by_name = {c["name"]: c for c in commands}
    check("GET /command 에 deploy-checklist 가 source=skill 로 있음 (deny 여도)",
          by_name.get("deploy-checklist", {}).get("source") == "skill", str([c["name"] for c in commands]))
    check("GET /command 에서 기본 명령 init/review 는 source=command", by_name.get("init", {}).get("source") == "command")

    # -- 실제 모델 (선택) --------------------------------------------------------------
    if model_enabled():
        out = lab.run_model(box, "프로덕션 v2.3 배포 직전 점검 부탁해", HERE, DEFAULT_MODEL,
                            extra_args=["--command", "deploy-checklist"])
        if RATE_LIMIT_RE.search(out) or out.startswith("<<timeout>>"):
            out = MODEL_UNAVAILABLE + "\n" + out
        model_check("실제 모델: --command deploy-checklist 로 체크리스트 본문을 받아 답함",
                    out, ("롤백" in out or "CI" in out) and '→ Skill "deploy-checklist"' not in out)
# octest.Sandbox 는 Windows 에서 읽기 전용 git 객체 파일을 못 지우고 폴더를 남기므로 한 번 더 정리한다
lab.rmtree_force(sb.root)
finish()
