"""C7 검사: OpenAI 호환 provider 설정이 실제 요청(주소, Authorization, 모델 이름)으로 이어지는지 확인한다.

진짜 모델 대신 model_server.py(모의 서버)를 빈 포트에 띄워 쓴다. 인터넷도 레지스트리도 필요 없다.
(opencode 1.19.5 는 @ai-sdk/openai-compatible 을 내장하고 있어 첫 실행에도 내려받지 않는다. 아래 검사가 이를 확인한다.)
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
from model_server import REPLY, ModelServer  # noqa: E402
from octest import Sandbox, check, finish  # noqa: E402

PY = sys.executable
KEY = "demo-token-123"
cfg_text = (HERE / "opencode.json").read_text(encoding="utf-8")
cfg = json.loads(cfg_text)
prov = cfg["provider"]["demo-endpoint"]

# 1. opencode.json 자체
check("provider: npm 이 @ai-sdk/openai-compatible", prov["npm"] == "@ai-sdk/openai-compatible")
check("baseURL 과 apiKey 를 {env:...} 로 받음 (파일에 주소·키가 없음)",
      prov["options"] == {"baseURL": "{env:LLM_BASE_URL}", "apiKey": "{env:LLM_API_KEY}"}, str(prov["options"]))
check("모델 2개, 각각 limit.context/output", sorted(prov["models"]) == ["demo-chat", "demo-small"]
      and all({"context", "output"} <= set(m["limit"]) for m in prov["models"].values()))
check("기본 model 이 provider/모델 형식으로 등록된 모델을 가리킴",
      cfg["model"] == "demo-endpoint/demo-chat" and cfg["model"].split("/", 1)[1] in prov["models"])
check("실제 서비스 이름·키 모양이 파일에 없음",
      not re.search(r"openai\.com|anthropic|[A-Za-z0-9_]{32,}|https?://(?!127)", cfg_text.replace("https://opencode.ai/config.json", "")
                     + (HERE / "model_server.py").read_text(encoding="utf-8")))


def post(url: str, key: str | None, body: dict | None = None):
    req = urllib.request.Request(url, data=json.dumps(body or {"model": "m"}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# 2. model_server.py 자체
log = pathlib.Path(tempfile.mkdtemp(prefix="c7-log-")) / "sub" / "m.log"
with ModelServer(0, KEY, strict=False, log_path=log, quiet=True) as srv:
    status, data = post(srv.base_url + "/chat/completions", KEY, {"model": "demo-chat"})
    check("모의 서버: 고정 답변을 돌려줌", status == 200 and data["choices"][0]["message"]["content"] == REPLY, str(data))
    post(srv.base_url + "/chat/completions", "other-key")
    post(srv.base_url + "/chat/completions", None)
    check("모의 서버: Authorization 이 match / mismatch / missing 으로 기록됨",
          [r["auth"] for r in srv.requests] == ["match", "mismatch", "missing"], str(srv.requests))
    text = log.read_text(encoding="utf-8")
    check("모의 서버: 기록 파일에 경로·모델·auth 가 남고 키 값은 없음",
          "POST /v1/chat/completions auth=match model=demo-chat" in text and KEY not in text and "other-key" not in text, text)
with ModelServer(0, KEY, strict=True, quiet=True) as srv:
    status, data = post(srv.base_url + "/chat/completions", "other-key")
    check("모의 서버 --strict: 키가 다르면 401 + 'Incorrect API key provided'",
          status == 401 and data["error"]["message"] == "Incorrect API key provided", str(data))
    check("모의 서버 --strict: 맞는 키는 200", post(srv.base_url + "/chat/completions", KEY)[0] == 200)

cli_log = log.parent / "cli.log"
proc = subprocess.Popen([PY, str(HERE / "model_server.py"), "--port", "0", "--log", str(cli_log), "--api-key", "cli-key"],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
try:
    line = proc.stdout.readline()
    m = re.search(r"(http://127\.0\.0\.1:\d+/v1)", line)
    check("model_server.py 를 명령으로 실행하면 주소를 출력", bool(m), line)
    if m:
        post(m.group(1) + "/chat/completions", "cli-key")
        check("명령으로 띄운 서버도 --log 파일에 기록 (auth=match)",
              cli_log.exists() and "auth=match" in cli_log.read_text(encoding="utf-8"))
finally:
    proc.kill()
    proc.wait()
    proc.stdout.close()
    proc.stderr.close()

# 3. opencode 와 연결
with Sandbox("c7") as sb:
    for var in ("LLM_BASE_URL", "LLM_API_KEY"):
        sb.env.pop(var, None)
    DEAD = "http://127.0.0.1:1"  # 레지스트리를 닿지 않는 주소로 돌려 둔다: 내려받기가 필요하면 여기서 드러난다
    registry_off = {"NPM_CONFIG_REGISTRY": DEAD, "BUN_CONFIG_REGISTRY": DEAD}

    def env_for(srv, **extra):
        return {"PWD": str(HERE), "LLM_BASE_URL": srv.base_url, "LLM_API_KEY": KEY, **extra}

    with ModelServer(0, KEY, strict=True, quiet=True) as srv:
        # 첫 실행: 새 캐시 + 죽은 레지스트리
        first = sb.opencode(["run", "안녕"], HERE, timeout=120, extra_env=env_for(srv, **registry_off))
        check("첫 실행(새 캐시, 레지스트리 막힘)에서도 -m 없이 모의 서버의 답이 옴 -> @ai-sdk/openai-compatible 은 내려받지 않음",
              first.returncode == 0 and REPLY in first.stdout, first.stdout[-200:] + first.stderr[-300:])
        downloaded = [p for p in sb.root.rglob("openai-compatible*") if "node_modules" in p.parts or "@ai-sdk" in p.parts]
        check("첫 실행 뒤 opencode 캐시·데이터 폴더에 @ai-sdk 패키지가 없음", not downloaded, str(downloaded[:3]))
        main = [r for r in srv.requests if r["tools"]]
        check("서버가 받은 요청: POST /v1/chat/completions, Authorization 이 환경변수 값과 일치, model=demo-chat",
              bool(main) and main[0]["path"] == "/v1/chat/completions" and main[0]["auth"] == "match" and main[0]["model"] == "demo-chat", str(srv.requests))

        models = sb.opencode(["models"], HERE, extra_env=env_for(srv))
        check("opencode models: demo-endpoint/demo-chat, demo-endpoint/demo-small 이 목록에 있음",
              {"demo-endpoint/demo-chat", "demo-endpoint/demo-small"} <= set(models.stdout.split()), models.stdout[-300:])
        only = sb.opencode(["models", "demo-endpoint"], HERE, extra_env=env_for(srv))
        check("opencode models demo-endpoint: 그 provider 의 모델만 나옴",
              only.stdout.split() == ["demo-endpoint/demo-chat", "demo-endpoint/demo-small"], only.stdout)

        conf = sb.debug_config(HERE, extra_env=env_for(srv))
        opts = conf["provider"]["demo-endpoint"]["options"]
        check("debug config: baseURL 은 환경변수 값으로 치환되어 그대로 보이고, apiKey 는 *** 로 가려짐",
              opts["baseURL"] == srv.base_url and opts["apiKey"] == "***" and KEY not in json.dumps(conf), str(opts))
        check("debug config: 기본 model 이 demo-endpoint/demo-chat", conf.get("model") == "demo-endpoint/demo-chat")

        before = len(srv.requests)
        sb.opencode(["run", "-m", "demo-endpoint/demo-small", "안녕"], HERE, extra_env=env_for(srv))
        check("-m demo-endpoint/demo-small: 서버가 받은 model 이 demo-small",
              {r["model"] for r in srv.requests[before:]} == {"demo-small"}, str(srv.requests[before:]))

        # 실패 모습 1: 키가 틀림
        before = len(srv.requests)
        bad = sb.opencode(["run", "안녕"], HERE, extra_env=env_for(srv, LLM_API_KEY="wrong-key"))
        check("키가 틀리면: 서버는 auth=mismatch 를 기록하고, 화면에는 서버의 메시지 'Error: Incorrect API key provided' 만 나옴",
              bad.returncode == 1 and "Error: Incorrect API key provided" in bad.stderr
              and {r["auth"] for r in srv.requests[before:]} == {"mismatch"}, bad.stderr[-300:])
        # 실패 모습 2: 키 환경변수가 없음
        before = len(srv.requests)
        env = env_for(srv)
        del env["LLM_API_KEY"]
        unset = sb.opencode(["run", "안녕"], HERE, extra_env=env)
        check("LLM_API_KEY 가 없으면: 화면 메시지는 키가 틀렸을 때와 똑같지만, 서버에는 Authorization 헤더가 아예 없음(auth=missing)",
              unset.returncode == 1 and "Error: Incorrect API key provided" in unset.stderr
              and {r["auth"] for r in srv.requests[before:]} == {"missing"}, unset.stderr[-300:] + str(srv.requests[before:]))
        conf = sb.debug_config(HERE, extra_env=env)
        check("LLM_API_KEY 가 없어도 debug config 의 apiKey 는 똑같이 *** (설정 여부를 구분할 수 없음)",
              conf["provider"]["demo-endpoint"]["options"]["apiKey"] == "***")

    # 실패 모습 3: 주소 환경변수가 없음
    nourl = sb.opencode(["run", "안녕"], HERE, extra_env={"PWD": str(HERE), "LLM_API_KEY": KEY})
    check("LLM_BASE_URL 이 없으면: 'Error: Invalid URL' 로 실패 (종료 코드 1)",
          nourl.returncode == 1 and "Error: Invalid URL" in nourl.stderr, nourl.stderr[-300:])
    logs = sb.opencode(["run", "--print-logs", "--log-level", "ERROR", "안녕"], HERE, extra_env={"PWD": str(HERE), "LLM_API_KEY": KEY})
    check("--print-logs --log-level ERROR 로 보면 providerID=demo-endpoint 와 TypeError: Invalid URL 이 나옴",
          "providerID=demo-endpoint" in logs.stderr and "TypeError: Invalid URL" in logs.stderr, logs.stderr[-400:])
    conf = sb.debug_config(HERE, extra_env={"PWD": str(HERE), "LLM_API_KEY": KEY})
    check('debug config 에서 baseURL 이 "" (빈 문자열)로 보임 -- 없는 환경변수는 오류 없이 빈 문자열이 됨',
          conf["provider"]["demo-endpoint"]["options"]["baseURL"] == "", str(conf["provider"]["demo-endpoint"]["options"]))
    names = sb.opencode(["models", "demo-endpoint"], HERE, extra_env={"PWD": str(HERE)})
    check("환경변수가 없어도 opencode models 에는 모델이 그대로 나옴 (목록만으로는 연결 성공을 알 수 없음)",
          names.stdout.split() == ["demo-endpoint/demo-chat", "demo-endpoint/demo-small"], names.stdout)

    # baseURL 에 /v1 이 없으면: 경로는 baseURL 뒤에 /chat/completions 가 붙을 뿐이다
    with ModelServer(0, KEY, quiet=True) as srv:
        e = env_for(srv, LLM_BASE_URL=f"http://127.0.0.1:{srv.port}")
        sb.opencode(["run", "안녕"], HERE, extra_env=e)
        check("baseURL 뒤에 /chat/completions 가 그대로 붙음 (baseURL 이 /v1 로 끝나지 않으면 요청 경로에도 /v1 이 없음)",
              bool(srv.requests) and {r["path"] for r in srv.requests} == {"/chat/completions"}, str(srv.requests))

finish()
