"""USD backtest display from recorded results. No execution or metric changes."""

from decimal import Context, Decimal, localcontext

from portfolio_research_desk.report_design import (
    bullets,
    document,
    downloads,
    e,
    line_chart,
    metric,
    money,
    notice,
    number,
    percent,
    section,
    stamp,
    table,
    time_range,
)


def drawdown_series(equity, initial_nav):
    """Display the recorded NAV path below its running peak, matching engine precision."""
    with localcontext(Context(prec=28)):
        peak = Decimal(str(initial_nav))
        values = []
        for point in equity:
            nav = Decimal(str(point["nav"]))
            peak = max(peak, nav)
            values.append(-(1 - nav / peak))
        return values


def _asset(asset):
    return e(asset["symbol"]) + f"<small>{e(asset['exchange'])} / {e(asset['currency'])}</small>"


def render_backtest_report(result, dataset, run_id, generated_at):
    config, metrics = result["config"], result["metrics"]
    equity, universe = result["equity"], result["universe"]
    latest = equity[-1] if equity else None
    labels = [row["session_date"] for row in equity]
    interval = f"{labels[0]} to {labels[-1]}" if labels else "No valuations recorded"
    overview = notice(
        "SYNTHETIC USD accounting and causality verification; not historical market evidence. "
        "No model fitting, credible real-market OOS result or profitability claim.",
        True,
    )
    overview += (
        '<div class="metrics">'
        + "".join(
            (
                metric(
                    "Ending NAV",
                    money(metrics["ending_nav"], "USD"),
                    "Includes marked open positions",
                    "backtest-nav",
                    True,
                ),
                metric(
                    "Cumulative return",
                    percent(metrics["cumulative_return"]),
                    "After simulated costs",
                    "backtest-return",
                ),
                metric(
                    "Maximum drawdown",
                    percent(metrics["max_drawdown"]),
                    "Largest decline from a prior NAV peak",
                    "backtest-drawdown",
                ),
                metric(
                    "Cash benchmark",
                    percent(metrics["cash_benchmark_return"]),
                    "Uninvested USD; no interest",
                    "backtest-benchmark",
                ),
            )
        )
        + "</div>"
    )
    overview += '<p class="section-intro">NAV is cash plus marked holdings. Cumulative return '
    overview += (
        "compares ending NAV with starting capital. Drawdown measures the worst drop "
        "from a prior peak, not the probability of a future loss.</p>"
    )
    overview += "<h2>NAV &amp; Benchmark</h2>" + line_chart(
        labels,
        [
            ("Strategy NAV", [r["nav"] for r in equity]),
            ("Cash baseline", [r["cash_benchmark_nav"] for r in equity]),
        ],
        "backtest-nav-chart",
        "Recorded USD NAV and cash benchmark",
        lambda v: number(v, 0),
        note="USD; recorded session valuations, equally spaced. "
        "This benchmark is cash, not an equity index.",
    )
    overview += table(
        ("Account / cost measure", "Recorded result", "Interpretation"),
        [
            [
                "Starting capital",
                money(metrics["initial_nav"], "USD"),
                "USD account; separate from CAD Paper",
            ],
            [
                "Ending cash",
                money(latest["cash"] if latest else None, "USD"),
                "Cash remaining after fills and fees",
            ],
            ["Commission", money(metrics["total_commission"], "USD"), "Already included in NAV"],
            [
                "Slippage cost",
                money(metrics["total_slippage_cost"], "USD"),
                "Embedded in fill prices; do not subtract again",
            ],
            [
                "Simulated fills / cancelled orders",
                f"{metrics['fill_count']} / {metrics['cancelled_order_count']}",
                "Cancelled requests are not filled trades",
            ],
            [
                "Traded notional / starting capital",
                number(metrics.get("traded_notional_over_initial_capital"), 3),
                "Total raw-price traded notional; not annualized turnover",
            ],
        ],
        "backtest-costs",
        (1,),
    )

    details = line_chart(
        labels,
        [("Drawdown", drawdown_series(equity, metrics["initial_nav"]))],
        "backtest-dd-chart",
        "NAV decline below running peak",
        percent,
        True,
        "Zero is a NAV peak; negative values show the decline below it. "
        "The overview reports maximum drawdown as a positive depth.",
    )
    holdings = (
        [
            [
                _asset(p["asset"]),
                f"{p['quantity']:,}",
                money(p["close"], "USD"),
                money(p["market_value"], "USD"),
                percent(p["weight"]),
            ]
            for p in latest["positions"]
        ]
        if latest
        else []
    )
    details += "<h3>End-of-run holdings</h3>" + (
        table(
            ("Security", "Shares", "Mark price", "Market value", "NAV weight"),
            holdings,
            "backtest-holdings",
            (1, 2, 3, 4),
        )
        if holdings
        else notice("No open holdings at the last recorded valuation.", True)
    )
    fill_rows = [
        [
            e(stamp(f["execution_at"])),
            _asset(f["asset"]),
            e(f["side"]),
            f"{f['quantity']:,}",
            money(f["price"], "USD"),
            money(f["commission"], "USD"),
            money(f["slippage_cost"], "USD"),
        ]
        for f in result["fills"]
    ]
    details += "<h2>Trading History</h2>" + (
        table(
            ("Executed (UTC)", "Security", "Side", "Shares", "Fill price", "Fee", "Slippage"),
            fill_rows,
            "backtest-fills",
            (3, 4, 5, 6),
        )
        if fill_rows
        else notice("No simulated fills.", True)
    )
    details += '<p class="note">No forced final liquidation. Fill prices already contain slippage. '
    details += (
        "Decision timestamps, raw prices, order IDs and all outcomes "
        "remain in fills/orders CSV.</p>"
    )

    method = table(
        ("Risk / return metric", "Result", "Scope"),
        [
            [
                "Annualized return",
                percent(metrics["annualized_return"]),
                "Not supplied by this short-sample verification engine",
            ],
            [
                "Annualized volatility",
                percent(metrics["annualized_volatility"]),
                "Not supplied; no invented estimate",
            ],
            [
                "Sharpe",
                number(metrics["sharpe"], 3),
                "Not supplied; no risk-adjusted performance claim",
            ],
            [
                "Position weight limit",
                percent(config["portfolio"]["max_position_weight"]),
                "Checked when sizing/executing; later price drift can breach it",
            ],
            [
                "Minimum cash buffer",
                percent(config["portfolio"]["cash_buffer"]),
                "Applied by existing execution logic",
            ],
        ],
        "backtest-risk",
        (1,),
    )
    cancelled = [o for o in result["orders"] if o["status"] != "FILLED"]
    if cancelled:
        method += "<h3>Order exceptions</h3>" + table(
            ("Security", "Status", "Filled shares", "Reason"),
            [
                [
                    _asset(o["order"]["asset"]),
                    e(o["status"]),
                    str(o["filled_quantity"]),
                    e(o["reason"]),
                ]
                for o in cancelled
            ],
            "backtest-exceptions",
            (2,),
        )
    bars = dataset.get("bars", [])
    method += "<h3>Data, timing and execution</h3>" + table(
        ("Item", "Recorded setting"),
        [
            ["Universe", e(f"{universe['membership_type']} / {universe['source']}")],
            [
                "Universe as of / available",
                e(stamp(universe["as_of"]) + " / " + stamp(universe.get("available_at"))),
            ],
            ["Price source", e(dataset.get("source", config["data_source"]))],
            ["Close inputs available", e(time_range(b.get("available_at") for b in bars))],
            [
                "Last account valuation",
                e(stamp(latest["valuation_at"]) if latest else "Not recorded"),
            ],
            [
                "Strategy",
                e(
                    f"{config['strategy']['name']}; "
                    f"lookback {config['strategy']['lookback_sessions']} "
                    f"sessions; Top-{config['strategy']['top_k']}"
                ),
            ],
            [
                "Cost assumptions",
                f"USD {number(config['execution']['fixed_fee'])} fixed + "
                f"{number(config['execution']['commission_bps'])} bps commission; "
                f"{number(config['execution']['slippage_bps'])} bps slippage.",
            ],
        ],
        "backtest-method",
    )
    method += (
        '<div class="methodology"><p>Trailing close momentum forms equal target weights. '
        "Signals are decided after scheduled close; execution uses the next explicit session open, "
        "integer shares and sells before buys. Requests are fixed from known closes and may only "
        "be reduced for cash/weight limits. No leverage or short selling.</p><p>Return and risk "
        "cards use saved engine metrics. The drawdown chart only maps the saved NAV path to its "
        "running peak, using the same definition and precision. Money/percent display rounding "
        "never changes the ledger. Generation time is separate from valuations "
        "and input availability.</p></div>"
    )
    method += "<h3>Strategy and data limitations</h3>" + bullets(result["warnings"])
    method += "<h3>Audit downloads</h3>" + downloads(
        [
            ("result.json", "Full results JSON"),
            ("equity.csv", "NAV CSV"),
            ("positions.csv", "Holdings CSV"),
            ("fills.csv", "Trades CSV"),
            ("orders.csv", "Order outcomes CSV"),
            ("config_snapshot.json", "Parameters"),
            ("data_snapshot.json", "Data inputs"),
            ("run.json", "Provenance"),
        ]
    )
    return document(
        "Backtesting Report",
        run_id,
        generated_at,
        ("SYNTHETIC", "USD", "SOFTWARE VALIDATION"),
        [("Valuation interval", interval)],
        section("Portfolio Overview", overview, "overview", "01 / Overview")
        + section("Drawdown, Holdings & Trades", details, "details", "02 / Details", True)
        + section("Risk, Data & Methodology", method, "methodology", "03 / Methodology", True),
    )
