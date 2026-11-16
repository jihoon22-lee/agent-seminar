"""공용 도우미 (표준 라이브러리만 사용, Python 3.10+).

demo.py / show_prompt.py / compare.py 처럼 "도구 없이 혼자 실행되는" 스크립트가 쓰는 작은 샌드박스입니다.
  - 임시 폴더에 XDG 디렉터리를 만들어 내 진짜 opencode 설정·세션을 건드리지 않습니다.
  - 내 PC의 ~/.claude/skills, ~/.agents/skills 는 보지 않도록 OPENCODE_DISABLE_EXTERNAL_SKILLS=1 을 줍니다.
  - opencode run 은 프로세스의 현재 폴더가 아니라 환경변수 PWD 를 작업 폴더로 삼기 때문에
    cwd 를 바꿀 때 PWD 도 같이 맞춰 줍니다 (1.19.5에서 확인).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # Windows 콘솔 기본값은 cp949
    except AttributeError:
        pass

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def find_opencode() -> str:
    explicit = os.environ.get("OPENCODE_BIN")
    if explicit:
        return explicit
    found = shutil.which("opencode")
    if not found:
        raise SystemExit("opencode 를 PATH 에서 찾지 못했습니다 (OPENCODE_BIN 으로 경로를 지정할 수 있습니다)")
    return found


def rmtree_force(path: Path | str) -> None:
    """임시 폴더 삭제. Windows 에서는 git 객체 파일이 읽기 전용이라 그냥 지우면 남으므로 권한을 풀고 지웁니다."""
    import stat

    def _retry(func, target, *_):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_retry)
    else:
        shutil.rmtree(path, onerror=_retry)


class Sandbox:
    """임시 XDG 디렉터리를 쓰는 격리 환경. `with Sandbox() as sb:` 로 사용."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="agent-seminar-lab-"))
        self.config_dir = self.root / "config" / "opencode"  # 여기가 "전역" 설정 폴더
        self.config_dir.mkdir(parents=True)
        (self.config_dir / "opencode.json").write_text(
            json.dumps({"$schema": "https://opencode.ai/config.json", "autoupdate": False}), encoding="utf-8")
        self.env = dict(os.environ)
        self.env.update({
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_DATA_HOME": str(self.root / "data"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "XDG_STATE_HOME": str(self.root / "state"),
            "OPENCODE_DISABLE_AUTOUPDATE": "1",
            "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
            "PYTHONUTF8": "1",
        })
        for key in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG_DIR"):
            self.env.pop(key, None)
        self.bin = find_opencode()
        self._n = 0

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc: object) -> None:
        rmtree_force(self.root)

    def opencode(self, args: list[str], cwd: Path | str, overlay: dict | None = None, timeout: int = 180,
                 extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        return run_opencode(self.bin, self.env, args, cwd, overlay=overlay, timeout=timeout,
                            extra_env=extra_env, scratch=self.root)

    def skills(self, cwd: Path | str, overlay: dict | None = None) -> list[dict]:
        """`opencode debug skill` 결과(JSON). 항상 들어 있는 내장 스킬 customize-opencode 는 뺍니다."""
        proc = self.opencode(["debug", "skill"], cwd, overlay=overlay)
        return [s for s in parse_json(proc.stdout) if s["name"] != "customize-opencode"]


def run_opencode(binary: str, env: dict[str, str], args: list[str], cwd: Path | str, overlay: dict | None = None,
                 timeout: int = 180, extra_env: dict[str, str] | None = None,
                 scratch: Path | None = None) -> subprocess.CompletedProcess:
    """opencode 한 번 실행. 출력은 파일로 받아 읽습니다(파이프로 큰 출력을 읽으면 잘릴 수 있음)."""
    env = dict(env)
    env["PWD"] = str(cwd)  # 중요: opencode run 은 cwd 가 아니라 PWD 를 봅니다
    if overlay:
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(overlay)  # 맨 마지막에 병합되는 설정 덧씌우기
    env.update(extra_env or {})
    tmp = Path(tempfile.mkdtemp(prefix="oc-out-", dir=str(scratch) if scratch else None))
    try:
        with open(tmp / "out", "wb") as out, open(tmp / "err", "wb") as err:
            code = subprocess.run([binary, *args], cwd=str(cwd), env=env, stdout=out, stderr=err,
                                  timeout=timeout, stdin=subprocess.DEVNULL).returncode
        text = lambda name: ANSI_RE.sub("", (tmp / name).read_bytes().decode("utf-8", errors="replace"))
        return subprocess.CompletedProcess([binary, *args], code, text("out"), text("err"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def parse_json(text: str):
    text = text.strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise RuntimeError(f"JSON 이 없습니다: {text[:300]}")
    return json.loads(text[start:])


class model_lock:
    """AGENT_SEMINAR_MODEL_LOCK 이 있을 때만 모델 호출을 한 줄로 세웁니다(공용 무료 모델 보호용, 평소엔 아무 일도 안 함)."""

    def __init__(self) -> None:
        self.path = os.environ.get("AGENT_SEMINAR_MODEL_LOCK")
        self.fd = None

    def __enter__(self) -> None:
        if not self.path:
            return
        deadline = time.time() + 6 * 3600
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > 600:
                        os.remove(self.path)
                        continue
                except OSError:
                    pass
                if time.time() > deadline:
                    raise RuntimeError("model lock wait exceeded 6 hours")
                time.sleep(3)

    def __exit__(self, *exc: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
            try:
                os.remove(self.path)
            except OSError:
                pass


def run_model(sb: Sandbox, prompt: str, cwd: Path | str, model: str, timeout: int = 420, auto: bool = True,
              extra_args: list[str] | None = None) -> str:
    """진짜 모델로 `opencode run` 한 번. 대화 기록(stdout+stderr)을 돌려줍니다."""
    args = ["run", "-m", model] + (["--auto"] if auto else []) + (extra_args or []) + [prompt]
    with model_lock():
        try:
            proc = sb.opencode(args, cwd, timeout=timeout)
        except subprocess.TimeoutExpired:
            return "<<timeout>>"
    return proc.stdout + "\n" + proc.stderr


def short(path: str, base: Path | str | None = None) -> str:
    """표에 찍을 때 긴 경로를 줄입니다."""
    p = str(path)
    if base:
        b = str(base)
        if p.startswith(b):
            return "." + p[len(b):].replace("\\", "/")
    return p.replace("\\", "/")
