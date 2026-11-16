"""Shared helpers for example checks (Python 3.10+ standard library only).

Every opencode invocation runs inside an isolated sandbox:
XDG_CONFIG_HOME / XDG_DATA_HOME / XDG_CACHE_HOME / XDG_STATE_HOME point to a
temporary directory, so the user's real opencode config, sessions and
credentials are never read or modified.

Usage inside an example's check.py:

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "tools"))
    from octest import Sandbox, check, finish, model_enabled

    HERE = pathlib.Path(__file__).resolve().parent

    with Sandbox("s1a") as sb:
        skills = sb.debug_skills(cwd=HERE)
        check("skill discovered", any(s["name"] == "commit-message" for s in skills))
        if model_enabled():
            out = sb.run_model("...", cwd=HERE)
            check("model used the skill", "..." in out, soft=True)
    finish()

Environment variables:
    OPENCODE_BIN               path to the opencode executable (default: found on PATH)
    AGENT_SEMINAR_MODEL        model for model checks (default: opencode/big-pickle)
    AGENT_SEMINAR_MODEL_CHECKS set to 1 to run checks that call a model
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_MODEL = os.environ.get("AGENT_SEMINAR_MODEL", "opencode/big-pickle")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

_results: list[tuple[str, bool, bool]] = []  # (label, ok, soft)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp949
    except AttributeError:
        pass


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def model_enabled() -> bool:
    return os.environ.get("AGENT_SEMINAR_MODEL_CHECKS") == "1" or "--model" in sys.argv


def check(label: str, ok: bool, detail: str = "", soft: bool = False) -> bool:
    """Record one check. soft=True marks model-dependent checks (reported, never fatal)."""
    tag = "PASS" if ok else ("WARN" if soft else "FAIL")
    line = f"[{tag}] {label}"
    if detail and not ok:
        line += f"\n       {detail[:800]}"
    print(line, flush=True)
    _results.append((label, ok, soft))
    return ok


def finish() -> None:
    """Print a summary and exit non-zero if any hard check failed."""
    hard_fail = [label for label, ok, soft in _results if not ok and not soft]
    soft_fail = [label for label, ok, soft in _results if not ok and soft]
    print(f"== {len(_results)} checks, {len(hard_fail)} failed, {len(soft_fail)} warnings", flush=True)
    sys.exit(1 if hard_fail else 0)


def find_opencode() -> str:
    explicit = os.environ.get("OPENCODE_BIN")
    if explicit:
        return explicit
    found = shutil.which("opencode")
    if not found:
        raise SystemExit("opencode not found on PATH (set OPENCODE_BIN)")
    return found


class Sandbox:
    """Isolated opencode environment. Use as a context manager."""

    def __init__(self, name: str, global_config: dict[str, Any] | None = None, keep: bool = False):
        self.name = name
        self.keep = keep
        self._calls = 0
        self.root = Path(tempfile.mkdtemp(prefix=f"agent-seminar-{name}-"))
        self.config_home = self.root / "config"
        self.opencode_config_dir = self.config_home / "opencode"
        self.opencode_config_dir.mkdir(parents=True)
        cfg = {"$schema": "https://opencode.ai/config.json", "autoupdate": False}
        cfg.update(global_config or {})
        self.write_global_config(cfg)
        shim = self.root / "bin"
        shim.mkdir()
        if os.name != "nt":
            # Linux often has only `python3`; examples call `python` (the Windows default).
            (shim / "python").symlink_to(sys.executable)
        path = os.pathsep.join([str(shim), str(Path(sys.executable).parent), os.environ.get("PATH", "")])
        self.env = dict(os.environ)
        self.env.update(
            {
                "XDG_CONFIG_HOME": str(self.config_home),
                "XDG_DATA_HOME": str(self.root / "data"),
                "XDG_CACHE_HOME": str(self.root / "cache"),
                "XDG_STATE_HOME": str(self.root / "state"),
                "OPENCODE_DISABLE_AUTOUPDATE": "1",
                # Hide ~/.claude/skills and ~/.agents/skills of the person running the checks.
                "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
                "PYTHONUTF8": "1",
                "PATH": path,
            }
        )
        for key in ("OPENCODE_CONFIG", "OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG_DIR"):
            self.env.pop(key, None)
        self.bin = find_opencode()

    # -- lifecycle -----------------------------------------------------------
    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc: object) -> None:
        if not self.keep:
            shutil.rmtree(self.root, ignore_errors=True)

    # -- config --------------------------------------------------------------
    def write_global_config(self, cfg: dict[str, Any]) -> Path:
        path = self.opencode_config_dir / "opencode.json"
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    # -- running opencode ------------------------------------------------------
    def opencode(self, args: list[str], cwd: Path | str, timeout: int = 180,
                 extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        env = dict(self.env)
        env.update(extra_env or {})
        # Large outputs (e.g. `debug skill`) get truncated when read through a pipe,
        # so stdout/stderr go to files and are read back afterwards.
        self._calls += 1
        out_path = self.root / f"out-{self._calls}.txt"
        err_path = self.root / f"err-{self._calls}.txt"
        with open(out_path, "wb") as out, open(err_path, "wb") as err:
            code = subprocess.run(
                [self.bin, *args], cwd=str(cwd), env=env, stdout=out, stderr=err,
                timeout=timeout, stdin=subprocess.DEVNULL,
            ).returncode
        stdout = strip_ansi(out_path.read_bytes().decode("utf-8", errors="replace"))
        stderr = strip_ansi(err_path.read_bytes().decode("utf-8", errors="replace"))
        return subprocess.CompletedProcess([self.bin, *args], code, stdout, stderr)

    def debug_config(self, cwd: Path | str, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
        proc = self.opencode(["debug", "config"], cwd, timeout=120, extra_env=extra_env)
        return _parse_json(proc)

    def debug_skills(self, cwd: Path | str, extra_env: dict[str, str] | None = None) -> list[dict[str, Any]]:
        proc = self.opencode(["debug", "skill"], cwd, timeout=120, extra_env=extra_env)
        return _parse_json(proc)

    def mcp_list(self, cwd: Path | str, extra_env: dict[str, str] | None = None) -> dict[str, str]:
        """Return {server_name: 'connected' | 'failed' | 'disabled' | ...}."""
        proc = self.opencode(["mcp", "list"], cwd, timeout=240, extra_env=extra_env)
        status: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            # e.g. "●  ✓ glossary connected" / "●  ✗ broken failed"
            m = re.search(r"[✓✗○⚠]\s+(\S+)\s+(.+)$", line.strip())
            if m:
                status[m.group(1)] = m.group(2).strip()
        return status

    def run_model(self, prompt: str, cwd: Path | str, model: str | None = None, auto: bool = True,
                  timeout: int = 420, extra_env: dict[str, str] | None = None) -> str:
        """Run one non-interactive prompt. Returns stdout+stderr (ANSI stripped).

        Returns MODEL_UNAVAILABLE when the provider refuses (quota / rate limit), so callers can
        report "unverified" instead of a behavioural failure. In the transcript:
          → Skill "name"              a skill was loaded        (see skill_loaded)
          ⚙ server_tool {...}         an MCP / custom tool call (see tool_called)
        """
        args = ["run", "-m", model or DEFAULT_MODEL]
        if auto:
            args.append("--auto")
        args.append(prompt)
        with _model_lock():
            try:
                proc = self.opencode(args, cwd, timeout=timeout, extra_env=extra_env)
            except subprocess.TimeoutExpired:
                return "<<timeout>>"
        out = proc.stdout + "\n" + proc.stderr
        if RATE_LIMIT_RE.search(out):
            return MODEL_UNAVAILABLE + "\n" + out
        return out


MODEL_UNAVAILABLE = "<<model-unavailable>>"
RATE_LIMIT_RE = re.compile(r"FreeTierError|rate.?limit|\b429\b|\b403\b.*(forbidden|quota)|quota exceeded", re.I)


def skill_loaded(transcript: str, name: str) -> bool:
    return f'Skill "{name}"' in transcript


def tool_called(transcript: str, name: str) -> bool:
    """True if the transcript shows a call to a tool whose name contains `name`."""
    return any(name in line for line in transcript.splitlines() if line.lstrip().startswith(("⚙", "→")))


def model_check(label: str, transcript: str, ok: bool) -> bool:
    """Soft check that reports provider refusals separately from behavioural misses."""
    if transcript.startswith(MODEL_UNAVAILABLE):
        print(f"[SKIP] {label} (model unavailable: quota/rate limit — unverified)", flush=True)
        return False
    return check(label, ok, transcript[-600:], soft=True)


class _model_lock:
    """Serialises model runs across processes (and across WSL/Windows) when
    AGENT_SEMINAR_MODEL_LOCK points at a shared lock-file path. No-op otherwise."""

    def __init__(self) -> None:
        self.path = os.environ.get("AGENT_SEMINAR_MODEL_LOCK")
        self.fd: int | None = None

    def __enter__(self) -> None:
        if not self.path:
            return
        import time
        deadline = time.time() + 1800
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > 600:  # stale lock
                        os.remove(self.path)
                        continue
                except OSError:
                    pass
                if time.time() > deadline:
                    raise RuntimeError("model lock wait exceeded 30 minutes")
                time.sleep(3)

    def __exit__(self, *exc: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
            try:
                os.remove(self.path)
            except OSError:
                pass


def _parse_json(proc: subprocess.CompletedProcess) -> Any:
    text = proc.stdout.strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise RuntimeError(f"no JSON in opencode output: {proc.stdout[:300]} {proc.stderr[:300]}")
    return json.loads(text[start:])
