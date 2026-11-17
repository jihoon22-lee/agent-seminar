"""진짜 모델 서버를 대신하는 OpenAI 호환 모의 서버 (표준 라이브러리만 사용).

실제 모델이 아닙니다. 어떤 질문에도 같은 고정 문장을 돌려주고, 요청이 어떻게 도착했는지 기록합니다.
opencode 가 보낸 요청의 경로, Authorization 헤더가 있는지·기대한 값과 같은지, 모델 이름을 확인하는 데 씁니다.
실제 서비스의 주소와 키로 바꿔도 opencode.json 의 모양은 그대로입니다.

    python model_server.py                     (포트 8799, 기대하는 키 demo-token-123)
    python model_server.py --port 9000 --api-key my-demo-key --strict

  --strict   Authorization 이 기대한 값과 다르면 401 로 거절한다 (진짜 서비스가 하는 일). 기본은 기록만 하고 답한다.
  --log      기록 파일 (기본: 이 폴더의 logs/model_server.log)

기록 한 줄 예: 2026-11-17T07:38:36 POST /v1/chat/completions auth=match model=demo-chat stream=True tools=10
auth= 값: match(기대한 값과 같음) | mismatch(다름) | missing(헤더 없음). 키 값 자체는 기록하지 않습니다.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPLY = "[모의 서버] 이 문장은 model_server.py 가 돌려주는 고정 답변입니다. 실제 모델이 아닙니다."
DEFAULT_PORT = 8799
DEFAULT_KEY = "demo-token-123"
DEFAULT_LOG = Path(__file__).resolve().parent / "logs" / "model_server.log"


class ModelServer:
    def __init__(self, port: int = 0, api_key: str = DEFAULT_KEY, strict: bool = False, log_path: Path | None = None,
                 quiet: bool = False):
        self.quiet = quiet
        self.api_key = api_key
        self.strict = strict
        self.log_path = Path(log_path) if log_path else None
        self.requests: list[dict] = []   # 받은 요청 요약 (check.py 가 읽음)
        self._lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    body = {}
                outer._handle(self, body, "POST")

            def do_GET(self):  # noqa: N802
                outer._handle(self, {}, "GET")

            def log_message(self, *args):  # 표준 접속 로그는 끄고 우리 기록만 남긴다
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.port = self.server.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}/v1"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "ModelServer":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()

    # -- 기록 ----------------------------------------------------------------------
    def _auth_state(self, handler) -> str:
        header = handler.headers.get("Authorization")
        if header is None:
            return "missing"
        return "match" if header == f"Bearer {self.api_key}" else "mismatch"

    def _record(self, method: str, path: str, auth: str, body: dict) -> None:
        info = {"method": method, "path": path, "auth": auth, "model": body.get("model"),
                "stream": body.get("stream"), "tools": len(body.get("tools") or [])}
        line = (f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {method} {path} auth={auth} "
                f"model={info['model']} stream={info['stream']} tools={info['tools']}")
        with self._lock:
            self.requests.append(info)
            if not self.quiet:
                print(line, file=sys.stderr, flush=True)
            if self.log_path:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.log_path, "a", encoding="utf-8", newline="\n") as f:
                    f.write(line + "\n")

    # -- 응답 ----------------------------------------------------------------------
    def _handle(self, handler, body: dict, method: str) -> None:
        auth = self._auth_state(handler)
        self._record(method, handler.path, auth, body)
        if self.strict and auth != "match":
            self._json(handler, 401, {"error": {"message": "Incorrect API key provided",
                                                "type": "invalid_request_error", "code": "invalid_api_key"}})
        elif method == "GET" and handler.path.rstrip("/").endswith("/models"):
            self._json(handler, 200, {"object": "list", "data": [{"id": "demo-chat", "object": "model"}]})
        elif method == "POST" and handler.path.endswith("/chat/completions"):
            self._completion(handler, body)
        else:
            self._json(handler, 404, {"error": {"message": f"no route for {method} {handler.path}"}})

    @staticmethod
    def _json(handler, status: int, obj: dict) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def _completion(self, handler, body: dict) -> None:
        model = body.get("model") or "demo-chat"
        usage = {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18}
        base = {"id": "stand-in-1", "created": 0, "model": model}
        if not body.get("stream"):
            self._json(handler, 200, {**base, "object": "chat.completion", "usage": usage, "choices": [
                {"index": 0, "message": {"role": "assistant", "content": REPLY}, "finish_reason": "stop"}]})
            return
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.end_headers()

        def event(obj: dict) -> None:
            payload = json.dumps({**base, "object": "chat.completion.chunk", **obj}, ensure_ascii=False)
            handler.wfile.write(("data: " + payload + "\n\n").encode("utf-8"))
            handler.wfile.flush()

        event({"choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]})
        event({"choices": [{"index": 0, "delta": {"content": REPLY}, "finish_reason": None}]})
        event({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": usage})
        handler.wfile.write(b"data: [DONE]\n\n")
        handler.wfile.flush()


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="OpenAI 호환 모의 서버 (진짜 모델이 아님)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="0 이면 빈 포트를 잡고 주소를 출력")
    ap.add_argument("--api-key", default=DEFAULT_KEY, help="기대하는 키 (기본: demo-token-123)")
    ap.add_argument("--strict", action="store_true", help="키가 다르거나 없으면 401")
    ap.add_argument("--log", default=str(DEFAULT_LOG), help="기록 파일")
    args = ap.parse_args()
    with ModelServer(args.port, args.api_key, args.strict, Path(args.log)) as srv:
        print(f"모의 서버: {srv.base_url}  (Ctrl+C 로 종료)  기록: {args.log}", flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
