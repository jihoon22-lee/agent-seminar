"""현재 셸에 주입된 환경변수를 출력합니다. (에이전트에게 시키기 전/후를 비교하는 용도)

    python show_env.py        (Linux에서 python 명령이 없으면 python3)
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

for name in ("APP_ENV", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "REQUESTS_CA_BUNDLE"):
    print(f"{name}={os.environ.get(name)}")
