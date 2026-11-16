"""p7 검증: experimental.session.compacting 훅이 압축 때 실제로 호출되고, 넣은 문자열이 요약 프롬프트에 들어가는가.

가짜 LLM(fake_llm.py)이 요약 모델 역할을 하며 opencode 가 보낸 압축 요청 본문을 기록한다 → 모델 없이 결정적.
압축을 일으키는 두 가지 길:
  1) 수동: `POST /session/:id/summarize` (TUI 의 /compact 가 쓰는 것과 같은 기능)
  2) 자동: 응답 usage 가 컨텍스트 한도 근처라고 보고하면 opencode 가 스스로 압축한다 (`opencode run` 만으로 재현)
`--model` 이면 실제 모델이 만든 요약에 고정 사실(pnpm)이 들어 있는지 (soft) 확인한다.
"""
import json
import pathlib
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import MODEL_UNAVAILABLE, Sandbox, _model_lock, check, finish, model_check, model_enabled  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fake_llm import FakeLLM  # noqa: E402

LOG = HERE / "logs" / "compaction.log"
FACTS = (HERE / ".opencode" / "memory" / "project-facts.md").read_text(encoding="utf-8").strip()
LAST_FACT_LINE = FACTS.splitlines()[-1]


def http(method, url, body=None, timeout=150):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "null")


def read_log(path=LOG):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def reset_log():
    shutil.rmtree(HERE / "logs", ignore_errors=True)


def stop(proc):
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


class Server:
    """opencode serve 를 띄우고 닫는 컨텍스트 매니저. 첫 시작에는 @opencode-ai/plugin 설치 때문에 오래 걸릴 수 있다."""

    def __init__(self, sb, cwd, llm_env):
        self.sb, self.cwd = sb, cwd
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.env = dict(sb.env, PWD=str(cwd), **llm_env)

    def __enter__(self):
        self.proc = subprocess.Popen([self.sb.bin, "serve", "--port", str(self.port)], cwd=str(self.cwd), env=self.env,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(600):
            try:
                http("GET", self.base + "/mcp", timeout=2)
                return self
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("opencode serve 가 시작되지 않음")

    def __exit__(self, *exc):
        stop(self.proc)

    def say(self, sid, text, provider="fake", model="echo"):
        return http("POST", f"{self.base}/session/{sid}/message",
                    {"model": {"providerID": provider, "modelID": model}, "parts": [{"type": "text", "text": text}]})

    def summarize(self, sid, provider="fake", model="echo"):
        return http("POST", f"{self.base}/session/{sid}/summarize", {"providerID": provider, "modelID": model})


def compaction_request(llm, since):
    """since 이후 요청 중 압축 요청(도구 목록 없음 + 요약 시스템 프롬프트)."""
    for r in llm.requests[since:]:
        if not r.get("tools") and "context summarization agent" in llm.message_text(r["messages"][0]):
            return r
    return None


check("플러그인과 고정 사실 파일이 있음", (HERE / ".opencode" / "plugins" / "compaction-context.js").exists() and "pnpm" in FACTS)
check("opencode.json 이 없음 (플러그인은 .opencode/plugins/ 에서 자동 로드되므로 설정이 필요 없다)", not (HERE / "opencode.json").exists())

reset_log()
with FakeLLM() as llm, Sandbox("p7") as sb:
    llm_env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}

    # --- 1. 수동 압축 -------------------------------------------------------------------------
    with Server(sb, HERE, llm_env) as srv:
        sid = http("POST", srv.base + "/session", {"title": "p7"})["id"]
        srv.say(sid, "첫 질문: 이 프로젝트 소개해줘")
        srv.say(sid, "둘째 질문: 배포는 어떻게 해?")
        n = len(llm.requests)
        check("POST /session/:id/summarize 가 성공", srv.summarize(sid) is True)
        events = [e for e in read_log() if e["event"] == "compacting"]
        check("압축 시 experimental.session.compacting 훅이 정확히 한 번 호출되고 logs/compaction.log 에 기록됨",
              len(events) == 1 and events[0]["sessionID"] == sid, str(read_log()))
        e = events[0] if events else {}
        check("훅 input 은 {sessionID} 뿐, output 은 {context: [], prompt: 없음} (1.19.5 관찰)",
              e.get("inputKeys") == ["sessionID"] and e.get("outputKeys") == ["context", "prompt"]
              and e.get("contextBefore") == 0 and e.get("promptSet") is False, str(e))
        req = compaction_request(llm, n)
        user = llm.message_text(req["messages"][-1]) if req else ""
        check("압축 요청은 도구 없이 [system 요약 에이전트, user 압축 프롬프트] 두 메시지", req is not None and not req.get("tools") and [m["role"] for m in req["messages"]] == ["system", "user"], str(req)[:300])
        check("output.context 에 push 한 고정 사실이 압축 프롬프트(user) 맨 끝에 붙어 요약 모델에게 전달됨",
              "Create a new anchored summary" in user and user.rstrip().endswith(LAST_FACT_LINE) and "pnpm" in user, user[-600:])
        check("기본 압축 프롬프트의 원문 대화(<conversation>)도 그대로 들어 있음", "<conversation>" in user and "둘째 질문" in user)
        # 작동하지 않는 길들 (관찰): v2 API 의 compact 는 아직 준비되지 않음
        try:
            http("POST", f"{srv.base}/api/session/{sid}/compact", {})
            code = 200
        except urllib.error.HTTPError as exc:
            code = exc.code
        check("POST /api/session/:id/compact (v2 API) 는 아직 503 'not available yet' — summarize 를 써야 함", code == 503, str(code))
        msgs = http("GET", f"{srv.base}/session/{sid}/message")
        check("압축 뒤 세션에 compaction 파트를 가진 user 메시지와 agent=compaction 요약(assistant) 메시지가 생김",
              any(p["type"] == "compaction" for m in msgs for p in m["parts"])
              and any(m["info"].get("agent") == "compaction" and m["info"].get("summary") for m in msgs), str([(m["info"]["role"], m["info"].get("agent")) for m in msgs]))

    # --- 2. 자동 압축: 첫 턴 usage 를 한도 근처로 보고 → opencode 가 스스로 압축 ------------------
    reset_log()
with FakeLLM(prompt_tokens=[99000, 10]) as llm, Sandbox("p7-auto") as sb:
    env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config(context=100000)), "PWD": str(HERE)}
    out = sb.opencode(["run", "-m", "fake/echo", "첫 질문"], HERE, timeout=240, extra_env=env)
    ev = read_log()
    kinds = [e["event"] for e in ev]
    check("자동 압축: opencode run 한 번으로 compacting → autocontinue 훅이 순서대로 호출 (TUI 없이 재현 가능)",
          kinds == ["compacting", "autocontinue"], f"{kinds}\n{out.stdout}\n{out.stderr}")
    auto = ev[1] if len(ev) > 1 else {}
    check("autocontinue 훅 input 키 = sessionID, agent, model, provider, message, overflow / output 기본값 {enabled: true}",
          sorted(auto.get("inputKeys", [])) == ["agent", "message", "model", "overflow", "provider", "sessionID"]
          and auto.get("outputBefore") == {"enabled": True}, str(auto))
    check("자동 압축 뒤 opencode 가 'Continue if you have next steps…' 턴을 이어서 실행 (요청 4개: 제목·대화·압축·이어하기)",
          "Continue if you have next steps" in out.stdout and len(llm.requests) == 4, f"{len(llm.requests)} {out.stdout}")

    # `opencode run` 으로는? --command compact 는 서버 명령이 아니라 TUI 내장이라 실패, 본문의 /compact 는 글자 그대로 모델에게 감
    reset_log()
    before = len(llm.requests)
    out = sb.opencode(["run", "-c", "-m", "fake/echo", "--command", "compact"], HERE, timeout=120, extra_env=env)
    check("opencode run --command compact 는 실패(서버 명령이 아님)하고 압축도 일어나지 않음",
          out.returncode != 0 and not read_log(), f"rc={out.returncode} {out.stdout}{out.stderr}")
    out = sb.opencode(["run", "-c", "-m", "fake/echo", "/compact"], HERE, timeout=120, extra_env=env)
    check("opencode run \"/compact\" 는 슬래시 명령으로 해석되지 않고 모델에게 글자 그대로 전달됨(압축 없음)",
          out.returncode == 0 and not read_log() and any("/compact" in llm.message_text(m) for r in llm.requests[before:]
                                                         for m in r["messages"] if m["role"] == "user"), f"{out.stdout}{out.stderr}")

    # --- 3. 변형 플러그인: output.prompt 설정 / autocontinue 끄기 -------------------------------
    def variant(name, replace_from, replace_to):
        d = sb.root / name
        shutil.copytree(HERE, d, ignore=shutil.ignore_patterns("logs", "__pycache__"))
        plugin = d / ".opencode" / "plugins" / "compaction-context.js"
        text = plugin.read_text(encoding="utf-8")
        assert replace_from in text
        plugin.write_text(text.replace(replace_from, replace_to), encoding="utf-8")
        return d

    d = variant("v-prompt", "      if (facts) {", '      output.prompt = "CUSTOM-PROMPT: 한 줄로만 요약하라."\n      if (facts) {')
    with FakeLLM() as llm2:
        with Server(sb, d, {"OPENCODE_CONFIG_CONTENT": json.dumps(llm2.provider_config())}) as srv:
            sid = http("POST", srv.base + "/session", {"title": "v"})["id"]
            srv.say(sid, "hello")
            n = len(llm2.requests)
            srv.summarize(sid)
            req = compaction_request(llm2, n)
            user = llm2.message_text(req["messages"][-1]) if req else ""
        check("output.prompt 를 설정하면 기본 압축 프롬프트가 통째로 대체되고, 같이 push 한 context(고정 사실)는 무시됨",
              user.startswith("CUSTOM-PROMPT") and "pnpm" not in user and "Create a new anchored summary" not in user, user[:300])

    # 훅 안의 예외: 감싸지 않으면 압축이 통째로 실패하고, 이 예제처럼 safe() 로 감싸면 압축은 계속된다
    boom = "      const facts = existsSync"
    for name, unguard, expect_ok in (("v-throw-guarded", False, True), ("v-throw-unguarded", True, False)):
        d = variant(name, boom, '      throw new Error("boom in hook")\n' + boom)
        if unguard:
            plugin = d / ".opencode" / "plugins" / "compaction-context.js"
            guard = 'try { await fn(input, output) } catch (err) { log({ event: "error", hook, message: String(err) }) }'
            text = plugin.read_text(encoding="utf-8")
            assert guard in text
            plugin.write_text(text.replace(guard, "await fn(input, output)"), encoding="utf-8")
        with FakeLLM() as llm4:
            with Server(sb, d, {"OPENCODE_CONFIG_CONTENT": json.dumps(llm4.provider_config())}) as srv:
                sid = http("POST", srv.base + "/session", {"title": "v"})["id"]
                srv.say(sid, "hello")
                n = len(llm4.requests)
                try:
                    result = srv.summarize(sid)
                except urllib.error.HTTPError as exc:
                    result = exc.code
                got = compaction_request(llm4, n) is not None
            errs = [e for e in read_log(d / "logs" / "compaction.log") if e["event"] == "error"]
        if expect_ok:
            check("훅이 예외를 던져도 safe() 로 감싸 두면 압축은 정상 진행되고 오류는 logs/compaction.log 에 기록됨",
                  result is True and got and errs and "boom in hook" in errs[0]["message"], f"{result} {got} {errs}")
        else:
            check("감싸지 않은 훅이 예외를 던지면 압축이 통째로 실패 (summarize 500, 요약 요청도 안 나감)", result == 500 and not got, f"{result} {got}")

    d = variant("v-nocontinue", "      log({\n        event: \"autocontinue\"", "      output.enabled = false\n      log({\n        event: \"autocontinue\"")
    with FakeLLM(prompt_tokens=[99000, 10]) as llm3:
        env3 = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm3.provider_config(context=100000)), "PWD": str(d)}
        out = sb.opencode(["run", "-m", "fake/echo", "첫 질문"], d, timeout=240, extra_env=env3)
        check("autocontinue 훅에서 output.enabled=false 로 바꾸면 '이어하기' 턴이 생기지 않음 (요청 3개)",
              len(llm3.requests) == 3 and "Continue if you have next steps" not in out.stdout, f"{len(llm3.requests)} {out.stdout}")

    # --- 4. 실제 모델 ---------------------------------------------------------------------------
    if model_enabled():
        reset_log()
        summary, ok = "", False
        with _model_lock():
            try:
                with Server(sb, HERE, {}) as srv:
                    sid = http("POST", srv.base + "/session", {"title": "p7-model"})["id"]
                    srv.say(sid, "로그인 화면의 버그를 고치는 일을 시작했어. 오늘 할 일을 한 문장으로 정리해줘.", "opencode", "big-pickle")
                    srv.say(sid, "다음에 할 일은 테스트 추가야. 도구는 쓰지 말고 짧게 답해줘.", "opencode", "big-pickle")
                    ok = srv.summarize(sid, "opencode", "big-pickle") is True
                    msgs = http("GET", f"{srv.base}/session/{sid}/message")
                    summary = "\n".join(p.get("text", "") for m in msgs if m["info"].get("agent") == "compaction"
                                        for p in m["parts"] if p["type"] == "text")
            except Exception as exc:  # 할당량·네트워크 문제는 '검증 불가'로 보고
                summary = MODEL_UNAVAILABLE + f" {exc}"
        model_check("실제 모델이 만든 요약에 고정 사실(pnpm)이 담김 — 대화에는 한 번도 나오지 않은 정보",
                    summary, ok and "pnpm" in summary)
        print(f"       훅 호출 기록: {[e['event'] for e in read_log()]}")
        print("       요약 앞부분: " + summary[:300].replace("\n", " | "))

reset_log()
finish()
