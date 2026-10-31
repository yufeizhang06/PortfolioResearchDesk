# PortfolioResearchDesk — Report visual standard

2026-10-29. The accepted CAD Paper design is the shared standard for CAD Paper,
Factor Research, Machine Learning and Backtesting reports. Implementation is
`report_design.py` plus small report-specific renderers; no UI framework is required.

## Information and visual rules

1. **Identity first:** report title, run, currency, synthetic/observed classification,
   research scope, generation clock and sample/valuation interval.
2. **Overview:** four metric cards, short explanations and the main comparison/chart.
3. **Details:** full relevant model/strategy comparisons, uncertainty, folds,
   holdings/trades, costs and diagnostic results. Never hide unfavorable results.
4. **Methodology:** source, availability/retrieval clocks, parameter meaning,
   known limits and local audit downloads. Raw JSON is never report body content.

| Token | Standard |
|---|---|
| Text / primary card | `#182d40` deep blue |
| Emphasis | `#087f8c` teal |
| Secondary text / borders | `#526577` / `#dce4e9` |
| Background | white content, `#edf2f5` screen surround, pale gray chart/table panels |
| Warning | amber background + explicit wording; never color alone |
| Typeface | local Segoe UI, Arial, sans-serif; tabular numerals |
| Screen | max content width 1140px; four cards, two at narrow widths |
| Tables | right-aligned numeric columns, readable headers, local horizontal scroll on mobile |
| Charts | inline SVG, named series, units/periods, visible gaps; no external scripts/fonts |
| Print | A4 portrait, 12/11/13mm top/side/bottom margins; body 9pt, tables 8pt |

Keep print section breaks, repeat table headers, avoid splitting rows/charts and
allow longer datasets to flow. Do not truncate data just to meet a page target.
PDF examples are browser prints of the same HTML, not independently calculated documents.
The ML report intentionally gives full portfolio comparisons and NAV/cost charts separate pages.

## Numerical and temporal rules

- Money: explicit CAD/USD (or recorded local currency), thousands separator, 2 decimals.
- Percentages: 2 decimals by default. Alpha and its uncertainty: 4 decimals as
  percent **per day/month**, never silently annualized. Betas/F1/AUC: 3 decimals.
- p values: 4 decimals, with values below 0.0001 shown as `<0.0001`.
  FX: 6 decimals in Paper. Share counts: integers. Normalize negative display zero.
- `None`/nonfinite values: unavailable with explanation; not zero or an empty winner.
- Rounding is confined to display and independent of the caller's Decimal context.
  JSON/CSV precision, NAV, holdings, fees, model selection and financial definitions stay intact.
- Generation/export time is not account valuation, model fit, sample end, price
  observation, retrieval or input availability. Render explicit UTC labels; do not
  invent historic publication times from retrieval clocks.
- Charts plot saved observations. The drawdown chart maps saved NAV to its running
  peak with the engine's definition/precision; the headline uses the saved engine metric.
  ML NAV zooms to the frozen model's holdout evaluation dates and explicitly says
  earlier cash-only fixture observations remain in the full ledger.

## Scope and acceptance

Factor fits are ex-post explanations; synthetic ML/Backtesting are software
validation. No green badge may imply real profitability, certified PIT or real OOS.
Sharpe/annualized metrics absent from the current backtest engine remain unavailable.

Automated checks reconcile rendered cells and cards against actual offline engine
outputs, test failed/empty/undefined outcomes, escaping, local downloads and data
immutability. Final browser/PDF checks use saved real run bundles (synthetic data,
not a Mock UI). See [PHASE_7_REPORT.md](PHASE_7_REPORT.md) for evidence.
