# Contributing

Use Python 3.12 and uv 0.13.6. Read `AGENTS.md`, the current user-authorized phase,
`docs/PROJECT_PLAN.md`, `docs/CODE_WALKTHROUGH.md` and relevant numerical/data
contracts before editing. Future plans do not authorize implementation.

1. Check the working tree; preserve existing work and use a phase-scoped branch.
2. `uv sync --locked --extra data --extra factors --extra ml`.
3. Keep CLI thin, Decimal accounting explicit and provider/UI concerns at the edge.
4. Preserve `available_at <= decision_at < execution_at`, training-only fits and
   explicit synthetic / descriptive / historical / paper distinctions.
5. Add meaningful boundary/failure tests for financial or stateful changes. Retain
   old regressions. Tests must not request market data or use a dynamic clock.
6. Run the README test/build/install commands and record actual results. Update
   method/architecture decisions, changelog and phase report as appropriate.
7. Review candidate files for secrets, accounts, raw market data and generated
   artifacts. MIT covers our own work only; verify separate input/resource rights.

Do not commit, push, publish, change repository visibility, connect brokers or
create a release without the user's authorization. The user has authorized Phase 6
final acceptance and safe private synchronization; public visibility and a formal
v1.0.0 release remain outside that authorization.

Report bugs with command/config, Python/platform/version, exit code and redacted
stderr. Use a minimal synthetic input where possible. Never paste credentials,
private holdings or licensed data into an issue or review report.
