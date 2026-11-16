"""P8 데모: 같은 플러그인(hello.js)을 여러 방법으로 로드하고, 어느 쪽이 실제로 로드됐는지 표로 보여 준다.

    python demo.py            # 모든 시나리오 실행
    python demo.py a c1 pure  # 골라서 실행 (id 는 아래 SCENARIOS 참고)
    python demo.py --list     # 시나리오 목록
    python demo.py --keep     # 임시 폴더를 지우지 않고 남긴다 (직접 들여다보고 싶을 때)

안전 장치: 시나리오마다 새 임시 폴더와 임시 XDG 폴더를 만들고 거기서만 opencode 를 실행한다.
내 실제 ~/.config/opencode 는 읽지도 쓰지도 않는다. ('b' 시나리오의 "전역 플러그인 폴더"도 임시 XDG 폴더 안이다.)
표준 라이브러리만 사용한다. Linux 에서 python 명령이 없으면 python3 로 실행하세요.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

HERE = Path(__file__).resolve().parent
HELLO = HERE / "plugins" / "hello.js"
PACKAGE = HERE / "packages" / "opencode-hello"


# --------------------------------------------------------------------------- 환경
def find_opencode() -> str:
    found = os.environ.get("OPENCODE_BIN") or shutil.which("opencode")
    if not found:
        raise SystemExit("opencode 를 찾을 수 없습니다. PATH 를 확인하거나 OPENCODE_BIN 을 지정하세요.")
    return found


class Env:
    """임시 XDG 폴더 한 벌. 시나리오마다 새로 만든다."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="p8-demo-"))
        self.config_dir = self.root / "xdg-config" / "opencode"   # '전역' 설정 폴더 (진짜 홈이 아님)
        self.config_dir.mkdir(parents=True)
        (self.config_dir / "opencode.json").write_text(
            json.dumps({"$schema": "https://opencode.ai/config.json", "autoupdate": False}), encoding="utf-8")
        self.project = self.root / "project"
        self.project.mkdir()
        self.marker = self.root / "marker.log"
        self.vars = dict(os.environ)
        self.vars.update({
            "XDG_CONFIG_HOME": str(self.root / "xdg-config"),
            "XDG_DATA_HOME": str(self.root / "xdg-data"),
            "XDG_CACHE_HOME": str(self.root / "xdg-cache"),
            "XDG_STATE_HOME": str(self.root / "xdg-state"),
            "OPENCODE_DISABLE_AUTOUPDATE": "1",
            "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
            "HELLO_MARKER": str(self.marker),
        })
        for key in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG_DIR", "OPENCODE_PURE"):
            self.vars.pop(key, None)

    def write_config(self, cfg: dict) -> None:
        data = {"$schema": "https://opencode.ai/config.json", **cfg}
        (self.project / "opencode.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    def copy_to(self, rel: str, src: Path) -> Path:
        dst = self.project / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return dst

    def markers(self) -> list[dict]:
        if not self.marker.is_file():
            return []
        return [json.loads(line) for line in self.marker.read_text(encoding="utf-8").splitlines() if line.strip()]

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def _out(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout.decode("utf-8", errors="replace")


def resolved_plugins(env: Env, opencode: str, extra_args: list[str] | None = None) -> tuple[list, str]:
    """`opencode debug config` 를 실행한다. 이 명령도 플러그인을 로드한다. (plugin 항목, 원문 일부) 를 돌려준다."""
    proc = subprocess.run([opencode, *(extra_args or []), "debug", "config"], cwd=env.project, env=env.vars,
                          capture_output=True, timeout=240, stdin=subprocess.DEVNULL)
    text = _out(proc)
    try:
        cfg = json.loads(text[text.index("{"):])
        return cfg.get("plugin", []), ""
    except (ValueError, json.JSONDecodeError):
        return [], text[:300] + proc.stderr.decode("utf-8", errors="replace")[:300]


# --------------------------------------------------------------------------- shell.env 확인
def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def shell_env_value(env: Env, opencode: str, extra_args: list[str] | None = None) -> str | None:
    """opencode serve 를 띄우고, 모델 없이 세션 shell API 로 `echo $HELLO_LOADED` 를 실행해 shell.env 훅을 확인한다.

    bash 도구가 실행하는 명령의 환경 변수에 플러그인이 넣은 값이 보이는지 보는 것이다.
    """
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen([opencode, *(extra_args or []), "serve", "--port", str(port), "--hostname", "127.0.0.1"],
                            cwd=env.project, env=env.vars, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def call(method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(base + path, method=method, headers={"Content-Type": "application/json"},
                                     data=json.dumps(body).encode() if body is not None else None)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8") or "null")

    try:
        for _ in range(120):
            try:
                call("GET", "/experimental/tool/ids")
                break
            except Exception:
                time.sleep(1)
        else:
            return None
        sid = call("POST", "/session", {})["id"]
        # Windows 의 bash 도구는 PowerShell 일 수도, Git Bash 일 수도 있어서 셸 문법에 의존하지 않는 python 으로 읽는다.
        cmd = ("echo HELLO_LOADED=$HELLO_LOADED" if os.name != "nt" else
               "python -c \"import os; print('HELLO_LOADED=' + str(os.environ.get('HELLO_LOADED')))\"")
        res = call("POST", f"/session/{sid}/shell", {"agent": "build", "command": cmd})
        for part in res.get("parts", []):
            if part.get("type") == "tool":
                return part["state"].get("output", "").strip()
        return None
    except Exception as exc:  # noqa: BLE001
        return f"(실패: {exc})"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# --------------------------------------------------------------------------- 가짜 레지스트리
_registry_state: dict = {}


def start_registry() -> str:
    """mini_registry.py 를 같은 프로세스의 스레드로 띄우고 주소를 돌려준다."""
    if "url" in _registry_state:
        return _registry_state["url"]
    sys.path.insert(0, str(HERE))
    import mini_registry  # noqa: PLC0415
    from http.server import ThreadingHTTPServer  # noqa: PLC0415

    port = free_port()
    mini_registry.Registry.base_url = f"http://127.0.0.1:{port}"
    server = ThreadingHTTPServer(("127.0.0.1", port), mini_registry.Registry)
    mini_registry.Registry.log_message = lambda self, fmt, *a: None  # 데모 출력이 길어지지 않게
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _registry_state.update(url=f"http://127.0.0.1:{port}/", server=server)
    return _registry_state["url"]


# --------------------------------------------------------------------------- 시나리오
@dataclass
class Scenario:
    id: str
    title: str
    how: str                                   # 사람이 읽는 설명
    setup: Callable[[Env], None]
    expect: int                                # 기대하는 로드 횟수
    extra_args: list[str] = field(default_factory=list)
    extra_env: dict[str, str] = field(default_factory=dict)
    check_shell_env: bool = False


def setup_a(env: Env) -> None:
    env.copy_to(".opencode/plugins/hello.js", HELLO)


def setup_b(env: Env) -> None:
    # 프로젝트에는 아무것도 없고, '전역 플러그인 폴더'(= 임시 XDG_CONFIG_HOME/opencode/plugins)에만 둔다.
    dst = env.config_dir / "plugins"
    dst.mkdir()
    shutil.copy2(HELLO, dst / "hello.js")


def setup_c1(env: Env) -> None:
    env.copy_to("plugins/hello.js", HELLO)
    env.write_config({"plugin": ["./plugins/hello.js"]})


def setup_c2(env: Env) -> None:
    dst = env.copy_to("plugins/hello.js", HELLO)
    env.write_config({"plugin": [dst.resolve().as_uri()]})            # file:///절대/경로


def setup_c3(env: Env) -> None:
    env.copy_to("plugins/hello.js", HELLO)
    env.write_config({"plugin": [["./plugins/hello.js", {"greeting": "안녕"}]]})   # [경로, 옵션] 형태


def setup_d1(env: Env) -> None:
    env.copy_to("packages/opencode-hello", PACKAGE)
    env.write_config({"plugin": ["./packages/opencode-hello"]})       # package.json 이 있는 폴더


def setup_d2(env: Env) -> None:
    dst = env.copy_to("packages/opencode-hello", PACKAGE)
    env.write_config({"plugin": [dst.resolve().as_uri()]})            # file:///.../packages/opencode-hello


def setup_d3(env: Env) -> None:
    url = start_registry()
    env.vars["npm_config_registry"] = url                             # .npmrc 의 registry= 와 같은 효과
    env.write_config({"plugin": ["opencode-hello@1.0.0"]})            # npm 이름 형태


def setup_e1(env: Env) -> None:
    env.copy_to("plugins/hello.js", HELLO)
    env.write_config({"plugin": ["./plugins/hello.js", "./plugins/hello.js"]})


def setup_e2(env: Env) -> None:
    dst = env.copy_to("plugins/hello.js", HELLO)
    env.write_config({"plugin": ["./plugins/hello.js", dst.resolve().as_uri()]})


def setup_e3(env: Env) -> None:
    env.copy_to(".opencode/plugins/hello.js", HELLO)                  # 자동 탐색 + 설정 파일에서 같은 파일 또 지정
    env.write_config({"plugin": ["./.opencode/plugins/hello.js"]})


def setup_e4(env: Env) -> None:
    env.copy_to(".opencode/plugins/hello.js", HELLO)                  # 파일 위치가 다르면 같은 내용이어도 별개 플러그인
    env.copy_to("plugins/hello.js", HELLO)
    env.write_config({"plugin": ["./plugins/hello.js"]})


def setup_f1(env: Env) -> None:
    setup_a(env)
    setup_b(env)
    env.copy_to("plugins/hello.js", HELLO)
    env.write_config({"plugin": ["./plugins/hello.js"]})


SCENARIOS: list[Scenario] = [
    Scenario("a", "(a) 자동 탐색", ".opencode/plugins/hello.js 에 파일만 두기", setup_a, 1, check_shell_env=True),
    Scenario("b", "(b) 전역 폴더", "<XDG_CONFIG_HOME>/opencode/plugins/hello.js (임시 XDG 안)", setup_b, 1),
    Scenario("c1", "(c) 상대 경로", 'opencode.json: "plugin": ["./plugins/hello.js"]', setup_c1, 1),
    Scenario("c2", "(c) file:/// 절대 경로", 'opencode.json: "plugin": ["file:///.../plugins/hello.js"]', setup_c2, 1),
    Scenario("c3", "(c) [경로, 옵션]", 'opencode.json: "plugin": [["./plugins/hello.js", {...}]]', setup_c3, 1),
    Scenario("d1", "(d) 패키지 폴더(상대 경로)", 'opencode.json: "plugin": ["./packages/opencode-hello"]', setup_d1, 1),
    Scenario("d2", "(d) 패키지 폴더(file:///)", 'opencode.json: "plugin": ["file:///.../packages/opencode-hello"]', setup_d2, 1),
    Scenario("d3", "(d) npm 이름 + 패키지 미러", 'opencode.json: "plugin": ["opencode-hello@1.0.0"] + registry 주소 지정',
             setup_d3, 1),
    Scenario("e1", "중복: 같은 경로 두 번", '"plugin": ["./plugins/hello.js", "./plugins/hello.js"]', setup_e1, 1),
    Scenario("e2", "중복: 상대 경로 + 절대 경로", '"plugin": ["./plugins/hello.js", "file:///.../plugins/hello.js"]', setup_e2, 1),
    Scenario("e3", "중복: 자동 탐색 + 설정에서 같은 파일", '.opencode/plugins/hello.js + "plugin": ["./.opencode/plugins/hello.js"]', setup_e3, 1),
    Scenario("e4", "중복: 같은 내용, 다른 위치의 파일 2개", ".opencode/plugins/hello.js + plugins/hello.js(설정에서 지정)", setup_e4, 2),
    Scenario("f1", "자동 + 전역 + 설정 모두 켜기", "세 위치에 모두 두기", setup_f1, 3),
    Scenario("pure", "--pure", "f1 과 같은 구성으로 opencode --pure 실행", setup_f1, 0, extra_args=["--pure"]),
]


def short(url: str) -> str:
    """마커에 찍힌 file:// 주소를 읽기 좋게 줄인다."""
    text = url.replace("file:///", "")
    for key in ("xdg-cache/opencode/packages/", "xdg-config/opencode/", "project/"):
        if key in text:
            return key.rstrip("/") + "/" + text.split(key, 1)[1]
    return text


def run_scenario(sc: Scenario, opencode: str, keep: bool = False) -> dict:
    res = _run_once(sc, opencode, keep)
    if sc.id == "d3" and not res["loaded"]:
        # npm 이름 형태는 첫 실행에서 패키지를 내려받는다. Windows 에서 아주 가끔 첫 시도에 0회로 끝나서 한 번 더 시도한다.
        print("  (npm 설치가 늦어 0회 — 한 번 더 시도합니다)")
        res = _run_once(sc, opencode, keep)
        res["retried"] = True
    return res


def _run_once(sc: Scenario, opencode: str, keep: bool = False) -> dict:
    env = Env()
    env.vars.update(sc.extra_env)
    try:
        sc.setup(env)
        t0 = time.time()
        plugin_cfg, err = resolved_plugins(env, opencode, sc.extra_args)
        loaded = env.markers()
        result = {
            "id": sc.id, "title": sc.title, "how": sc.how, "expect": sc.expect,
            "config_plugin": plugin_cfg, "loaded": [m["loadedFrom"] for m in loaded],
            "options": [m.get("options") for m in loaded], "seconds": round(time.time() - t0, 1), "error": err,
        }
        if sc.check_shell_env:
            result["shell_env"] = shell_env_value(env, opencode, sc.extra_args)
        return result
    finally:
        if keep:
            print(f"  (남겨 둔 폴더: {env.root})")
        else:
            env.cleanup()


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--list" in sys.argv:
        for sc in SCENARIOS:
            print(f"{sc.id:5} {sc.title:32} {sc.how}")
        return 0
    chosen = [sc for sc in SCENARIOS if not args or sc.id in args]
    if not chosen:
        print("알 수 없는 시나리오입니다. --list 로 목록을 확인하세요.")
        return 2
    opencode = find_opencode()
    print(f"opencode: {opencode}\n")
    failures = 0
    for sc in chosen:
        res = run_scenario(sc, opencode, keep="--keep" in sys.argv)
        ok = len(res["loaded"]) == sc.expect
        failures += 0 if ok else 1
        print(f"[{'OK' if ok else '!!'}] {sc.id:5} {sc.title}  ({res['seconds']}s)")
        print(f"       방법    : {sc.how}")
        print(f"       로드 횟수: {len(res['loaded'])} (기대 {sc.expect})")
        for src in res["loaded"]:
            print(f"       - {short(src)}")
        if sc.extra_args:
            print(f"       옵션    : opencode {' '.join(sc.extra_args)}")
            print(f"       설정에는 플러그인 {len(res['config_plugin'])}개가 적혀 있지만 실행되지 않음")
        given = [o for o in res["options"] if o]
        if given:
            print(f"       플러그인이 받은 옵션: {given[0]}")
        if res.get("shell_env") is not None:
            print(f"       shell.env 확인: {res['shell_env']}")
        if res["error"]:
            print(f"       오류: {res['error']}")
        print()
    srv = _registry_state.get("server")
    if srv:
        srv.shutdown()
    print(f"== {len(chosen)} 시나리오, 기대와 다른 것 {failures}개")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
