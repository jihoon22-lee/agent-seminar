"""가짜 LLM 서버 (표준 라이브러리만 사용) — check.py 와 연습용.

OpenAI 호환 /v1/chat/completions 엔드포인트를 흉내 낸다. 진짜 모델 대신 이 서버를 쓰면
"opencode 가 모델에게 실제로 무엇을 보냈는가"(도구 목록, 사용자 메시지, 시스템 프롬프트)를
요청 본문 그대로 기록할 수 있고, 결과가 항상 같다(모델 한도·무작위성 없음).

    from fake_llm import FakeLLM
    with FakeLLM(script=["FAKE-REPLY"]) as llm:
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(llm.provider_config())}
        # opencode run -m fake/echo "질문"   (env 와 함께 실행)
        print(llm.requests)   # 받은 요청 본문(dict) 목록

script: 요청 순서대로 돌려줄 응답. 문자열은 일반 텍스트 답변,
        ("tool", "도구이름", {인자}) 는 모델이 그 도구를 호출하는 것처럼 흉내 낸다.
        script 는 도구 목록이 붙은 요청(진짜 대화 턴)에만 소비된다. 다 쓰면 기본 텍스트("FAKE-REPLY")를 돌려준다.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeLLM:
    def __init__(self, script=None, default="FAKE-REPLY", prompt_tokens=(10,)):
        self.script = list(script or [])
        # 응답 usage 로 보고할 입력 토큰 수. 리스트면 "도구 목록이 붙은 요청(대화 턴)"마다 하나씩 소비한다
        # (자동 압축 실험용: 첫 턴만 컨텍스트 한도에 가깝게 보고하고 이후는 작게)
        self.prompt_tokens = list(prompt_tokens) if isinstance(prompt_tokens, (list, tuple)) else [prompt_tokens]
        self.default = default
        self.requests: list[dict] = []
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                with outer._lock:
                    outer.requests.append(body)
                    # 제목 생성 같은 도구 없는 보조 요청에는 script 를 쓰지 않는다
                    reply = outer.script.pop(0) if (outer.script and body.get("tools")) else outer.default
                    tokens = 10
                    if body.get("tools"):
                        tokens = outer.prompt_tokens.pop(0) if len(outer.prompt_tokens) > 1 else outer.prompt_tokens[0]
                outer._send(self, body, reply, tokens)

            def log_message(self, *args):  # 조용히
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    # -- lifecycle ----------------------------------------------------------------
    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    # -- opencode 설정 조각 -----------------------------------------------------------
    def provider_config(self, provider="fake", model="echo", context=100000) -> dict:
        """OPENCODE_CONFIG_CONTENT 로 넘길 설정. 모델 이름은 "fake/echo"."""
        return {"provider": {provider: {
            "npm": "@ai-sdk/openai-compatible", "name": provider,
            "options": {"baseURL": f"http://127.0.0.1:{self.port}/v1", "apiKey": "demo-key"},
            "models": {model: {"name": model, "tool_call": True,
                               "limit": {"context": context, "output": 4000}}}}}}

    # -- 요청 분석 도우미 -------------------------------------------------------------
    def main_requests(self) -> list[dict]:
        """제목 생성용 요청(도구 없음)을 뺀, 도구 목록이 붙은 요청만."""
        return [r for r in self.requests if r.get("tools")]

    @staticmethod
    def tool_names(request: dict) -> list[str]:
        return sorted(t["function"]["name"] for t in request.get("tools", []))

    @staticmethod
    def message_text(message: dict) -> str:
        content = message.get("content")
        if isinstance(content, list):
            return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
        return content or ""

    # -- 응답 만들기 ------------------------------------------------------------------
    def _send(self, handler, body, reply, tokens=10):
        stream = bool(body.get("stream"))
        if isinstance(reply, tuple):
            _, name, args = reply
            delta = {"tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                     "function": {"name": name, "arguments": json.dumps(args)}}]}
            finish = "tool_calls"
            message = {"role": "assistant", "content": None, "tool_calls": delta["tool_calls"]}
        else:
            delta = {"content": reply}
            finish = "stop"
            message = {"role": "assistant", "content": reply}
        usage = {"prompt_tokens": tokens, "completion_tokens": 3, "total_tokens": tokens + 3}
        base = {"id": "fake-1", "object": "chat.completion.chunk", "created": 0, "model": "echo"}
        if not stream:
            data = json.dumps({**base, "object": "chat.completion", "usage": usage,
                               "choices": [{"index": 0, "message": message, "finish_reason": finish}]}).encode()
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(data)))
            handler.end_headers()
            handler.wfile.write(data)
            return
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()

        def event(obj):
            handler.wfile.write(("data: " + json.dumps(obj) + "\n\n").encode())
            handler.wfile.flush()

        event({**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]})
        event({**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]})
        event({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}], "usage": usage})
        handler.wfile.write(b"data: [DONE]\n\n")
        handler.wfile.flush()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    with FakeLLM() as llm:
        print(f"fake LLM: http://127.0.0.1:{llm.port}/v1  (Ctrl+C 로 종료)")
        print(json.dumps(llm.provider_config(), indent=2))
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
