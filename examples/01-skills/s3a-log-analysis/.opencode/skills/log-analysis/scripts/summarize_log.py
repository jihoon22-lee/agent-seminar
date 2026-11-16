#!/usr/bin/env python3
"""Summarise a large application log without reading it into an LLM context.

Expected line format (one event per line):

    2026-11-03T10:15:22 ERROR [payment] gateway timeout after 30000ms (order=ORD-48213)

Output: one JSON document on stdout (levels, components, normalised top error
messages, 5-minute windows with error spikes). Lines that do not match the format
(for example stack-trace continuation lines) are only counted.

Exit codes: 0 = summary printed, 2 = bad arguments / file not readable / no log lines found.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s+"
    r"(?P<level>DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)\s+"
    r"\[(?P<component>[^\]]+)\]\s+(?P<message>.*)$"
)
ERROR_LEVELS = {"ERROR", "CRITICAL", "FATAL"}

# Order matters: the most specific patterns first.
MASKS = [
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<UUID>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "<IP>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<HEX>"),
    (re.compile(r"\b[0-9a-f]{12,}\b"), "<HEX>"),
    (re.compile(r"\d+"), "<N>"),
]


def normalise(message: str) -> str:
    for pattern, repl in MASKS:
        message = pattern.sub(repl, message)
    return message.strip()


def parse_duration(text: str) -> int:
    m = re.fullmatch(r"(\d+)\s*([smh]?)", text.strip().lower())
    if not m or int(m.group(1)) == 0:
        raise argparse.ArgumentTypeError(f"bad duration {text!r} (examples: 30s, 5m, 1h)")
    return int(m.group(1)) * {"": 60, "s": 1, "m": 60, "h": 3600}[m.group(2)]


def parse_ts(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text.replace("T", " "))
    except ValueError:
        raise argparse.ArgumentTypeError(f"bad timestamp {text!r} (example: 2026-11-03T10:30:00)")


def bucket_start(dt: datetime, seconds: int) -> datetime:
    epoch = int((dt - datetime(1970, 1, 1)).total_seconds())
    return datetime(1970, 1, 1) + timedelta(seconds=epoch // seconds * seconds)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def top(counter: Counter, n: int) -> list[dict]:
    return [{"name": k, "count": v} for k, v in counter.most_common(n)]


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarise an application log (JSON on stdout).")
    ap.add_argument("logfile", help="path to the log file")
    ap.add_argument("--window", type=parse_duration, default=300, metavar="5m",
                    help="window size for spike detection: 30s, 5m, 1h (default 5m)")
    ap.add_argument("--top", type=int, default=10, help="how many top items to list (default 10)")
    ap.add_argument("--min-errors", type=int, default=5,
                    help="a window needs at least this many errors to count as a spike (default 5)")
    ap.add_argument("--from", dest="since", type=parse_ts, help="ignore lines before this timestamp")
    ap.add_argument("--to", dest="until", type=parse_ts, help="ignore lines after this timestamp")
    ap.add_argument("--component", help="only look at one component, e.g. payment")
    ap.add_argument("--sample", type=int, default=0, metavar="N",
                    help="also print up to N raw WARN/ERROR lines (first ones in the selected range)")
    args = ap.parse_args()

    path = Path(args.logfile)
    if not path.is_file():
        print(f"error: not a file: {path}", file=sys.stderr)
        return 2

    levels: Counter = Counter()
    components: Counter = Counter()
    errors_by_component: Counter = Counter()
    messages: dict[tuple[str, str], dict] = {}
    err_windows: Counter = Counter()
    all_windows: Counter = Counter()
    window_components: dict[datetime, Counter] = defaultdict(Counter)
    window_messages: dict[datetime, Counter] = defaultdict(Counter)
    samples: list[str] = []
    total = parsed = 0
    first_ts = last_ts = None

    # Stream the file: memory use stays flat however large the log is.
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            total += 1
            m = LINE_RE.match(raw)
            if not m:
                continue
            ts = datetime.fromisoformat(m["ts"].replace("T", " "))
            if args.since and ts < args.since or args.until and ts > args.until:
                continue
            if args.component and m["component"] != args.component:
                continue
            parsed += 1
            level = "WARN" if m["level"] == "WARNING" else m["level"]
            first_ts = ts if first_ts is None or ts < first_ts else first_ts
            last_ts = ts if last_ts is None or ts > last_ts else last_ts
            levels[level] += 1
            components[m["component"]] += 1
            b = bucket_start(ts, args.window)
            all_windows[b] += 1
            if level in ERROR_LEVELS:
                errors_by_component[m["component"]] += 1
                err_windows[b] += 1
                norm = normalise(m["message"])
                key = (m["component"], norm)
                entry = messages.get(key)
                if entry is None:
                    entry = messages[key] = {"component": m["component"], "message": norm, "count": 0,
                                             "first_seen": iso(ts), "last_seen": iso(ts),
                                             "example": m["message"][:300]}
                entry["count"] += 1
                entry["last_seen"] = iso(ts) if iso(ts) > entry["last_seen"] else entry["last_seen"]
                entry["first_seen"] = iso(ts) if iso(ts) < entry["first_seen"] else entry["first_seen"]
                window_components[b][m["component"]] += 1
                window_messages[b][norm] += 1
            if args.sample and level in ERROR_LEVELS | {"WARN"} and len(samples) < args.sample:
                samples.append(raw.rstrip("\r\n")[:300])

    if parsed == 0:
        print("error: no lines matched '<ISO timestamp> LEVEL [component] message'", file=sys.stderr)
        return 2

    # Spike rule: error count >= mean + 2*stdev over ALL windows in the range, and >= --min-errors.
    n_windows = int((bucket_start(last_ts, args.window) - bucket_start(first_ts, args.window)).total_seconds()
                    // args.window) + 1
    counts = [err_windows.get(bucket_start(first_ts, args.window) + timedelta(seconds=i * args.window), 0)
              for i in range(n_windows)]
    mean = statistics.fmean(counts)
    stdev = statistics.pstdev(counts)
    threshold = max(args.min_errors, mean + 2 * stdev)
    spike_starts = sorted(b for b, c in err_windows.items() if c >= threshold)

    def window_info(b: datetime) -> dict:
        return {
            "start": iso(b), "end": iso(b + timedelta(seconds=args.window)),
            "errors": err_windows[b], "all_events": all_windows[b],
            "top_components": top(window_components[b], 3),
            "top_messages": top(window_messages[b], 3),
        }

    # Merge touching spike windows into incidents.
    incidents: list[dict] = []
    for b in spike_starts:
        if incidents and b <= datetime.fromisoformat(incidents[-1]["end"]):
            incidents[-1]["end"] = iso(b + timedelta(seconds=args.window))
            incidents[-1]["errors"] += err_windows[b]
            incidents[-1]["_windows"].append(b)
        else:
            incidents.append({"start": iso(b), "end": iso(b + timedelta(seconds=args.window)),
                              "errors": err_windows[b], "_windows": [b]})
    for inc in incidents:
        comp: Counter = Counter()
        msgs: Counter = Counter()
        for b in inc.pop("_windows"):
            comp.update(window_components[b])
            msgs.update(window_messages[b])
        inc["top_components"] = top(comp, 3)
        inc["top_messages"] = top(msgs, 3)

    top_messages = sorted(messages.values(), key=lambda e: (-e["count"], e["first_seen"]))[: args.top]
    result = {
        "file": str(path),
        "lines_total": total,
        "lines_parsed": parsed,
        "lines_unparsed": total - parsed if not (args.since or args.until or args.component) else None,
        "time_range": {"first": iso(first_ts), "last": iso(last_ts)},
        "filters": {"from": iso(args.since) if args.since else None, "to": iso(args.until) if args.until else None,
                    "component": args.component},
        "levels": dict(levels.most_common()),
        "components": top(components, args.top),
        "errors_by_component": top(errors_by_component, args.top),
        "top_errors": top_messages,
        "window_seconds": args.window,
        "spike_rule": {"baseline_mean": round(mean, 2), "baseline_stdev": round(stdev, 2),
                       "threshold": round(threshold, 2), "windows_total": n_windows},
        "spike_windows": [window_info(b) for b in spike_starts][: args.top],
        "incidents": incidents,
    }
    if args.sample:
        result["sample_lines"] = samples
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
