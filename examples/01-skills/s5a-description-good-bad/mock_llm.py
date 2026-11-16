"""모델 없이 돌리는 가짜 모델 서버 (표준 라이브러리만 사용, Python 3.10+).

opencode 가 모델에게 보내는 요청을 127.0.0.1 에서 받아 그대로 기록하고, 정해진 답을 돌려줍니다.
  - 요청 본문에 들어 있는 system 프롬프트와 도구 목록을 보면 "모델이 처음부터 무엇을 보는가"를 알 수 있습니다.
  - 프롬프트에 [[skill:이름]] 표식이 있으면 `skill` 도구를 그 이름으로 호출하는 척합니다.
    (도구 결과가 돌아오면 "TOOL-RESULT: ..." 로 한 번 되풀이하고 끝냅니다.)
  - 그 밖의 프롬프트에는 "OK" 라고만 답합니다.
인터넷도, 모델 쿼터도 쓰지 않으므로 결과가 매번 똑같습니다.
"""
from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MARKER = re.compile(r"\[\[skill:([A-Za-z0-9_.-]+)\]\]")


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


class MockLLM:
    def __init__(self, port: int = 0) -> None:
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence
                pass

            def do_POST(self):
                length = int(self.headers.get("content-length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                outer.requests.append(body)
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.end_headers()
                outer._reply(self, body)

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> "MockLLM":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def config(self) -> dict:
        """Config fragment that registers the mock as provider `mock` (model `mock/m`)."""
        return {
            "provider": {
                "mock": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Mock",
                    "options": {"baseURL": f"http://127.0.0.1:{self.port}/v1", "apiKey": "demo-key-123"},
                    "models": {"m": {"name": "M", "tool_call": True, "limit": {"context": 32000, "output": 4000}}},
                }
            }
        }

    # -- helpers for assertions ---------------------------------------------
    def chat_requests(self) -> list[dict]:
        """Requests that carry the tool list = the real conversation (not the title generator)."""
        return [r for r in self.requests if r.get("tools")]

    def system_prompt(self) -> str:
        reqs = self.chat_requests()
        if not reqs:
            return ""
        return "\n".join(_text_of(m.get("content")) for m in reqs[0]["messages"] if m["role"] == "system")

    def tool_names(self) -> list[str]:
        reqs = self.chat_requests()
        return [t["function"]["name"] for t in reqs[0]["tools"]] if reqs else []

    # -- protocol ------------------------------------------------------------
    def _reply(self, h: BaseHTTPRequestHandler, body: dict) -> None:
        def send(delta, finish=None, usage=None):
            chunk = {"id": "mock-1", "object": "chat.completion.chunk", "created": 1, "model": "m",
                     "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
            if usage:
                chunk["usage"] = usage
            h.wfile.write(b"data: " + json.dumps(chunk).encode() + b"\n\n")
            h.wfile.flush()

        usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        messages = body.get("messages", [])
        last_user = next((_text_of(m.get("content")) for m in reversed(messages) if m["role"] == "user"), "")
        wanted = MARKER.search(last_user)
        has_tool_result = bool(messages) and messages[-1]["role"] == "tool"
        if wanted and body.get("tools") and not has_tool_result:
            send({"role": "assistant", "tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                                       "function": {"name": "skill",
                                                                    "arguments": json.dumps({"name": wanted.group(1)})}}]})
            send({}, "tool_calls", usage)
        elif has_tool_result:
            result = _text_of(messages[-1].get("content")).replace("\n", " ")
            send({"role": "assistant", "content": "TOOL-RESULT: " + result[:160]})
            send({}, "stop", usage)
        else:
            send({"role": "assistant", "content": "OK"})
            send({}, "stop", usage)
        h.wfile.write(b"data: [DONE]\n\n")
        h.wfile.flush()


# ---------------------------------------------------------------------------
# 한 번 실행해 보고 결과를 모아 주는 함수
# ---------------------------------------------------------------------------
class MockRun:
    def __init__(self, mock: "MockLLM", proc) -> None:
        self.proc = proc
        self.transcript = proc.stdout + "\n" + proc.stderr
        self.system_prompt = mock.system_prompt()
        self.tool_names = mock.tool_names()
        self.listed = re.findall(r"<name>([^<]+)</name>", self.system_prompt)  # 모델에게 보이는 스킬 이름들
        chats = mock.chat_requests()
        self.first_user_text = ""
        if chats:
            users = [_text_of(m.get("content")) for m in chats[0]["messages"] if m["role"] == "user"]
            self.first_user_text = users[-1] if users else ""
        m = re.search(r"TOOL-RESULT: (.*)", proc.stdout)
        self.tool_result = m.group(1) if m else ""
        self.chat_request_count = len(chats)

    def skill_loaded(self, name: str) -> bool:
        """대화 기록에 `→ Skill "이름"` 표식이 있는가 (스킬이 실제로 로드됨)."""
        return f'→ Skill "{name}"' in self.transcript

    def skill_failed(self, name: str) -> bool:
        """`✗ Skill "이름" failed` 표식이 있는가 (권한 거부·못 찾음 등)."""
        return f'✗ Skill "{name}"' in self.transcript


def mock_run(sb, cwd, prompt: str = "", overlay: dict | None = None, agent: str | None = None,
             command: str | None = None, command_args: list[str] | None = None, auto: bool = True,
             timeout: int = 120) -> MockRun:
    """가짜 모델로 `opencode run` 을 한 번 실행합니다. sb 는 lab.Sandbox (또는 같은 모양의 객체)."""
    mock = MockLLM().start()
    try:
        cfg = dict(mock.config())
        cfg.update(overlay or {})
        args = ["run", "-m", "mock/m"]
        if auto:
            args.append("--auto")
        if agent:
            args += ["--agent", agent]
        if command:
            args += ["--command", command]
        args += list(command_args or [])
        if prompt:
            args.append(prompt)
        proc = sb.opencode(args, cwd, overlay=cfg, timeout=timeout)
        return MockRun(mock, proc)
    finally:
        mock.stop()
