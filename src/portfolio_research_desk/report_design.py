"""Approved shared report styling and display-only primitives; no finance logic."""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from html import escape
from math import isfinite

CSS = """
:root { color-scheme: light; --ink:#182d40; --muted:#526577; --line:#dce4e9;
  --accent:#087f8c; --soft:#eef5f6; }
* { box-sizing:border-box; }
body { margin:0; background:#edf2f5; color:var(--ink);
  font:14px/1.5 'Segoe UI',Arial,sans-serif; font-variant-numeric:tabular-nums; }
main { max-width:1140px; margin:28px auto; padding:38px 42px; background:white;
  border:1px solid var(--line); border-radius:14px; }
header { border-bottom:2px solid var(--accent); padding-bottom:20px; margin-bottom:22px; }
.eyebrow { color:var(--accent); text-transform:uppercase; letter-spacing:1.8px;
  font-size:11px; font-weight:700; margin:0 0 7px; }
h1 { font-size:32px; line-height:1.15; margin:0 0 12px; letter-spacing:-.8px; }
h2 { font-size:19px; line-height:1.25; margin:23px 0 12px; }
h3 { font-size:13px; margin:0 0 8px; }
p { margin:8px 0; } a { color:#066573; text-underline-offset:3px; }
.muted, .note { color:var(--muted); } .note { font-size:12px; }
.badge { display:inline-block; border:1px solid #93bcc1; border-radius:4px;
  padding:3px 8px; font-size:11px; font-weight:700; margin-right:8px; }
.toolbar { display:flex; gap:20px; align-items:center; margin-top:14px; font-size:12px; }
.toolbar .print-hint { margin-left:auto; color:var(--muted); }
.clocks { display:flex; gap:28px; flex-wrap:wrap; font-size:12px; margin-top:12px; }
.clocks span { display:block; color:var(--muted); }
.notice { padding:11px 14px; background:#fff5df; border-left:3px solid #b26a17;
  margin:12px 0; overflow-wrap:anywhere; }
.notice.info { background:var(--soft); border-color:var(--accent); }
.metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
.metric { border:1px solid var(--line); border-radius:8px; padding:15px 16px; }
.metric.primary { background:var(--ink); color:white; border-color:var(--ink); }
.metric p { margin:0; font-size:11px; text-transform:uppercase; letter-spacing:.7px; }
.metric strong { display:block; font-size:25px; line-height:1.3; margin:8px 0 5px;
  overflow-wrap:anywhere; }
.metric small { display:block; font-size:11px; }
.negative { color:#a12b35; } .positive { color:#176d50; }
.allocation { display:grid; grid-template-columns:180px minmax(0,1fr); gap:24px;
  align-items:center; background:#f7fafb; border:1px solid var(--line); padding:16px;
  border-radius:8px; }
.allocation svg { width:170px; height:170px; }
.legend-row { display:grid; grid-template-columns:12px minmax(90px,1fr) auto 65px;
  gap:10px; align-items:center; padding:5px 0; border-bottom:1px solid var(--line); }
.swatch { width:10px; height:10px; border:1px solid #526577; }
.legend-row span:last-child { text-align:right; }
.table-wrap { width:100%; overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:12px; margin:5px 0 8px; }
th { color:var(--muted); font-weight:600; text-align:left; background:#f2f6f8;
  font-size:10px; letter-spacing:.2px; }
th, td { padding:9px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
td { overflow-wrap:anywhere; } .number { text-align:right; }
td small { display:block; font-size:10px; color:var(--muted); margin-top:2px; }
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:22px; }
.compact { margin:7px 0; padding-left:18px; font-size:12px; }
.compact li { margin:4px 0; overflow-wrap:anywhere; }
.downloads { display:flex; flex-wrap:wrap; gap:10px; margin:12px 0; }
.downloads a { padding:7px 11px; border:1px solid var(--line); border-radius:5px; }
footer { border-top:1px solid var(--line); margin-top:24px; padding-top:10px;
  font-size:11px; color:var(--muted); overflow-wrap:anywhere; }
.methodology { font-size:12px; } .methodology h3 { margin-top:12px; }
@media(max-width:720px) {
  main { margin:0; padding:22px 16px; border:0; border-radius:0; }
  .metrics { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .two-col { grid-template-columns:1fr; gap:8px; }
  .allocation { grid-template-columns:1fr; }
  .toolbar { flex-wrap:wrap; gap:12px; } .toolbar .print-hint { margin-left:0; }
  .clocks { gap:12px; } .table-wrap table { min-width:640px; }
}
@page { size:A4 portrait; margin:12mm 11mm 13mm; }
@media print {
  body { background:white; font-size:9pt; line-height:1.35;
    print-color-adjust:exact; -webkit-print-color-adjust:exact; }
  main { max-width:none; margin:0; padding:0; border:0; border-radius:0; }
  header { padding-bottom:9px; margin-bottom:12px; }
  h1 { font-size:24pt; margin-bottom:7px; } h2 { font-size:13pt; margin:15px 0 8px; }
  h3 { font-size:9pt; } h2,h3 { break-after:avoid; }
  .toolbar { display:none; } .clocks { font-size:8pt; gap:18px; margin-top:8px; }
  .eyebrow,.badge { font-size:7pt; } .badge { padding:2px 6px; }
  .metrics { gap:8px; } .metric { padding:10px; }
  .metric strong { font-size:17pt; margin:6px 0 4px; }
  .metric p,.metric small { font-size:7pt; }
  .allocation { grid-template-columns:135px minmax(0,1fr); padding:10px; gap:16px; }
  .allocation svg { width:125px; height:125px; } .legend-row { padding:4px 0; }
  .note,.compact,.methodology { font-size:8pt; }
  table { font-size:8pt; table-layout:fixed; } th { font-size:7pt; }
  th,td { padding:5px; } td small { font-size:7pt; }
  .table-wrap { overflow:visible; } thead { display:table-header-group; }
  tr { break-inside:avoid; } .metrics,.allocation { break-inside:avoid; }
  .details-page { break-before:page; }
  .notice { padding:7px 10px; margin:8px 0; }
  .two-col { gap:14px; } .downloads { gap:6px; font-size:8pt; }
  .downloads a { padding:3px 6px; text-decoration:none; }
  footer { display:none; }
  p { orphans:3; widows:3; }
}
"""


def e(value):
    return escape(str(value), quote=True)


def number(value, places=2):
    """Presentation rounding only, independent of the caller's Decimal context."""
    if value is None:
        return "Not available"
    with localcontext(Context(prec=80, rounding=ROUND_HALF_UP)):
        value = Decimal(str(value))
        if not value.is_finite():
            return "Not available"
        rounded = value.quantize(Decimal(1).scaleb(-places))
        if not rounded:
            rounded = abs(rounded)  # Never show negative zero.
        return f"{rounded:,.{places}f}"


def money(value, currency="CAD"):
    return f"{currency} {number(value)}" if value is not None else "Not available"


def percent(value, places=2):
    with localcontext(Context(prec=80, rounding=ROUND_HALF_UP)):
        if value is None or not Decimal(str(value)).is_finite():
            return "Not available"
        return f"{number(Decimal(str(value)) * 100, places)}%"


def stamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC") if value else "Not recorded"


def table(headers, rows, table_id, numeric=()):
    head = "".join(
        f'<th scope="col" class="{"number" if i in numeric else ""}">{e(h)}</th>'
        for i, h in enumerate(headers)
    )
    body = "".join(
        "<tr>"
        + "".join(
            f'<td class="{"number" if i in numeric else ""}">{cell}</td>'
            for i, cell in enumerate(row)
        )
        + "</tr>"
        for row in rows
    )
    return (
        f'<div class="table-wrap"><table id="{table_id}"><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def metric(label, value, detail, field, primary=False, tone=""):
    return (
        f'<div class="metric {"primary" if primary else ""}"><p>{e(label)}</p>'
        f'<strong id="{field}" class="{tone}">{e(value)}</strong>'
        f"<small>{e(detail)}</small></div>"
    )


RESEARCH_CSS = """
.chart { border:1px solid var(--line); border-radius:8px; padding:12px; margin:12px 0;
  background:#f7fafb; break-inside:avoid; }
.chart svg { display:block; width:100%; height:auto; }
.chart figcaption { font-size:12px; color:var(--muted); margin-top:8px; }
.chart-key { display:flex; flex-wrap:wrap; gap:8px 18px; font-size:11px; margin:8px 0 2px; }
.chart-key span { display:flex; align-items:center; gap:6px; }
.chart-key i { display:inline-block; width:16px; height:3px; }
.research-page .metric strong { font-size:23px; }
.research-page .metric .word { font-size:19px; }
.research-page .methodology { line-height:1.5; }
.research-page .section-intro { color:var(--muted); font-size:12px; }
@media screen and (max-width:720px) {
  .chart svg text { font-size:21px; }
}
@media print {
  .chart { margin:8px 0; padding:7px; }
  .chart figcaption,.chart-key { font-size:7.5pt; }
  .research-page .metric strong { font-size:16pt; }
  .research-page .section-intro { font-size:8pt; }
  .research-page .methodology { line-height:1.35; }
  .print-page { break-before:page; }
}
"""
CHART_COLORS = ("#087f8c", "#b26a17", "#5956a5", "#22734c", "#ac476b", "#64748b")


def pvalue(value):
    if value is None:
        return "Not available"
    return "<0.0001" if 0 <= Decimal(str(value)) < Decimal("0.0001") else number(value, 4)


def time_range(values):
    known = [datetime.fromisoformat(v) if isinstance(v, str) else v for v in values if v]
    if not known:
        return "Not recorded"
    lo, hi = min(known), max(known)
    return stamp(lo) if lo == hi else f"{stamp(lo)} to {stamp(hi)}"


def notice(message, info=False):
    return f'<p class="notice{" info" if info else ""}">{e(message)}</p>'


def bullets(items):
    return (
        '<ul class="compact">' + "".join(f"<li>{e(x)}</li>" for x in dict.fromkeys(items)) + "</ul>"
    )


def downloads(files):
    # Callers supply a fixed local filename inventory, never data-supplied URLs.
    return (
        '<div class="downloads">'
        + "".join(f'<a href="{e(name)}" download>{e(label)}</a>' for name, label in files)
        + "</div>"
    )


def document(title, run_id, generated_at, badges, clocks, body):
    header_clocks = "".join(
        f"<div><span>{e(label)}</span>{e(value)}</div>" for label, value in clocks
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{e(title)} | {e(run_id)}</title><style>{CSS}{RESEARCH_CSS}</style></head>"
        '<body><main class="research-page"><header>'
        '<p class="eyebrow">PortfolioResearchDesk / Research report</p>'
        f"<h1>{e(title)}</h1>"
        + "".join(f'<span class="badge">{e(badge)}</span>' for badge in badges)
        + f'<div class="clocks"><div><span>Report generated</span>{e(stamp(generated_at))}</div>'
        + header_clocks
        + f'</div><p class="note">Run {e(run_id)}</p>'
        '<nav class="toolbar" aria-label="Report sections"><a href="#overview">Overview</a>'
        '<a href="#details">Details</a><a href="#methodology">Methodology &amp; downloads</a>'
        '<span class="print-hint">Print / Save PDF: Ctrl+P (A4)</span></nav></header>'
        + body
        + "<footer>PortfolioResearchDesk | Snapshot research report | "
        "Display rounding only; exact inputs and results remain in the downloads.</footer>"
        "</main></body></html>"
    )


def section(title, contents, section_id, eyebrow=None, page=False):
    return (
        f'<section id="{e(section_id)}" class="{"print-page" if page else ""}">'
        + (f'<p class="eyebrow">{e(eyebrow)}</p>' if eyebrow else "")
        + f"<h2>{e(title)}</h2>{contents}</section>"
    )


def _chart_shell(svg, chart_id, title, series_names, note):
    legend = "".join(
        f'<span><i style="background:{CHART_COLORS[i % len(CHART_COLORS)]}"></i>{e(name)}</span>'
        for i, name in enumerate(series_names)
    )
    return (
        f'<figure class="chart" id="{e(chart_id)}"><svg viewBox="0 0 760 240" '
        f'role="img" aria-labelledby="{e(chart_id)}-title">'
        f'<title id="{e(chart_id)}-title">{e(title)}</title>{svg}</svg>'
        f'<div class="chart-key">{legend}</div><figcaption>{e(note)}</figcaption></figure>'
    )


def line_chart(labels, series, chart_id, title, formatter=number, zero=False, note=""):
    """Plot recorded observations with gaps; no interpolation, fitting or downsampling."""
    numeric = [
        [None if v is None or not isfinite(float(v)) else float(v) for v in values]
        for _, values in series
    ]
    if any(len(values) != len(labels) for values in numeric):
        raise ValueError("Chart labels and recorded observations must align.")
    known = [value for values in numeric for value in values if value is not None]
    if not labels or not known:
        return notice("Chart unavailable: no finite recorded observations.", True)
    lo, hi = min(known), max(known)
    if zero:
        lo, hi = min(lo, 0), max(hi, 0)
    padding = (hi - lo) * 0.08 or max(abs(hi) * 0.05, 0.001)
    lo, hi = lo - padding, hi + padding

    def x(i):
        return 92 + 644 * i / max(1, len(labels) - 1)

    def y(value):
        return 198 - 174 * (value - lo) / (hi - lo)

    parts = []
    for i in range(5):
        value = lo + (hi - lo) * i / 4
        yy = y(value)
        parts.append(
            f'<path d="M92 {yy:.2f} H736" stroke="#dce4e9"/>'
            f'<text x="83" y="{yy + 4:.2f}" text-anchor="end" font-size="11" '
            f'fill="#526577">{e(formatter(value))}</text>'
        )
    for i in sorted({0, (len(labels) - 1) // 2, len(labels) - 1}):
        anchor = "start" if i == 0 else "end" if i == len(labels) - 1 else "middle"
        parts.append(
            f'<text x="{x(i):.2f}" y="224" text-anchor="{anchor}" '
            f'font-size="11" fill="#526577">{e(str(labels[i])[:10])}</text>'
        )
    for index, values in enumerate(numeric):
        color = CHART_COLORS[index % len(CHART_COLORS)]
        path, segment = [], []
        for i, value in enumerate(values):
            if value is None:
                if segment:
                    path.append(" ".join(segment))
                segment = []
            else:
                segment.append(f"{'M' if not segment else 'L'}{x(i):.2f},{y(value):.2f}")
                # Isolated points must remain visible, including a single-observation chart.
                if len(values) == 1 or (
                    (i == 0 or values[i - 1] is None)
                    and (i == len(values) - 1 or values[i + 1] is None)
                ):
                    parts.append(
                        f'<circle cx="{x(i):.2f}" cy="{y(value):.2f}" r="3" fill="{color}"/>'
                    )
        if segment:
            path.append(" ".join(segment))
        for segment in path:
            parts.append(
                f'<path d="{segment}" fill="none" stroke="{color}" '
                f'stroke-width="2" stroke-dasharray="{"6 3" if index % 2 else "none"}"/>'
            )
    return _chart_shell(
        "".join(parts),
        chart_id,
        title,
        [name for name, _ in series],
        note or "Recorded observations; equally spaced periods. Gaps mean unavailable results.",
    )
