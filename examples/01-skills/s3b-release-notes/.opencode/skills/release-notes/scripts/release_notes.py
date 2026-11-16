#!/usr/bin/env python3
"""Group the commits between two git refs by Conventional Commit type and print Markdown.

    python release_notes.py --from v1.0.0 --to HEAD
    python release_notes.py --from v1.0.0 --to HEAD --format json

Run it inside the repository (or pass --repo). Merge commits are skipped.
Exit codes: 0 = notes printed, 2 = not a git repo / unknown ref / git missing.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

HEADER_RE = re.compile(r"^(?P<type>[A-Za-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s*(?P<desc>.+)$")
BREAKING_RE = re.compile(r"^BREAKING[ -]CHANGE:\s*(.+)$", re.MULTILINE)

SECTIONS = [  # (type, heading shown in the Markdown)
    ("feat", "Features"),
    ("fix", "Bug fixes"),
    ("perf", "Performance"),
    ("refactor", "Refactoring"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("build", "Build system"),
    ("ci", "CI"),
    ("style", "Style"),
    ("chore", "Chores"),
    ("revert", "Reverts"),
]
KNOWN = {t for t, _ in SECTIONS}
SEP_FIELD, SEP_RECORD = "\x1f", "\x1e"


def git(repo: str, *args: str) -> str:
    try:
        proc = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=repo, capture_output=True,
                              encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print("error: git not found on PATH", file=sys.stderr)
        raise SystemExit(2)
    if proc.returncode != 0:
        print(f"error: git {' '.join(args)} failed: {proc.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    return proc.stdout


def parse_commit(record: str) -> dict:
    sha, short, author, date, subject, body = (record.strip("\n").split(SEP_FIELD) + [""] * 6)[:6]
    m = HEADER_RE.match(subject)
    ctype = m["type"].lower() if m else None
    breaking_notes = [n.strip() for n in BREAKING_RE.findall(body)]
    breaking = bool(m and m["bang"]) or bool(breaking_notes)
    if m and m["bang"] and not breaking_notes:
        breaking_notes = [m["desc"]]
    return {
        "sha": sha, "short": short, "author": author, "date": date[:10],
        "type": ctype if ctype in KNOWN else "other",
        "scope": (m["scope"] or None) if m else None,
        "description": m["desc"].strip() if m else subject.strip(),
        "breaking": breaking, "breaking_notes": breaking_notes,
        "conventional": bool(m) and ctype in KNOWN,
    }


def entry_line(c: dict) -> str:
    scope = f"**{c['scope']}**: " if c["scope"] else ""
    return f"- {scope}{c['description']} (`{c['short']}`)"


def render_markdown(commits: list[dict], frm: str, to: str) -> str:
    out = [f"# Changes {frm} -> {to}", ""]
    if not commits:
        out.append("No commits in this range.")
        return "\n".join(out) + "\n"
    dates = sorted(c["date"] for c in commits)
    out.append(f"{len(commits)} commits, {dates[0]} .. {dates[-1]}, "
               f"{len({c['author'] for c in commits})} author(s).")
    out.append("")
    breaking = [c for c in commits if c["breaking"]]
    if breaking:
        out += ["## Breaking changes", ""]
        for c in breaking:
            out.append(entry_line(c))
            for note in c["breaking_notes"]:
                if note != c["description"]:
                    out.append(f"  - {note}")
        out.append("")
    for ctype, heading in SECTIONS:
        group = [c for c in commits if c["type"] == ctype]
        if group:
            out += [f"## {heading}", "", *map(entry_line, group), ""]
    other = [c for c in commits if c["type"] == "other"]
    if other:
        out += ["## Other (not Conventional Commits)", "", *map(entry_line, other), ""]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Release notes from Conventional Commits (Markdown on stdout).")
    ap.add_argument("--from", dest="frm", help="start ref, excluded (tag or commit). Default: latest tag")
    ap.add_argument("--to", default="HEAD", help="end ref, included (default HEAD)")
    ap.add_argument("--repo", default=".", help="repository directory (default: current directory)")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = ap.parse_args()

    git(args.repo, "rev-parse", "--git-dir")
    git(args.repo, "rev-parse", "--verify", "--quiet", args.to + "^{commit}")
    frm = args.frm
    if frm is None:
        try:
            frm = git(args.repo, "describe", "--tags", "--abbrev=0", args.to).strip()
        except SystemExit:
            frm = None  # no tag yet: whole history
    rng = f"{frm}..{args.to}" if frm else args.to
    if frm:
        git(args.repo, "rev-parse", "--verify", "--quiet", frm + "^{commit}")
    fmt = SEP_FIELD.join(["%H", "%h", "%an", "%aI", "%s", "%b"]) + SEP_RECORD
    raw = git(args.repo, "log", "--no-merges", "--reverse", f"--pretty=format:{fmt}", rng)
    commits = [parse_commit(r) for r in raw.split(SEP_RECORD) if r.strip()]

    if args.format == "json":
        json.dump({"from": frm, "to": args.to, "commits": commits}, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(commits, frm or "(start)", args.to))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
