"""P8 검증: demo.py 의 시나리오를 그대로 실행해 기대한 로드 횟수가 나오는지 확인한다.

모델은 쓰지 않는다. 플러그인이 로드되면 마커 파일에 한 줄이 남고,
`opencode debug config` 가 플러그인 초기화까지 수행하므로 그것으로 충분하다.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import demo  # noqa: E402
from octest import check, finish  # noqa: E402

# 파일 자체 검사 (opencode 없이)
pkg = json.loads((demo.PACKAGE / "package.json").read_text(encoding="utf-8"))
check("패키지 package.json 에 name/main/exports 가 있다",
      pkg.get("name") == "opencode-hello" and pkg.get("main") == "./index.js" and "." in pkg.get("exports", {}))
check("패키지 index.js 는 plugins/hello.js 와 같은 내용이다",
      (demo.PACKAGE / "index.js").read_text(encoding="utf-8") == demo.HELLO.read_text(encoding="utf-8"))

opencode = demo.find_opencode()
for sc in demo.SCENARIOS:
    res = demo.run_scenario(sc, opencode)
    check(f"[{sc.id}] {sc.title}: 로드 {len(res['loaded'])}회 (기대 {sc.expect})",
          len(res["loaded"]) == sc.expect, json.dumps(res, ensure_ascii=False))
    if sc.check_shell_env:
        check(f"[{sc.id}] shell.env 훅이 bash 환경에 HELLO_LOADED=yes 를 넣었다",
              res.get("shell_env") is not None and "HELLO_LOADED=yes" in res["shell_env"], str(res.get("shell_env")))
    if sc.id == "c3":
        check("[c3] [경로, 옵션] 형태에서 플러그인이 옵션을 받았다", {"greeting": "안녕"} in res["options"], str(res["options"]))
    if sc.id == "x1":
        check("[x1] 함수가 아닌 값(export const X = 42)을 export 하면 파일 전체가 로드되지 않는다", len(res["loaded"]) == 0)
    if sc.id == "x2":
        check("[x2] 도우미 함수를 export 해도 진짜 플러그인은 여전히 로드된다", len(res["loaded"]) >= 1)
    if sc.id == "d3":
        check("[d3] npm 이름 형태는 캐시 폴더의 node_modules 에서 로드됐다",
              any("node_modules/opencode-hello" in src for src in res["loaded"]), str(res["loaded"]))
if demo._registry_state.get("server"):
    demo._registry_state["server"].shutdown()
finish()
