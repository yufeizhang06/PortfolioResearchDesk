# Contributing

Contributions should address a focused bug, documentation improvement or agreed
feature. For a substantial change, discuss scope in an issue before implementation.
Read [AGENTS.md](AGENTS.md), [Architecture](docs/ARCHITECTURE.md),
[Code Walkthrough](docs/CODE_WALKTHROUGH.md) and the relevant data/numerical contracts.
The original [Project Plan](docs/PROJECT_PLAN.md) provides design context; use the
[README capability matrix](README.md#current-development-status) for current support.

## Development setup

Use Python **3.12.x** and uv **0.13.6**. Fork the repository if needed, create a
focused branch and preserve existing work. From the checkout root:

```bash
python -m pip install uv==0.13.6
uv sync --locked --extra gui --extra data --extra factors --extra ml --python 3.12
uv run --locked --offline prd doctor --require factors --require ml
```

See [Installation](README.md#installation--quick-start) for Windows Python-launcher
and PATH alternatives. Initial dependency provisioning needs network or a populated
cache. All four extras are required for the complete development checks.

## Change and validation requirements

1. Keep CLI/UI thin, Decimal accounting explicit, and provider/UI concerns at the edge.
2. Preserve `available_at <= decision_at < execution_at`, training-only fits and
   explicit synthetic / descriptive / historical / paper distinctions.
3. Add meaningful boundary/failure tests for financial or stateful changes. Retain
   existing regressions. Tests must not request market data or use a dynamic clock.
4. Run the [README quality checks](README.md#testing--ci) appropriate to the change.
   Record actual commands/results and any checks not run. Update relevant method,
   architecture, user documentation and [changelog](docs/CHANGELOG.md).
5. Review candidate files for secrets, accounts, raw market data, personal paths and
   generated artifacts. MIT covers our own work only; verify separate resource rights.
6. Submit a pull request with the problem, resulting behavior, validation and known
   limitations. Maintainers manage merges, repository settings and releases.

AI-assisted contributions are welcome. Contributors remain responsible for
correctness, licensing and validation; identify agent-run review evidence accurately.
Do not include private conversations, temporary prompts or personal authorization
records in project documents. No real broker/order integration is supported.

## Reporting bugs

Include the command/config, Python/platform/project version, exit code and redacted
stderr. Use a minimal synthetic input where possible. Never paste credentials,
private holdings or licensed data into an issue or review report.

The [documentation index](docs/README.md) links user guides, technical contracts
and dated development evidence.
