"""Read-only Paper presentation. Ledger values and audit exports remain authoritative."""

from decimal import ROUND_HALF_UP, Context, Decimal, localcontext

from portfolio_research_desk.paper_store import loads
from portfolio_research_desk.report_design import CSS, e, money, number, percent, stamp, table
from portfolio_research_desk.report_design import metric as _metric

ZERO = Decimal(0)
COLORS = ("#64748b", "#087f8c", "#b26a17", "#5956a5", "#22734c", "#ac476b")


def identity(asset):
    return f"{asset.symbol} / {asset.exchange} / {asset.currency}"


def valuation_context(view, events):
    """Match the last recorded mark to its input event; event order detects staleness."""
    market, index = None, 0
    commands = [(event["seq"], loads(event["payload"])) for event in events]
    for seq, command in commands:
        if command["kind"] == "VALUE" or (
            command["kind"] == "EXECUTE" and view.plans[command["plan_id"]].status == "SIMULATED"
        ):
            market, index = command["market"], seq
    stale = not view.valuations or any(
        seq > index and command["kind"] in {"CASH", "CONVERT", "ACTION"}
        for seq, command in commands
    )
    return market, stale


def _allocation(value):
    if value is None or value.nav_cad == 0:
        return '<p class="notice info">Allocation unavailable until a positive NAV is recorded.</p>'
    items = [("Cash", value.cash_cad, value.cash_weight)]
    items.extend(
        (sector, sum((p["value_cad"] for p in value.positions if p["sector"] == sector), ZERO), w)
        for sector, w in value.sector_weights
    )
    circles, legend, offset = [], [], ZERO
    for i, (label, amount, weight) in enumerate(items):
        color = COLORS[i % len(COLORS)]
        size = weight * 100
        circles.append(
            f'<circle cx="90" cy="90" r="64" pathLength="100" fill="none" '
            f'stroke="{color}" stroke-width="25" stroke-dasharray="{size:.6f} '
            f'{100 - size:.6f}" stroke-dashoffset="{-offset:.6f}" '
            'transform="rotate(-90 90 90)"/>'
        )
        offset += size
        legend.append(
            f'<div class="legend-row"><span class="swatch" style="background:{color}"></span>'
            f"<span>{e(label)}</span><span>{e(money(amount))}</span>"
            f"<span>{percent(weight)}</span></div>"
        )
    return (
        '<div class="allocation"><svg viewBox="0 0 180 180" role="img" '
        'aria-labelledby="allocation-title"><title id="allocation-title">'
        "Asset allocation by sector and cash, as a share of CAD NAV. "
        + e("; ".join(f"{label}: {percent(w)}" for label, _, w in items))
        + "</title>"
        + "".join(circles)
        + '<text x="90" y="87" text-anchor="middle" fill="#182d40" font-size="18">'
        + f'{percent(value.cash_weight)}</text><text x="90" y="106" text-anchor="middle" '
        'fill="#526577" font-size="11">cash</text></svg><div>'
        + "".join(legend)
        + '<p class="note">Actual sector exposure, including cash. Weights use CAD NAV.</p>'
        "</div></div>"
    )


def _holdings(view, value, market):
    quotes = {q.asset: q for q in market.quotes} if market else {}
    rows = []
    for p in value.positions if value else ():
        asset = p["asset"]
        name = "Synthetic asset" if quotes[asset].synthetic else "Name not supplied"
        rows.append(
            [
                f"<b>{e(asset.symbol)}</b><small>{e(name)}<br>{e(asset.exchange)}"
                f" / {e(asset.currency)}</small>",
                f"{p['quantity']:,}",
                money(p["price_local"], asset.currency),
                money(p["value_cad"]),
                percent(p["weight"]) if value.nav_cad else "Not available",
                money(p["cad_pnl"]) + f"<small>{percent(p['cad_cost_return'])}</small>",
            ]
        )
    if value is None:
        for p in view.state.positions:
            rows.append(
                [e(identity(p.asset)), f"{p.quantity:,}", "Not valued", "Not valued", "-", "-"]
            )
    if not rows:
        return '<p class="notice info">No current holdings. The account holds cash only.</p>'
    return table(
        ("Security / name", "Shares", "Price (local)", "Value (CAD)", "Weight", "P&L (CAD)"),
        rows,
        "holdings",
        (1, 2, 3, 4, 5),
    ) + (
        '<p class="note">Company names are not supplied by this ledger; identifiers are shown '
        "without a guessed issuer name. P&amp;L is unrealized cost-basis P&amp;L; "
        "the percentage uses CAD cost, not NAV.</p>"
    )


def _risk(view, value):
    limits = view.limits
    largest = max((p["weight"] for p in value.positions), default=ZERO) if value else None
    sector = max((w for _, w in value.sector_weights), default=ZERO) if value else None
    defined = value is not None and value.nav_cad > 0
    constraints = (
        (
            "Largest position",
            percent(largest) if defined else "Not available",
            percent(limits.max_position_weight),
            "MAX_POSITION_WEIGHT",
        ),
        (
            "Largest sector",
            percent(sector) if defined else "Not available",
            percent(limits.max_sector_weight),
            "MAX_SECTOR_WEIGHT",
        ),
        (
            "Cash buffer (minimum)",
            percent(value.cash_weight) if defined else "Not available",
            percent(limits.cash_buffer),
            "CASH_BUFFER",
        ),
        (
            "Position count",
            str(len(view.state.positions)),
            str(limits.max_positions),
            "MAX_POSITIONS",
        ),
    )
    rows = [
        [
            label,
            actual,
            cap,
            "Not assessed"
            if not defined
            else "BREACH"
            if code in value.violations
            else "Within limit",
        ]
        for label, actual, cap, code in constraints
    ]
    warnings = (
        "Recorded breaches: " + ", ".join(value.violations)
        if value and value.violations
        else "No recorded concentration or cash-buffer breaches at this valuation."
        if defined
        else "Revalue the account to assess current allocation constraints."
    )
    return (
        f'<p class="note">{e(warnings)} Long-only; no leverage.</p>'
        + table(("Constraint", "Actual", "Limit", "Assessment"), rows, "risk", (1, 2))
        + '<p class="note">Trade controls: maximum order '
        + f"{limits.max_order_shares:,} shares; "
        + f"{percent(limits.max_trade_weight)} of NAV per trade; "
        + f"{percent(limits.max_turnover)} turnover per batch; "
        + f"minimum {money(limits.min_trade_cad)}. "
        + f"Maximum execution/reference price deviation: {percent(limits.max_price_deviation)}. "
        + "These controls are enforced on execution, not a forecast of future risk.</p>"
    )


def _trading(view):
    fills = sorted(
        (f for record in view.plans.values() for f in record.fills),
        key=lambda f: (f.execution_at, f.order.order_id),
    )
    rows = []
    for f in fills:
        asset = f.order.asset
        rows.append(
            [
                e(stamp(f.execution_at)),
                f"<b>{e(asset.symbol)}</b><small>{e(asset.exchange)} / {asset.currency}</small>",
                e(f.order.side) + f"<small>{f.order.quantity:,} shares</small>",
                money(f.price, asset.currency),
                money(f.commission_local, asset.currency),
                number(f.fx_rate.cad_per_usd, 6) if f.fx_rate else "1.000000",
                money(f.conversion.fee_cad if f.conversion else ZERO),
            ]
        )
    result = (
        table(
            (
                "Executed (UTC)",
                "Security",
                "Side / shares",
                "Fill price",
                "Commission",
                "CAD / unit",
                "FX fee (CAD)",
            ),
            rows,
            "trades",
            (3, 4, 5, 6),
        )
        if rows
        else '<p class="notice info">No simulated fills. Proposed orders are not trades.</p>'
    )
    result += (
        '<p class="note">Fill prices include slippage. FX is CAD per unit of local currency '
        "at execution; it can differ from valuation FX. FX fees apply only when currency is "
        "actually converted. Full order IDs, raw prices and FX rounding remain in trades.csv.</p>"
    )
    state = view.state
    result += table(
        ("Cumulative cost / income", "CAD", "Treatment"),
        [
            ["Commissions", money(state.commission_cad), "Already reflected in NAV"],
            [
                "FX costs",
                money(state.fx_cost_cad),
                "Fees plus FX rounding; already reflected in NAV",
            ],
            ["Slippage", money(state.slippage_cad), "Embedded in fill prices; do not deduct again"],
            ["Realized P&L", money(state.realized_pnl_cad), "Recorded CAD cost-basis attribution"],
            ["Dividends", money(state.dividends_cad), "Explicit supplied corporate actions only"],
        ],
        "costs",
        (1,),
    )
    if view.conversions:
        result += "<h3>Standalone currency conversions</h3>" + table(
            ("Source", "Destination", "CAD / USD", "Fee (CAD)", "Rounding (CAD)"),
            [
                [
                    money(c.source_amount, c.source_currency),
                    money(c.destination_amount, c.destination_currency),
                    number(c.rate.cad_per_usd, 6),
                    money(c.fee_cad),
                    money(c.rounding_cad),
                ]
                for c in view.conversions
            ],
            "conversions",
            (0, 1, 2, 3, 4),
        )
    if view.plans:
        result += "<h3>Plan status &amp; exceptions</h3>" + table(
            ("Plan", "Status", "Source / explanation"),
            [
                [
                    e(plan_id),
                    e(record.status),
                    e(record.plan.signals.source)
                    + ("<small>" + e(record.reason) + "</small>" if record.reason else ""),
                ]
                for plan_id, record in view.plans.items()
            ],
            "plans",
        )
    return result


def _methodology(view, value, market):
    rows = []
    if value and market:
        held = {p["asset"] for p in value.positions}
        for q in market.quotes:
            if q.asset in held:
                rows.append(
                    [
                        e(identity(q.asset)),
                        e(stamp(q.observed_at)),
                        e(stamp(q.available_at)),
                        e(q.source)
                        + (
                            "<small>Synthetic</small>"
                            if q.synthetic
                            else "<small>Observed / unverified</small>"
                        ),
                    ]
                )
        if value.fx:
            fx = value.fx
            rows.append(
                [
                    f"USD/CAD: {number(fx.cad_per_usd, 6)}",
                    e(stamp(fx.observed_at)),
                    e(stamp(fx.available_at)),
                    e(fx.source)
                    + (
                        "<small>Synthetic</small>"
                        if fx.synthetic
                        else "<small>Observed / unverified</small>"
                    ),
                ]
            )
    sources = (
        table(
            ("Valuation input", "Observed (UTC)", "Available (UTC)", "Source / kind"),
            rows,
            "sources",
        )
        if rows
        else "<p>No price or FX inputs were used in a recorded asset valuation.</p>"
    )
    costs, limits = view.costs, view.limits
    return sources + (
        '<div class="two-col methodology"><div><h3>Valuation &amp; P&amp;L</h3>'
        "<p>NAV = CAD cash + USD cash translated at recorded FX + raw-price holdings "
        "translated to CAD. Account P&amp;L = NAV minus net contributions; this is an "
        "amount, not a time-weighted or annualized strategy return. Holding P&amp;L "
        "uses the recorded CAD cost basis, including allocated purchase costs.</p>"
        "<p>Money and percentages display 2 decimals; FX displays 6. Display rounding "
        "does not change the ledger. Rounded components may differ by a cent or "
        "0.01 percentage point. Exact values are in the downloads.</p></div><div>"
        "<h3>Execution &amp; limitations</h3>"
        f"<p>Cost assumptions: {number(costs.fixed_fee)} in trade currency fixed + "
        f"{number(costs.commission_bps)} bps commission; {number(costs.slippage_bps)} bps "
        f"slippage; {number(costs.fx_fee_bps)} bps FX fee. Explicit review precedes "
        "next-session simulation. No broker or real orders.</p>"
        f"<p>Input age limits: quotes {limits.max_quote_age_seconds:,} seconds; "
        f"FX {limits.max_fx_age_seconds:,} seconds. Availability is supplied metadata, "
        "not independently certified publication evidence. Historical PIT, membership, "
        "delistings and calendars remain unverified; corporate actions are limited. "
        "No credible real-market OOS or tax-reporting claim.</p></div></div>"
    )


def render_account_report(view, events, generated_at, run_id):
    # A separate high-precision context is only for display aggregates/geometry.
    # Never reprice a position, execute a trade or mutate the supplied audit view.
    with localcontext(Context(prec=80, rounding=ROUND_HALF_UP)):
        return _render(view, events, generated_at, run_id)


def _render(view, events, generated_at, run_id):
    market, stale = valuation_context(view, events)
    latest = view.valuations[-1] if view.valuations else None
    value = latest if not stale else None
    used = (
        [q for q in market.quotes if latest and q.asset in {p["asset"] for p in latest.positions}]
        if market
        else []
    )
    if latest and latest.fx:
        used.append(latest.fx)
    kind = (
        "SYNTHETIC VALUATION"
        if used and all(q.synthetic for q in used)
        else (
            "MIXED INPUTS"
            if any(q.synthetic for q in used)
            else "OBSERVED INPUTS / UNVERIFIED"
            if used
            else "NO MARKET INPUTS"
        )
    )
    alert = ""
    if stale:
        message = "Valuation required. "
        if latest:
            message += f"Last recorded NAV was {money(latest.nav_cad)} at {stamp(latest.as_of)}. "
        message += (
            "No current NAV, allocation or P&L is shown because "
            "the account has no valuation matching its latest economic state. Revalue with "
            "explicit available prices and FX. Current ledger quantities and cash appear below."
        )
        alert = f'<p class="notice">{e(message)}</p>'
    if kind == "MIXED INPUTS":
        alert += (
            '<p class="notice">Mixed synthetic and observed valuation inputs; '
            "this is not an entirely synthetic valuation or verified market performance.</p>"
        )
    if value and value.violations:
        alert += (
            '<p class="notice">Risk alert: the recorded valuation breaches '
            f"{len(value.violations)} configured limits. See Risk &amp; Constraints below.</p>"
        )
    pnl = value.nav_cad - view.state.net_contributions_cad if value else None
    holdings = sum((p["value_cad"] for p in value.positions), ZERO) if value else None
    badge = "Matches latest ledger state" if value else "Valuation required"
    summary = (
        f"{len(value.positions)} holdings; {percent(value.cash_weight)} in cash. "
        "Values are from the recorded snapshot, not live market prices."
        if value and value.nav_cad
        else "No positive, current NAV available for allocation weights."
    )
    cash = " / ".join(money(amount, c) for c, amount in view.state.cash)
    metrics = "".join(
        [
            _metric(
                "Portfolio NAV",
                money(value.nav_cad if value else None),
                "Total account value in CAD",
                "nav",
                True,
            ),
            _metric(
                "Cash",
                money(value.cash_cad if value else None),
                "All cash translated to CAD",
                "cash",
            ),
            _metric(
                "Holdings value", money(holdings), "Raw-price market value in CAD", "holdings-value"
            ),
            _metric(
                "Account P&L",
                money(pnl),
                "NAV less net contributions",
                "pnl",
                tone="negative" if pnl is not None and pnl < 0 else "positive",
            ),
        ]
    )
    downloads = "".join(
        f'<a href="{name}" download>{label}</a>'
        for name, label in (
            ("account.json", "Account JSON"),
            ("trades.csv", "Trades CSV"),
            ("nav.csv", "NAV CSV"),
            ("events.json", "Audit events JSON"),
            ("run.json", "Integrity manifest"),
        )
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>CAD Paper Account | {e(run_id)}</title><style>{CSS}</style></head><body><main>"
        '<header><p class="eyebrow">PortfolioResearchDesk / Account report</p>'
        '<h1>CAD Paper Account</h1><span class="badge">PAPER SIMULATION ONLY</span>'
        f'<span class="badge">{kind}</span><span class="note">{badge}</span>'
        '<div class="clocks"><div><span>Report generated</span>'
        f"{stamp(generated_at)}</div><div><span>Account valued</span>"
        f"{stamp(latest.as_of) if latest else 'Not recorded'}"
        f"</div><div><span>Last ledger event</span>{stamp(view.last_at)}</div></div>"
        f'<p class="note">Run {e(run_id)} / {view.event_count} ledger events</p>'
        '<nav class="toolbar" aria-label="Report sections"><a href="#overview">Overview</a>'
        '<a href="#holdings-section">Holdings</a><a href="#trading">Trading</a>'
        '<a href="#methodology">Methodology &amp; downloads</a>'
        '<span class="print-hint">Print / Save PDF: Ctrl+P (A4)</span></nav></header>'
        '<section id="overview"><p class="eyebrow">01 / Overview</p>'
        f'<h2>Portfolio Overview</h2>{alert}<div class="metrics">{metrics}</div>'
        f'<p class="note">{e(summary)}</p><p class="note">Ledger cash: {cash}. '
        f"Net contributions: {money(view.state.net_contributions_cad)}.</p>"
        f"<h2>Asset Allocation</h2>{_allocation(value)}</section>"
        '<section id="holdings-section"><h2>Current Holdings</h2>'
        f"{_holdings(view, value, market)}</section><section><h2>Risk &amp; Constraints</h2>"
        f'{_risk(view, value)}</section><section class="details-page" id="trading">'
        '<p class="eyebrow">02 / Details</p><h2>Trading History</h2>'
        f'{_trading(view)}</section><section id="methodology">'
        '<p class="eyebrow">03 / Methodology</p><h2>Data &amp; Methodology</h2>'
        '<p class="notice info">Synthetic examples verify software behavior, not market '
        "performance. Generation time is the export time; valuation time is the recorded "
        "account snapshot. Observed and available times below belong to its actual inputs.</p>"
        f"{_methodology(view, latest, market)}<h3>Data downloads &amp; audit</h3>"
        f'<div class="downloads">{downloads}</div><p class="note">Downloads are local files '
        "beside this HTML report. Use the original report folder to access them from a PDF. "
        "The manifest verifies file integrity, not the truth of supplied market data.</p></section>"
        f"<footer>PortfolioResearchDesk | CAD paper simulation | Run {e(run_id)} | "
        f"{view.event_count} ledger events<br>Snapshot report; no automatic price refresh.</footer>"
        "</main></body></html>"
    )
