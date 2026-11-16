"""C2 검사: {env:}, {file:} 치환, ${} 비치환, 마스킹, 그리고 값이 MCP 프로세스까지 실제로 도착하는지."""
import json
import os
import shutil
import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
from octest import Sandbox, check, finish, model_check, model_enabled, tool_called  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "out"
SECRETS = HERE / "secrets"
HAD_SECRETS = SECRETS.exists()  # 사용자가 미리 prepare.py 를 돌렸다면 지우지 않는다
ENV = {"DEMO_API_TOKEN": "demo-env-token-123", "DEMO_GREETING": "안녕", "DEMO_NAME": "세미나", "DEMO_USER": "alice"}

try:
    proc = subprocess.run([sys.executable, str(HERE / "prepare.py")], capture_output=True, timeout=60,
                          env={**os.environ, "PYTHONUTF8": "1"})
    check("prepare.py 정상 종료", proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace"))
    token_file = SECRETS / "token.txt"
    check("prepare.py: 가짜 토큰 파일 생성", token_file.read_text(encoding="utf-8").strip() == "demo-file-token-456")

    data = json.loads((HERE / "opencode.json").read_text(encoding="utf-8"))
    check("opencode.json: model 키 없음, $schema 있음", "model" not in data and "$schema" in data)

    with Sandbox("c2") as sb:
        for name in list(sb.env):
            if name.startswith("DEMO_"):
                del sb.env[name]  # 실행하는 사람의 환경변수가 새어 들어오지 않게

        # 1. 환경변수를 모두 준 경우
        cfg = sb.debug_config(HERE, extra_env=ENV)
        env_block = cfg["mcp"]["env-probe"]["environment"]
        check("username: {env:DEMO_USER} 치환", cfg["username"] == "alice", str(cfg["username"]))
        check("{env:} + 텍스트 조합 치환", env_block["GREETING"] == "안녕, 세미나", str(env_block))
        check("${NAME} 는 치환되지 않고 글자 그대로", env_block["SHELL_STYLE"] == "${DEMO_API_TOKEN}", str(env_block))
        check("없는 환경변수는 빈 문자열", env_block["UNSET_VALUE"] == "", str(env_block))
        check("이름에 TOKEN 이 든 environment 값은 *** 로 마스킹 (env/file 모두)",
              env_block["DEMO_API_TOKEN"] == "***" and env_block["FILE_TOKEN"] == "***", str(env_block))
        check("그 밖의 이름은 마스킹되지 않음 (GREETING, PLAIN_NOTE)", env_block["PLAIN_NOTE"] == "just-a-literal")
        headers = cfg["mcp"]["remote-demo"]["headers"]
        check("remote headers 는 값이 전부 ***", set(headers.values()) == {"***"}, str(headers))

        # 2. 아무것도 안 준 경우
        cfg = sb.debug_config(HERE)
        env_block = cfg["mcp"]["env-probe"]["environment"]
        check("DEMO_USER 미설정이면 username 은 빈 문자열 -> 기본값(OS 사용자)으로 대체",
              cfg["username"] not in ("", "{env:DEMO_USER}"), str(cfg["username"]))
        check("미설정 토큰도 *** 로 보임 (마스킹 때문에 설정 여부를 구분할 수 없음)",
              env_block["DEMO_API_TOKEN"] == "***")
        check("미설정 조합 값: ', ' (빈 문자열 두 개)", env_block["GREETING"] == ", ", str(env_block))

        # 3. 없는 파일은 빈 문자열이 아니라 오류
        proc = sb.opencode(["debug", "config"], HERE,
                           extra_env={"OPENCODE_CONFIG_CONTENT": json.dumps({"username": "{file:no-such-file.txt}"})})
        check("{file:없는파일} 은 설정 오류", "bad file reference" in (proc.stderr + proc.stdout), proc.stderr[-300:])

        # 4. 값이 MCP 프로세스까지 도착했는지 (모델 없이): mcp list 가 서버를 띄우고, 서버가 받은 값을 기록
        shutil.rmtree(OUT, ignore_errors=True)
        status = sb.mcp_list(HERE, extra_env=ENV)
        check("mcp list: env-probe connected", status.get("env-probe") == "connected", str(status))
        received = json.loads((OUT / "received.json").read_text(encoding="utf-8"))
        check("프로세스는 마스킹 전 진짜 값을 받음", received["DEMO_API_TOKEN"] == "demo-env-token-123", str(received))
        check("프로세스가 받은 {file:} 값 (줄바꿈 제거됨)", received["FILE_TOKEN"] == "demo-file-token-456", str(received))
        check("프로세스가 받은 ${NAME} 은 글자 그대로", received["SHELL_STYLE"] == "${DEMO_API_TOKEN}")

        shutil.rmtree(OUT, ignore_errors=True)
        sb.mcp_list(HERE)
        received = json.loads((OUT / "received.json").read_text(encoding="utf-8"))
        check("미설정 {env:} 는 프로세스에 빈 문자열로 도착 (변수 없음 아님)", received["DEMO_API_TOKEN"] == "", str(received))

        if model_enabled():
            shutil.rmtree(OUT, ignore_errors=True)
            out = sb.run_model("env-probe_env_report 도구를 호출하고, 돌려받은 JSON 을 그대로 보여 주세요.", HERE,
                               extra_env=ENV)
            model_check("모델이 env_report 도구를 호출", out, tool_called(out, "env_report"))
            model_check("응답에 환경변수로 준 토큰 값이 나타남", out, "demo-env-token-123" in out)
finally:
    shutil.rmtree(OUT, ignore_errors=True)
    if not HAD_SECRETS:
        shutil.rmtree(SECRETS, ignore_errors=True)
finish()
