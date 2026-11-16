"""logs/audit.jsonl 을 읽어 도구별 호출 횟수와 시간순 타임라인을 출력합니다.

    python summarize_audit.py                       (Linux에서 python 명령이 없으면 python3)
    python summarize_audit.py --file logs/audit.jsonl
    python summarize_audit.py --all                 로테이션된 audit.*.jsonl 도 함께 읽기
    python summarize_audit.py --session ses_abc123  특정 세션만
    python summarize_audit.py --tool bash           특정 도구만 타임라인에 표시
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent


def load(paths: list[pathlib.Path]) -> tuple[list[dict], int]:
    records: list[dict] = []
    bad = 0
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    bad += 1  # 쓰는 도중 프로세스가 끊긴 줄 등
                    continue
                if isinstance(rec, dict) and "tool" in rec:
                    records.append(rec)
                else:
                    bad += 1
    records.sort(key=lambda r: str(r.get("ts", "")))
    return records, bad


def brief(rec: dict, width: int = 70) -> str:
    """타임라인에 보여 줄 한 줄 요약: 명령이나 경로를 우선한다."""
    args = rec.get("args") or {}
    if isinstance(args.get("pattern"), str):  # grep / glob: 무엇을 어디서 찾았는지
        text = args["pattern"] + (f" @ {args['path']}" if args.get("path") else "")
        return text if len(text) <= width else text[: width - 1] + "…"
    for key in ("command", "filePath", "path", "url", "file_path"):
        value = args.get(key)
        if isinstance(value, str) and value:
            text = value
            break
    else:
        text = str(rec.get("title") or "")
    return text if len(text) <= width else text[: width - 1] + "…"


def local_clock(ts: str) -> str:
    """기록은 UTC(ISO 8601, Z)로 저장되므로 보기 좋게 로컬 시각 HH:MM:SS 로 바꾼다."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
    except ValueError:
        return ts[11:19] if len(ts) >= 19 else ts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", type=pathlib.Path, default=HERE / "logs" / "audit.jsonl")
    ap.add_argument("--all", action="store_true", help="같은 폴더의 audit.*.jsonl(로테이션 파일)도 포함")
    ap.add_argument("--session", help="이 sessionID 의 기록만")
    ap.add_argument("--tool", help="타임라인에 이 도구만 표시 (횟수 표는 전체 기준)")
    args = ap.parse_args()

    paths = [args.file] if args.file.exists() else []
    if args.all:
        paths = sorted(args.file.parent.glob(args.file.stem + ".*.jsonl")) + paths
    if not paths:
        print(f"기록 파일이 없습니다: {args.file}")
        print("먼저 이 폴더에서 opencode 로 작업을 한 번 시켜 보세요.")
        return 1

    records, bad = load(paths)
    if args.session:
        records = [r for r in records if r.get("sessionID") == args.session]
    if not records:
        print("조건에 맞는 기록이 없습니다.")
        return 1

    counts = Counter(r["tool"] for r in records)
    sessions = sorted({str(r.get("sessionID")) for r in records})
    print(f"기록 {len(records)}건 · 세션 {len(sessions)}개 · 파일 {len(paths)}개" + (f" · 읽지 못한 줄 {bad}개" if bad else ""))
    print()
    print("도구별 호출 횟수")
    for tool, n in counts.most_common():
        print(f"  {tool:<12} {n:>4}  {'#' * min(n, 40)}")
    print()
    print("타임라인")
    shown = [r for r in records if not args.tool or r["tool"] == args.tool]
    for rec in shown:
        clock = local_clock(str(rec.get("ts", "")))
        sid = str(rec.get("sessionID", ""))[-6:]
        print(f"  {clock}  {sid:<6}  {rec['tool']:<10}  {brief(rec)}  [출력 {rec.get('outputLength', 0)}자]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
