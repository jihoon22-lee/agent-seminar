"""P6 검증: 플러그인 커스텀 도구가 등록되는지 확인한다.

모델 없이도 `opencode serve` 의 /experimental/tool/ids 로 도구 목록을 볼 수 있다.
"""
import json
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, tool_called  # noqa: E402

HERE = Path(__file__).resolve().parent
TOOLS = ("business_days", "uuid_v4", "team_glossary")


# --- 스크립트된 가짜 모델 (check.py 안에 복사해 쓰는 조각) ---------------------------------------------
# 무료 모델 한도와 상관없이 "도구가 실제로 실행되는지"를 결정적으로 검증하기 위한 OpenAI 호환 서버 흉내.
# opencode 에 provider 로 등록하면 `opencode run -m fake/scripted` 로 쓸 수 있다.
import json as _json
import threading as _threading
import time as _time
from http.server import BaseHTTPRequestHandler as _Handler, ThreadingHTTPServer as _Server


class ScriptedLLM:
    """steps[i] = [(도구이름, 인자dict), ...]  i 번째 응답에서 모델이 호출할 도구들.
    steps 를 다 쓰면 지금까지 받은 도구 결과를 그대로 읽어 주는 최종 문장을 돌려준다."""

    def __init__(self, steps):
        self.steps = steps
        outer = self

        class Handler(_Handler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a):
                pass

            def do_POST(self):
                body = _json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                msgs, tools = body.get("messages", []), body.get("tools") or []
                rounds = sum(1 for m in msgs if m.get("role") == "assistant" and m.get("tool_calls"))
                calls, text = None, "제목"
                if tools:
                    if rounds < len(outer.steps):
                        calls = outer.steps[rounds]
                    else:
                        results = [m.get("content") for m in msgs if m.get("role") == "tool"]
                        text = "도구 결과:\n" + "\n".join(str(r)[:600] for r in results)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()

                def send(raw):
                    self.wfile.write(f"{len(raw):x}\r\n".encode() + raw + b"\r\n")

                def chunk(delta, finish=None):
                    data = {"id": "c1", "object": "chat.completion.chunk", "created": int(_time.time()), "model": "scripted",
                            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                    send(("data: " + _json.dumps(data) + "\n\n").encode())

                chunk({"role": "assistant", "content": ""})
                if calls:
                    for i, (name, args) in enumerate(calls):
                        chunk({"tool_calls": [{"index": i, "id": f"call_{rounds}_{i}", "type": "function",
                                               "function": {"name": name, "arguments": _json.dumps(args, ensure_ascii=False)}}]})
                    chunk({}, "tool_calls")
                else:
                    chunk({"content": text})
                    chunk({}, "stop")
                send(b"data: [DONE]\n\n")
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()

        self.server = _Server(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]

    def provider_config(self):
        return {"provider": {"fake": {"npm": "@ai-sdk/openai-compatible", "name": "Scripted",
                                      "options": {"baseURL": f"http://127.0.0.1:{self.port}/v1", "apiKey": "unused"},
                                      "models": {"scripted": {"name": "scripted", "tool_call": True,
                                                              "limit": {"context": 100000, "output": 4000}}}}}}

    def __enter__(self):
        _threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *_exc):
        self.server.shutdown()
        self.server.server_close()
# -------------------------------------------------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve_get(sb: Sandbox, cwd: Path, path: str, timeout: int = 180):
    """opencode serve 를 잠깐 띄워 GET path 의 JSON 을 돌려준다."""
    port = free_port()
    proc = subprocess.Popen(
        [sb.bin, "serve", "--port", str(port), "--hostname", "127.0.0.1"],
        cwd=str(cwd), env=sb.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=60) as r:
                    return json.loads(r.read().decode("utf-8"))
            except Exception:
                time.sleep(1)
        return None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


with Sandbox("p6") as sb:
    # 첫 실행에서는 opencode 가 .opencode/ 에 @opencode-ai/plugin 을 npm 으로 설치한다.
    ids = serve_get(sb, HERE, "/experimental/tool/ids")
    check("opencode serve 가 도구 목록을 돌려준다", isinstance(ids, list), str(ids))
    ids = ids or []
    for name in TOOLS:
        check(f"커스텀 도구 {name} 등록됨", name in ids, f"등록된 도구: {ids}")
    check("내장 도구(bash)도 그대로 있다", "bash" in ids)

    pkg = HERE / ".opencode" / "node_modules" / "@opencode-ai" / "plugin" / "package.json"
    check("@opencode-ai/plugin 이 .opencode/ 에 자동 설치됨", pkg.is_file())

    schemas = serve_get(sb, HERE, "/experimental/tool?provider=opencode&model=big-pickle") or []
    by_id = {t["id"]: t for t in schemas if isinstance(t, dict)}
    bd = by_id.get("business_days", {}).get("parameters", {})
    check("business_days 의 zod 스키마가 JSON Schema 로 변환됨 (from, to 필수)",
          set(bd.get("required", [])) == {"from", "to"} and bd.get("properties", {}).get("from", {}).get("type") == "string",
          json.dumps(bd, ensure_ascii=False))
    check("uuid_v4 는 인자가 없다", by_id.get("uuid_v4", {}).get("parameters", {}).get("properties") == {})

    # --pure 에서는 외부 플러그인이 로드되지 않아 커스텀 도구도 사라진다.
    pure_ids = None
    port = free_port()
    proc = subprocess.Popen(
        [sb.bin, "--pure", "serve", "--port", str(port), "--hostname", "127.0.0.1"],
        cwd=str(HERE), env=sb.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(120):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/experimental/tool/ids", timeout=60) as r:
                    pure_ids = json.loads(r.read().decode("utf-8"))
                break
            except Exception:
                time.sleep(1)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    check("--pure 에서는 커스텀 도구가 없다", pure_ids is not None and not any(t in pure_ids for t in TOOLS), str(pure_ids))

    # 스크립트된 가짜 모델: 모델 한도와 상관없이 "도구가 실제로 실행되고 결과가 돌아오는지"를 결정적으로 확인한다.
    steps = [
        [("business_days", {"from": "2026-11-02", "to": "2026-11-27"}), ("uuid_v4", {}), ("team_glossary", {"term": "온콜"})],
        [("business_days", {"from": "2026-13-40", "to": "2026-11-27"}), ("team_glossary", {"term": "없는용어"})],
    ]
    with ScriptedLLM(steps) as llm, Sandbox("p6-fake", global_config=llm.provider_config()) as fake:
        out = fake.opencode(["run", "-m", "fake/scripted", "--auto", "도구를 써 줘"], HERE, timeout=240,
                            extra_env={"PWD": str(HERE)})
        out = out.stdout + "\n" + out.stderr
    check("스크립트 실행: ⚙ business_days 호출이 기록됨", tool_called(out, "business_days"), out[-800:])
    check("business_days 결과: 2026-11-02 ~ 2026-11-27 = 20일", "영업일: 20일" in out, out[-800:])
    check("uuid_v4 결과가 UUID 형식", re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", out) is not None, out[-800:])
    check("team_glossary('온콜') 결과가 glossary.json 에서 옴", "장애 알림을 받아" in out, out[-800:])
    check("잘못된 날짜는 도구 오류로 돌아온다", "존재하지 않는 날짜" in out, out[-800:])
    check("없는 용어는 등록된 용어 목록을 돌려준다", "등록된 용어: ADR, SLO" in out, out[-800:])

    if model_enabled():
        out = sb.run_model(
            "business_days 도구로 2026-11-02 부터 2026-11-27 까지 영업일이 며칠인지 알려 줘. 도구 결과를 그대로 말해 줘.",
            cwd=HERE, extra_env={"PWD": str(HERE)},
        )
        model_check("모델이 business_days 를 호출함", out, tool_called(out, "business_days"))
        model_check("영업일 20일이라고 답함", out, "20" in out)
        out = sb.run_model("team_glossary 도구로 '온콜' 이 무슨 뜻인지 찾아 줘.", cwd=HERE, extra_env={"PWD": str(HERE)})
        model_check("모델이 team_glossary 를 호출함", out, tool_called(out, "team_glossary"))
finish()
