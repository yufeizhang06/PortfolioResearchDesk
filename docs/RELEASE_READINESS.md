# Delivery and release readiness

## Current status

PortfolioResearchDesk is a **public source repository**, version **0.7.0**, Early
Beta / Work in Progress. Public availability is separate from a formal product
release; no formal v1.0.0 Release is recorded. Use the
[README capability matrix](../README.md#current-development-status) and
[known limitations](../README.md#known-limitations) for current support.

The first optional Streamlit GUI implements Home, Stock Explorer and Factor
Research, with read-only Paper views. Screening/ML/backtest forms and Paper write
wizards remain pending. The backend/CLI has broader capabilities than the GUI.
Windows GUI startup/operation was manually confirmed; macOS remains unverified.

## Recorded software evidence

| Gate | Dated evidence |
|---|---|
| Phase 7 functional commit | `88f1104616c489c8896626d10d765100fefd5aea`, [run 41175396204](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/41175396204): Windows 742 passed; Ubuntu 741 passed / 1 platform-specific skip |
| Phase 7 documentation closeout | `a1a686385942702cdeed41381e1597337c9d18bc`, [run 41176056821](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/41176056821): Windows 742 passed; Ubuntu 741 passed / 1 platform-specific skip |
| Build and isolated installs | Exact functional-SHA CI includes lock/Ruff/CLI checks, sdist rebuild, both-wheel independent installation and GUI smoke checks |
| Earlier product integration | [Phase 6 report](PHASE_6_REPORT.md): synthetic workflow, separate manual Paper lifecycle, restart/idempotency and independent numerical checks |
| Publication preparation | [2026-10-31 review](PUBLICATION_REVIEW.md): historical credential, data-rights, packaging and clean-install review |
| License/data boundaries | [MIT](../LICENSE), [third-party notices](../THIRD_PARTY_NOTICES.md), [data policy](DATA_POLICY.md) |

These results apply to their listed SHAs. The later `c36914a` README-only change
and any subsequent edits do not inherit an exact-SHA CI result. A CI badge is a
navigation aid, not proof that every branch or local change was tested.

Tests and synthetic examples verify software behavior, not real-market PIT/OOS
strategy performance or investment profit. The privacy review is not a blanket
license or security certification. See the [documentation index](README.md) for
current guides and the historical evidence archive.

## Work remaining before v1.0.0

- Define a release scope against the original Definition of Done and current
  supported behavior. The fixed demo is not arbitrary real-universe automation.
- Extend and validate onboarding, error messages, report navigation and continuing
  Paper operations; implement pending GUI workflows only with their required gates.
- Establish evidence for any expanded real-data claim: historical identities and
  membership, calendars, delistings, sector histories, FX provenance and corporate
  actions. Retain explicit limitations wherever evidence is incomplete.
- Review conservative integer sizing/cash utilization, backup/recovery practices,
  concurrency and migration policy before expanding account write interfaces.
- Validate installation, full regression, build and distribution contents at the
  intended release revision; record actual platform results and exact CI SHA.
- Review all included data/resources and dependency notices. Bundled environments
  require their own notice review; project MIT does not license third-party data.

Real trading, brokers, short selling and leverage remain outside the product.
