# Documentation

PortfolioResearchDesk is a public **0.7.0 Early Beta** research workbench. Start
with the current guides below; historical plans and acceptance records describe
their listed revisions and do not imply real investment performance.

## Use and install

| Guide | Purpose |
|---|---|
| [Project overview and installation](../README.md) | Requirements, quick start, screenshots and the current GUI/CLI capability matrix |
| [GUI guide](GUI_GUIDE.md) | Home → Stock Explorer → Factor Research; read-only Paper views and GUI limits |
| [CLI user guide](USER_GUIDE.md) | Offline workspace/demo, editable inputs, reviewed Paper lifecycle and recovery |
| [Known limitations](../README.md#known-limitations) | PIT/OOS, calendars, corporate actions, local-only UI and incomplete workflows |
| [Testing and CI](../README.md#testing--ci) | Full extras, deterministic tests, Ruff, lock, build and isolated installation commands |

## Technical contracts and contribution

| Document | Purpose |
|---|---|
| [Architecture](ARCHITECTURE.md) / [Code walkthrough](CODE_WALKTHROUGH.md) | Current module boundaries, calculations, services and source-reading order |
| [Data policy](DATA_POLICY.md) | Sources, data rights, identity, availability clocks and snapshot semantics |
| [Backtest assumptions](BACKTEST_ASSUMPTIONS.md) | Legacy synthetic USD execution, costs and known-answer accounting |
| [Factor research](FACTOR_RESEARCH.md) | Ex-post FF3/FF4, common samples, units and diagnostic limitations |
| [Model validation](MODEL_VALIDATION.md) | Synthetic features/labels, purge, train-only fits and holdout governance |
| [Paper trading](PAPER_TRADING.md) | CAD/FX, exact-hash review, limits, events and replay; no real orders |
| [Report design standard](REPORT_DESIGN_STANDARD.md) | Display precision, provenance, responsive HTML and printing |
| [Contributing](../CONTRIBUTING.md) / [Agent guidelines](../AGENTS.md) | Development setup, focused changes, validation and privacy |
| [MIT license](../LICENSE) / [Third-party notices](../THIRD_PARTY_NOTICES.md) | Project grant and separate dependency/data rights |

## Status and development evidence

- [Changelog](CHANGELOG.md): technical changes by development milestone.
- [Release readiness](RELEASE_READINESS.md): current early-beta position, exact-SHA
  software evidence and remaining work before any formal v1.0 release.
- [Development history](DEVELOPMENT_LOG.md): milestone summary, defects/decisions
  and the original Phase 1 acceptance evidence.
- [Original project plan](PROJECT_PLAN.md): historical product goals and future
  acceptance criteria. Unchecked boxes are the original plan, not current status.
- [GUI design plan](PHASE_7_GUI_PLAN.md): original six-page design; distinguish
  implemented first-GUI coverage from planned forms and Paper writes.

### Historical acceptance and reviews

| Record | Evidence scope |
|---|---|
| [Phase 0](PHASE_0_REPORT.md) | Initial package/config/CLI and synthetic fixture |
| [Phase 2](PHASE_2_REPORT.md) | Adapters, universe modes, screening and real descriptive probes |
| [Phase 3](PHASE_3_REPORT.md) | Factor diagnostics and R1–R5 corrective reviews |
| [Phase 4](PHASE_4_REPORT.md) | Synthetic USD ML/walk-forward, boundary and perturbation checks |
| [Phase 5](PHASE_5_REPORT.md) | CAD/FX/Paper accounting, persistence and independent numerical checks |
| [Phase 6](PHASE_6_REPORT.md) / [agent review](PHASE_6_CODE_REVIEW.md) | Product integration, readable inputs, software acceptance and review provenance |
| [Paper report acceptance](REPORTING_UX_ACCEPTANCE.md) | Original static Paper report visual/numerical checks; later reports supersede its deferred scope |
| [Phase 7](PHASE_7_REPORT.md) | Shared research reports, first GUI and browser/AppTest evidence |
| [Pre-publication review](PUBLICATION_REVIEW.md) | Dated 2026-10-31 credential/history, licensing, packaging and install evidence |

Original review JSON/hash files remain under [Phase 6 evidence](reviews/phase6/INDEPENDENT_REVIEW.md)
and are linked from the relevant reports. Review tools and generated HTML/PDF in
ignored local paths are not downloadable repository assets. AI-assisted
implementation and agent-run reviews are identified as such; local tests, remote
CI and real-market research are different forms of evidence.
