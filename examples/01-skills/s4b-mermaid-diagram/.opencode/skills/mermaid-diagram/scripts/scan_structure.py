#!/usr/bin/env python3
"""Scan a Python project and write its module-import structure as a Mermaid flowchart + text tree.

    python scan_structure.py sample-app --out out/architecture.md

The imports are read with the `ast` module (nothing is executed). Only imports between modules of the
scanned project count; standard library and third-party imports are ignored. Imports inside functions
are marked `lazy` (dotted arrows) because they do not run at import time.
stdout: JSON summary (modules, edges, cycles). Exit codes: 0 ok, 2 bad input (not a directory / no .py files).
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache", "build", "dist"}


def collect_modules(root: Path) -> dict[str, Path]:
    """dotted module name -> file path. Empty __init__.py files are not modules worth drawing."""
    mods: dict[str, Path] = {}
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
            if not parts or not path.read_text(encoding="utf-8", errors="replace").strip():
                continue
        mods[".".join(parts)] = path
    return mods


def imports_of(path: Path):
    """Yield (kind, module, names, level, lazy) for every import statement."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))

    def walk(node: ast.AST, lazy: bool):
        for child in ast.iter_child_nodes(node):
            inner = lazy or isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            if isinstance(child, ast.Import):
                for alias in child.names:
                    yield ("import", alias.name, [], 0, inner)
            elif isinstance(child, ast.ImportFrom):
                yield ("from", child.module or "", [a.name for a in child.names], child.level, inner)
            else:
                yield from walk(child, inner)

    yield from walk(tree, False)


def resolve(name: str, known: set[str]) -> str | None:
    """Longest known module that is `name` or one of its parents (import a.b.c -> a.b)."""
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in known:
            return cand
    return None


def build_edges(root: Path, mods: dict[str, Path]) -> dict[tuple[str, str], bool]:
    """(importer, imported) -> lazy-only? (True when every such import is inside a function)."""
    known = set(mods)
    edges: dict[tuple[str, str], bool] = {}
    for mod, path in mods.items():
        is_pkg = path.name == "__init__.py"
        package = mod if is_pkg else mod.rpartition(".")[0]
        for kind, name, names, level, lazy in imports_of(path):
            targets: list[str] = []
            if kind == "import":
                t = resolve(name, known)
                targets = [t] if t else []
            else:
                base = name
                if level:
                    up = package.split(".") if package else []
                    up = up[: len(up) - (level - 1)] if level > 1 else up
                    base = ".".join([*up, name] if name else up)
                for n in names:
                    t = resolve(f"{base}.{n}" if base else n, known)
                    if t is None and base:
                        t = resolve(base, known)
                    if t:
                        targets.append(t)
            for t in targets:
                if t != mod:
                    edges[(mod, t)] = edges.get((mod, t), True) and lazy
    return edges


def find_cycles(nodes: list[str], edges: dict[tuple[str, str], bool]) -> list[list[str]]:
    """One shortest concrete cycle per strongly connected component (Tarjan)."""
    adj: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    sccs: list[list[str]] = []
    counter = [0]

    def strong(v: str) -> None:
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in adj[v]:
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    sys.setrecursionlimit(10000)
    for n in nodes:
        if n not in index:
            strong(n)
    cycles = []
    for comp in sccs:
        if len(comp) < 2:
            continue
        members = set(comp)
        start = min(comp)
        prev = {start: None}
        queue = deque([start])
        found = None
        while queue and not found:
            cur = queue.popleft()
            for nxt in sorted(adj[cur]):
                if nxt not in members:
                    continue
                if nxt == start:
                    found = cur
                    break
                if nxt not in prev:
                    prev[nxt] = cur
                    queue.append(nxt)
        path = []
        cur = found
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        cycles.append(path + [start])
    return sorted(cycles)


def node_id(mod: str) -> str:
    return "m_" + mod.replace(".", "_")


def mermaid(mods: dict[str, Path], root: Path, edges: dict[tuple[str, str], bool], cycles: list[list[str]]) -> str:
    cyc_edges = {(c[i], c[i + 1]) for c in cycles for i in range(len(c) - 1)}
    cyc_nodes = {n for c in cycles for n in c}
    lines = ["flowchart LR"]
    packages: dict[str, list[str]] = defaultdict(list)
    for mod in mods:
        packages[mod.split(".")[0] if "." in mod else ""].append(mod)

    def label(mod: str) -> str:
        return mods[mod].relative_to(root).as_posix()

    for pkg, members in sorted(packages.items()):
        if pkg:
            lines.append(f'  subgraph pkg_{pkg}["{pkg}/"]')
        for mod in sorted(members):
            lines.append(f'{"    " if pkg else "  "}{node_id(mod)}["{label(mod)}"]')
        if pkg:
            lines.append("  end")
    link_index = 0
    red = []
    for (a, b), lazy in sorted(edges.items()):
        lines.append(f"  {node_id(a)} {'-.->' if lazy else '-->'} {node_id(b)}")
        if (a, b) in cyc_edges:
            red.append(link_index)
        link_index += 1
    if cyc_nodes:
        lines.append("  classDef cycle stroke:#d33,stroke-width:2px,fill:#fdecec,color:#600")
        lines.append("  class " + ",".join(node_id(n) for n in sorted(cyc_nodes)) + " cycle")
    if red:
        lines.append("  linkStyle " + ",".join(map(str, red)) + " stroke:#d33,stroke-width:2px")
    return "\n".join(lines)


def tree(root: Path, shown_name: str) -> str:
    out = [f"{shown_name}/"]

    def walk(d: Path, prefix: str) -> None:
        entries = [p for p in sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name))
                   if p.name not in SKIP_DIRS and (p.is_dir() or p.suffix == ".py")]
        for i, p in enumerate(entries):
            last = i == len(entries) - 1
            branch = "└── " if last else "├── "
            if p.is_dir():
                out.append(f"{prefix}{branch}{p.name}/")
                walk(p, prefix + ("    " if last else "│   "))
            else:
                n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
                out.append(f"{prefix}{branch}{p.name}  ({n} lines)")

    walk(root, "")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Module-import structure of a Python project as Mermaid + tree.")
    ap.add_argument("project", help="project directory to scan, e.g. sample-app")
    ap.add_argument("--out", default="out/architecture.md", help="Markdown output path (default out/architecture.md)")
    args = ap.parse_args()

    root = Path(args.project)
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    root = root.resolve()
    mods = collect_modules(root)
    if not mods:
        print(f"error: no .py files under {root}", file=sys.stderr)
        return 2
    try:
        edges = build_edges(root, mods)
    except SyntaxError as exc:
        print(f"error: cannot parse {exc.filename}:{exc.lineno}: {exc.msg}", file=sys.stderr)
        return 2
    cycles = find_cycles(sorted(mods), edges)
    fan_in: dict[str, int] = defaultdict(int)
    fan_out: dict[str, int] = defaultdict(int)
    for a, b in edges:
        fan_out[a] += 1
        fan_in[b] += 1

    def rel(mod: str) -> str:
        return mods[mod].relative_to(root).as_posix()

    rows = "\n".join(f"| `{rel(m)}` | {fan_out[m]} | {fan_in[m]} |" for m in sorted(mods))
    cycle_md = "\n".join("- `" + " -> ".join(rel(m) for m in c) + "`" for c in cycles) or "None found."
    md = "\n".join([
        f"# Architecture of `{root.name}`", "",
        f"{len(mods)} modules, {len(edges)} import edges between them, {len(cycles)} import cycle(s).",
        "Solid arrow = import at module level, dotted arrow = import inside a function. Red = part of a cycle.", "",
        "## Module import graph", "", "```mermaid", mermaid(mods, root, edges, cycles), "```", "",
        "## Directory tree", "", "```text", tree(root, root.name), "```", "",
        "## Import cycles", "", cycle_md, "",
        "## Modules", "", "| module | imports (out) | imported by (in) |", "|---|---|---|", rows, "",
    ])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8", newline="\n")
    summary = {
        "output": str(out), "output_absolute": str(out.resolve()),
        "modules": [rel(m) for m in sorted(mods)],
        "edges": [{"from": rel(a), "to": rel(b), "lazy": lazy} for (a, b), lazy in sorted(edges.items())],
        "cycles": [[rel(m) for m in c] for c in cycles],
        "most_imported": [{"module": rel(m), "imported_by": n} for m, n in sorted(fan_in.items(), key=lambda x: (-x[1], x[0]))[:3]],
        "entry_points": [rel(m) for m in sorted(mods) if fan_in[m] == 0],
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
