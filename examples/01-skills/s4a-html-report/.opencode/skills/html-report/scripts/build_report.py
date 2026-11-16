#!/usr/bin/env python3
"""Build a self-contained HTML sales report (summary table + inline SVG bar/line chart) from a CSV.

    python build_report.py data/sales.csv --out out/report.html

CSV columns (header required): month (YYYY-MM), region, units, revenue
The HTML has no external assets: no CDN, no JavaScript, no web fonts. Open it by double-clicking.
stdout: a JSON summary (paths, totals and the numbers worth commenting on). Exit codes: 0 ok, 2 bad input.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "report.html"
REQUIRED = ["month", "region", "units", "revenue"]


class InputError(Exception):
    pass


def load(path: Path) -> list[dict]:
    try:
        fh = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}")
    with fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise InputError(f"missing column(s): {', '.join(missing)} (header is {reader.fieldnames})")
        rows = []
        for n, row in enumerate(reader, start=2):
            try:
                datetime.strptime(row["month"], "%Y-%m")
                rows.append({"month": row["month"], "region": row["region"].strip(),
                             "units": int(row["units"]), "revenue": int(row["revenue"])})
            except (ValueError, TypeError, AttributeError):
                raise InputError(f"line {n}: cannot parse {row}")
    if not rows:
        raise InputError("no data rows")
    return rows


def won(n: float) -> str:
    return f"{n:,.0f}"


def mwon(n: float) -> str:
    return f"{n / 1_000_000:,.1f}"


def pct(x: float) -> str:
    return f"{x:+.1f}%"


def nice_ticks(vmax: float, n: int = 5) -> list[float]:
    raw = vmax / n
    mag = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 1
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    top = step * (int(vmax / step) + (0 if vmax % step == 0 else 1))
    return [step * i for i in range(int(top / step) + 1)]


def chart_svg(months: list[str], revenue: list[int], units: list[int]) -> str:
    w, h = 880, 380
    left, right, top, bottom = 64, 56, 28, 48
    pw, ph = w - left - right, h - top - bottom
    rt, ut = nice_ticks(max(revenue)), nice_ticks(max(units))
    rmax, umax = rt[-1], ut[-1]
    slot = pw / len(months)
    bw = slot * 0.58
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="chart-title chart-desc">',
           '<title id="chart-title">월별 매출과 판매 수량</title>',
           f'<desc id="chart-desc">{escape(months[0])}부터 {escape(months[-1])}까지 월별 매출 합계(막대, 백만원)와 '
           f'판매 수량 합계(선, 개).</desc>']
    for t in rt:  # grid + left axis labels (revenue)
        y = top + ph - t / rmax * ph
        out.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{w - right}" y2="{y:.1f}"/>')
        out.append(f'<text class="axis-left" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{t / 1_000_000:g}</text>')
    for t in ut:  # right axis labels (units)
        y = top + ph - t / umax * ph
        out.append(f'<text class="axis-right" x="{w - right + 8}" y="{y + 4:.1f}">{t:g}</text>')
    out.append(f'<text class="axis-left" x="4" y="14">매출(백만원)</text>')
    out.append(f'<text class="axis-right" x="{w - right + 8}" y="14">수량(개)</text>')
    points = []
    for i, (m, r, u) in enumerate(zip(months, revenue, units)):
        cx = left + slot * (i + 0.5)
        bh = r / rmax * ph
        out.append(f'<rect class="bar" x="{cx - bw / 2:.1f}" y="{top + ph - bh:.1f}" width="{bw:.1f}" '
                   f'height="{bh:.1f}" rx="2"><title>{escape(m)} 매출 {won(r)}원</title></rect>')
        points.append((cx, top + ph - u / umax * ph, m, u))
        out.append(f'<text x="{cx:.1f}" y="{h - bottom + 18}" text-anchor="middle">{escape(m[5:])}월</text>')
    out.append('<polyline class="trend" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in points) + '"/>')
    for x, y, m, u in points:
        out.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="3.5"><title>{escape(m)} 수량 {u:,}개</title></circle>')
    out.append(f'<text x="{left}" y="{h - 8}" class="axis-left">■ 매출(막대, 왼쪽 축)</text>')
    out.append(f'<text x="{left + 190}" y="{h - 8}" class="axis-right">● 판매 수량(선, 오른쪽 축)</text>')
    out.append("</svg>")
    return "\n".join(out)


def build(rows: list[dict], source: str) -> tuple[dict, dict]:
    months = sorted({r["month"] for r in rows})
    regions = sorted({r["region"] for r in rows})
    m_rev, m_units = defaultdict(int), defaultdict(int)
    rg: dict[str, dict] = {g: {"revenue": 0, "units": 0, "monthly": defaultdict(int)} for g in regions}
    for r in rows:
        m_rev[r["month"]] += r["revenue"]
        m_units[r["month"]] += r["units"]
        rg[r["region"]]["revenue"] += r["revenue"]
        rg[r["region"]]["units"] += r["units"]
        rg[r["region"]]["monthly"][r["month"]] += r["revenue"]
    revenue = [m_rev[m] for m in months]
    units = [m_units[m] for m in months]
    total_rev, total_units = sum(revenue), sum(units)
    best_i = max(range(len(months)), key=lambda i: revenue[i])
    worst_i = min(range(len(months)), key=lambda i: revenue[i])
    mom = [(months[i], (revenue[i] / revenue[i - 1] - 1) * 100) for i in range(1, len(months))]
    half = len(months) // 2

    region_stats = []
    for g in regions:
        monthly = [rg[g]["monthly"].get(m, 0) for m in months]
        first, second = sum(monthly[:half]), sum(monthly[half:])
        med = statistics.median(monthly)
        dips = [months[i] for i, v in enumerate(monthly) if med and v < med * 0.7]
        region_stats.append({
            "region": g, "revenue": rg[g]["revenue"], "units": rg[g]["units"],
            "share_pct": round(rg[g]["revenue"] / total_rev * 100, 1),
            "h2_vs_h1_pct": round((second / first - 1) * 100, 1) if first else None,
            "dip_months": dips,
        })

    kpis = [
        ("총 매출", f"{won(total_rev)}원", f"{months[0]} ~ {months[-1]}"),
        ("총 판매 수량", f"{total_units:,}개", f"객단가 평균 {won(total_rev / total_units)}원"),
        ("월 평균 매출", f"{won(total_rev / len(months))}원", f"{len(months)}개월 기준"),
        ("최고 매출 월", months[best_i], f"{won(revenue[best_i])}원"),
    ]
    kpi_html = "\n".join(
        f'    <div class="kpi"><div class="label">{escape(a)}</div><div class="value">{escape(b)}</div>'
        f'<div class="note">{escape(c)}</div></div>' for a, b, c in kpis)

    def cls(v):
        return "" if v is None else ("up" if v > 0 else "down")

    body = "\n".join(
        f'      <tr><td>{escape(s["region"])}</td><td>{won(s["revenue"])}</td><td>{s["units"]:,}</td>'
        f'<td>{s["share_pct"]:.1f}%</td><td class="{cls(s["h2_vs_h1_pct"])}">'
        f'{pct(s["h2_vs_h1_pct"]) if s["h2_vs_h1_pct"] is not None else "-"}</td></tr>' for s in region_stats)
    table = ('    <table>\n      <thead><tr><th>지역</th><th>매출(원)</th><th>수량(개)</th><th>매출 비중</th>'
             '<th>하반기 / 상반기</th></tr></thead>\n      <tbody>\n' + body + '\n      </tbody>\n'
             f'      <tfoot><tr><td>합계</td><td>{won(total_rev)}</td><td>{total_units:,}</td><td>100.0%</td><td></td></tr></tfoot>\n'
             '    </table>')

    page = {
        "title": "월별 판매 리포트",
        "subtitle": escape(f"원본: {source} · {len(rows)}행 · 지역 {len(regions)}곳"),
        "kpis": kpi_html, "chart": chart_svg(months, revenue, units), "table": table,
        "footer": escape(f"생성 {datetime.now():%Y-%m-%d %H:%M} · 외부 리소스 없는 단일 HTML 파일"),
    }
    summary = {
        "rows": len(rows), "months": [months[0], months[-1]], "regions": regions,
        "total_revenue": total_rev, "total_units": total_units,
        "best_month": {"month": months[best_i], "revenue": revenue[best_i]},
        "worst_month": {"month": months[worst_i], "revenue": revenue[worst_i]},
        "biggest_mom_increase": {"month": max(mom, key=lambda x: x[1])[0], "pct": round(max(x[1] for x in mom), 1)},
        "biggest_mom_decrease": {"month": min(mom, key=lambda x: x[1])[0], "pct": round(min(x[1] for x in mom), 1)},
        "regions_detail": region_stats,
    }
    return page, summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a self-contained HTML sales report from a CSV.")
    ap.add_argument("csv", help="input CSV (columns: month,region,units,revenue)")
    ap.add_argument("--out", default="out/report.html", help="output HTML path (default out/report.html)")
    args = ap.parse_args()
    try:
        rows = load(Path(args.csv))
        page, summary = build(rows, Path(args.csv).as_posix())
        html = TEMPLATE.read_text(encoding="utf-8")
    except (InputError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for key, value in page.items():
        html = html.replace("{{" + key + "}}", value)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8", newline="\n")
    summary = {"output": str(out), "output_absolute": str(out.resolve()), "bytes": len(html.encode("utf-8")), **summary}
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
