"""Run every example's check.py and print a summary table.

    python tools/run_checks.py              # checks that do not call a model
    python tools/run_checks.py --model      # also run model checks (uses a free opencode model)
    python tools/run_checks.py 02-mcp       # only examples whose path contains "02-mcp"
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    # Accept Windows-style paths (examples\01-skills) and trailing slashes.
    filters = [a.replace("\\", "/").rstrip("/") for a in sys.argv[1:] if not a.startswith("--")]
    env = dict(os.environ, PYTHONUTF8="1")
    if "--model" in sys.argv:
        env["AGENT_SEMINAR_MODEL_CHECKS"] = "1"
    checks = sorted((ROOT / "examples").glob("*/*/check.py"))
    if filters:
        checks = [c for c in checks if any(f in c.as_posix() for f in filters)]
    # Probe the npm registry once and tell every check.py the result (they would each probe otherwise).
    sys.path.insert(0, str(ROOT / "tools"))
    import octest
    octest.registry_reachable()
    env["AGENT_SEMINAR_REGISTRY"] = os.environ.get("AGENT_SEMINAR_REGISTRY", "ok")
    rows = []
    for path in checks:
        rel = path.parent.relative_to(ROOT).as_posix()
        print(f"\n### {rel}", flush=True)
        started = time.time()
        proc = subprocess.run([sys.executable, str(path)], cwd=str(path.parent), env=env)
        rows.append((rel, proc.returncode == 0, time.time() - started))
    print("\n== summary")
    for rel, ok, secs in rows:
        print(f"  {'OK  ' if ok else 'FAIL'} {rel} ({secs:.0f}s)")
    failed = [r for r in rows if not r[1]]
    print(f"== {len(rows)} examples, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
