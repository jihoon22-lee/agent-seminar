#!/usr/bin/env python3
"""Scan files for hard-coded secrets. Values are always masked in the output.

    python scan_secrets.py                 # scan the current directory
    python scan_secrets.py src config.py   # scan given files / directories
    python scan_secrets.py --changed       # only files git reports as modified, staged or untracked

Output (one finding per line):  <file>:<line>:<rule>: <line with the secret masked>
Exit codes: 0 = nothing found, 1 = findings, 2 = bad arguments / path missing / git problem.
Add the comment  secret-scan: ignore  to a line to suppress findings on it.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache"}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Cargo.lock", "bun.lock"}
MAX_BYTES = 1_000_000
IGNORE_MARK = "secret-scan: ignore"
ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")

SECRET_WORDS = r"(?:api[_-]?key|secret|passw(?:or)?d|pwd|token|access[_-]?key|private[_-]?key|credential)"
# 1. name = "value"  /  "name": "value"
RE_CREDENTIAL = re.compile(
    rf"(?i)(?P<name>[\w.-]*{SECRET_WORDS}[\w.-]*)[\"']?\s*[:=]\s*(?P<q>[\"'])(?P<val>[^\"'\s]{{8,}})(?P=q)")
# 2. private key header (assembled from parts so this file does not look like a key itself)
RE_PRIVATE_KEY = re.compile("-----" + "BEGIN " + r"(?:[A-Z]+ )?" + "PRIVATE " + "KEY(?: BLOCK)?" + "-----")
# 3. well-known token shapes
RE_KNOWN = re.compile(r"\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,}|sk-[A-Za-z0-9_-]{32,}|sk_(?:live|test)_[A-Za-z0-9]{16,}|xox[abprs]-[A-Za-z0-9-]{10,})")
# 4. user:password@host in URLs
RE_URL_CRED = re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@\"']+:(?P<val>[^@\s/\"']{4,})@")
# 5. KEY=value lines inside .env files
RE_ENV_LINE = re.compile(r"^\s*(?:export\s+)?(?P<name>[A-Za-z0-9_]+)\s*=\s*(?P<val>.*?)\s*$")
RE_ENV_SECRET_NAME = re.compile(rf"(?i){SECRET_WORDS}")
# 6. long random-looking strings
RE_CANDIDATE = re.compile(r"[A-Za-z0-9+/_=-]{32,}")
RE_HEX = re.compile(r"^[0-9a-fA-F]+$")

PLACEHOLDER_HINTS = ("example", "changeme", "change_me", "placeholder", "your", "xxxx", "todo", "dummy",
                     "sample", "<", "${", "{{", "{env:", "%s", "environ", "getenv", "process.env")


def is_placeholder(value: str) -> bool:
    low = value.lower()
    return any(h in low for h in PLACEHOLDER_HINTS) or len(set(value)) <= 2 or value.startswith("$")


def entropy(s: str) -> float:
    counts = Counter(s)
    return -sum(c / len(s) * math.log2(c / len(s)) for c in counts.values())


def mask(value: str) -> str:
    if len(value) <= 8:
        return value[:1] + "***"
    return f"{value[:3]}***({len(value)} chars)"


def is_env_file(path: Path) -> bool:
    name = path.name
    return (name == ".env" or name.startswith(".env.")) and not name.endswith(ENV_TEMPLATE_SUFFIXES)


def scan_text(path: Path, text: str) -> list[dict]:
    findings: list[dict] = []
    env_file = is_env_file(path)
    if env_file:
        findings.append({"file": str(path), "line": 1, "rule": "env-file",
                         "match": ".env file: keep it out of git (add to .gitignore) and share via a secret store"})
    for lineno, line in enumerate(text.splitlines(), start=1):
        if IGNORE_MARK in line:
            continue
        spans: list[tuple[int, int, str, str]] = []  # (start, end, rule, secret)

        def add(m: re.Match, rule: str, group: str | int = 0) -> None:
            s, e = m.span(group)
            if not any(s < b and a < e for a, b, _, _ in spans):
                spans.append((s, e, rule, m.group(group)))

        for m in RE_PRIVATE_KEY.finditer(line):
            add(m, "private-key-header")
        for m in RE_KNOWN.finditer(line):
            add(m, "known-token-prefix")
        for m in RE_CREDENTIAL.finditer(line):
            if not is_placeholder(m["val"]):
                add(m, "hardcoded-credential", "val")
        for m in RE_URL_CRED.finditer(line):
            if not is_placeholder(m["val"]):
                add(m, "url-credentials", "val")
        if env_file:
            m = RE_ENV_LINE.match(line)
            if m and RE_ENV_SECRET_NAME.search(m["name"]):
                val = m["val"].strip("\"'")
                if len(val) >= 6 and not is_placeholder(val):
                    add(m, "env-secret", "val")
        for m in RE_CANDIDATE.finditer(line):
            tok = m.group(0)
            if not any(ch.isdigit() for ch in tok) or tok.startswith("/") or "//" in tok:
                continue
            limit = 3.0 if RE_HEX.match(tok) else 4.3
            if entropy(tok) >= limit and not is_placeholder(tok):
                add(m, "high-entropy-string")
        if not spans:
            continue
        shown = line
        for s, e, rule, secret in sorted(spans, reverse=True):
            if rule != "private-key-header":  # the header line itself is not secret
                shown = shown[:s] + mask(secret) + shown[e:]
        shown = shown.strip()
        for _s, _e, rule, _secret in sorted(spans):
            findings.append({"file": str(path), "line": lineno, "rule": rule, "match": shown[:160]})
    return findings


def iter_files(paths: list[Path]):
    for root in paths:
        if root.is_file():
            yield root
            continue
        stack = [root]
        while stack:
            d = stack.pop()
            for child in sorted(d.iterdir(), reverse=True):
                if child.is_dir():
                    if child.name not in SKIP_DIRS:
                        stack.append(child)
                elif child.is_file() and child.name not in SKIP_FILES:
                    yield child


def changed_files() -> list[Path]:
    def git(*args: str) -> list[str]:
        try:
            proc = subprocess.run(["git", "-c", "core.quotepath=off", *args], capture_output=True, encoding="utf-8")
        except FileNotFoundError:
            raise SystemExit("error: git not found on PATH")
        if proc.returncode != 0:
            raise SystemExit(f"error: git {' '.join(args)} failed: {proc.stderr.strip()}")
        return [p for p in proc.stdout.split("\0") if p]

    names = set(git("ls-files", "-z", "-m", "-o", "--exclude-standard"))
    names |= set(git("diff", "-z", "--cached", "--name-only", "--relative", "--diff-filter=ACMR"))
    return sorted(Path(n) for n in names if Path(n).is_file())


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan for hard-coded secrets (values are masked in the output).")
    ap.add_argument("paths", nargs="*", help="files or directories (default: current directory)")
    ap.add_argument("--changed", action="store_true", help="only scan files git reports as changed/staged/untracked")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    try:
        if args.changed:
            files = changed_files()
        else:
            roots = [Path(p) for p in args.paths] or [Path(".")]
            missing = [str(r) for r in roots if not r.exists()]
            if missing:
                print(f"error: path not found: {', '.join(missing)}", file=sys.stderr)
                return 2
            files = list(iter_files(roots))
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2

    findings: list[dict] = []
    scanned = 0
    for f in files:
        try:
            if f.stat().st_size > MAX_BYTES:
                continue
            data = f.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:8192]:
            continue  # binary
        scanned += 1
        findings += scan_text(Path(f.as_posix()), data.decode("utf-8", errors="replace"))

    if args.format == "json":
        json.dump({"scanned_files": scanned, "findings": findings}, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        for f in findings:
            print(f"{f['file']}:{f['line']}:{f['rule']}: {f['match']}")
        print(f"# {len(findings)} finding(s) in {len({f['file'] for f in findings})} file(s); {scanned} file(s) scanned")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
