# Agent development guidelines

These guidelines apply to automated coding agents and complement
[CONTRIBUTING.md](CONTRIBUTING.md). Current capabilities and limitations are in
[README.md](README.md); the original project plan is historical design context.

## Scope and preservation

- Keep each change focused on the agreed issue or task. Roadmap entries are not
  instructions to implement unrelated features.
- Inspect the working tree, relevant code and documentation before editing.
  Preserve existing work; do not reset changes or rewrite Git history.
- Use a focused branch and describe the resulting behavior, validation and limits.
  Do not change repository visibility, publish packages/releases, push to protected
  branches or provision paid resources as an incidental development step.
- Use a modular monolith and create only modules needed by the change. Prefer
  small, readable, testable implementations over speculative abstractions.

## Architecture and financial research

- CLI and Streamlit are thin entry points. Reuse application services and existing
  calculations; keep domain, strategy, portfolio and execution code independent
  of UI frameworks and specific market-data providers.
- Historical inputs must satisfy `available_at <= decision_at < execution_at`.
  A signal computed after a close cannot execute at that same close price.
- Split panel data by global trading dates. Fit preprocessing only on training
  windows; preserve label start/end/known times, purge overlaps and apply the
  documented embargo policy. Unknown labels must not enter training.
- Distinguish PIT data, current snapshots and static universes. Use financial
  statements, sectors and factors only when available at the decision time.
  Unverified timing must block execution claims or limit results to descriptive
  research. Preserve future-perturbation and fold/execution-boundary regressions.
- Keep synthetic software validation, ex-post factor attribution, historical
  simulation and forward paper observations distinct. Do not claim certified
  real PIT/OOS performance, calibrated probabilities or investment profit from
  fixtures or passing tests.
- Preserve long-only, unleveraged simulation and exact-hash human review for paper
  plans. No broker or real-order integration is part of the current product.

## Environment and validation

- Use Python 3.12 and uv 0.13.6. Maintain `pyproject.toml` and the uv-generated
  `uv.lock` together; never hand-edit the lock. Add dependencies only when needed,
  checking upstream compatibility and installed metadata/runtime behavior.
- Install with `uv sync --locked`; use the README extras for full development.
  Run routine checks through `uv run --locked --offline` after provisioning.
- Follow the [README checks](README.md#testing--ci): tests, Ruff, lock, CLI,
  build and independent installation checks as appropriate to the change.
- Cover normal, boundary and failure paths for financial or stateful changes.
  Keep existing regressions. Tests and fixtures must be deterministic, without
  market requests, API keys or a dynamic clock.
- Preserve JSON stdout, diagnostic stderr and exit code 2 for expected CLI input
  errors. Do not replace meaningful failures with silent defaults.
- Report only checks actually run. Distinguish local results from remote Actions,
  and bind CI claims to the exact tested SHA. Update relevant method/architecture
  documentation and the changelog when behavior or support changes.

## Data, privacy and provenance

- Never commit credentials, private holdings/accounts or unauthorized market data.
  Keep real inputs, caches, generated reports and local tools in ignored paths.
- Label examples with synthetic/observed kind, currency and time assumptions.
  Financial numbers must come from calculations or explicit known-answer tests;
  do not invent or hard-code product performance claims.
- Preserve MIT attribution, third-party notices and data-rights limitations.
  The project's MIT license does not grant rights to external market datasets.
- Review diffs, screenshots and exports for personal paths and other unintended
  disclosures. If a real secret is found, stop the affected work and report its
  location without reproducing the value; do not rewrite history on your own.
- Keep AI-assisted implementation and agent-run review provenance accurate.
  Record technical decisions and evidence without copying private conversations,
  temporary prompts or session authorization logs into public documentation.
