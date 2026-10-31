# Phase 7 synchronization and publication readiness

Review date: **2026-10-31 (America/Toronto)**. Version **0.7.0**, **Early Beta / Work
in Progress**. The author confirmed first-GUI startup and operation on Windows.
This round authorizes private synchronization, not public visibility or a Release.

**Draft: local audit/checks recorded; candidate commit and exact-SHA remote CI pending.
This draft is not READY FOR PUBLICATION.**

## Scope and preservation

- Starting `codex/phase-7-gui`, HEAD/main
  `30049898b042b85acb29b5d7cda1c48545fb3016`.
- All **36** existing changed/untracked Phase 7 files preserved byte-for-byte in
  ignored `work/public-readiness/phase7-start-backup`, with SHA-256 inventory and
  binary diff. The older 18-file report preservation remains intact.
- Candidate: unified reports, first GUI/services/tests, English README, synthetic
  screenshots, notices and launcher portability. Financial/model/backtest/risk/ledger
  logic is unchanged. Preserve all history/branches, fast-forward main and normal
  private push only. No force push, history rewrite, visibility change or Release.

## Git and credential audit

Origin **yufeizhang06/PortfolioResearchDesk / PRIVATE** was checked through the GitHub
API, then fetched normally with tags. At audit start: **6 remote branches, 9 local
branches, 0 tags, 0 PRs, 13 reachable commits**. Local-only history branches are included.

[Gitleaks](https://github.com/gitleaks/gitleaks) **8.30.1** came from its official
release; archive SHA-256 matches the published checksum. Default rules, redaction
and no inline suppression:

```text
gitleaks git . --log-opts="--all --full-history" --redact --ignore-gitleaks-allow
gitleaks dir <all-unique-historical-blobs> --redact --ignore-gitleaks-allow
gitleaks dir <candidate-source-export> --redact --ignore-gitleaks-allow
gitleaks dir <downloaded-GitHub-surfaces> --redact --max-archive-depth=2
```

Initial scans covered all **13 commits**, **293 complete unique blobs / 158 historical
paths** (including later changed/deleted versions), and a separate export of tracked
plus nonignored untracked candidate files. **No secret findings.** Staged/final-commit
scans are required before push; the working tree is not inferred from historical HEAD.

Manual checks supplement scanner patterns with all historical filenames, commit
identity, paths/emails, data provenance, images and distribution contents:

| Category | Findings/disposition |
|---|---|
| Credentials | No Gitleaks findings or confirmed keys, tokens, passwords or private keys |
| `.env`, environments, caches, SQLite/private accounts, debug logs | No such tracked paths in any starting commit; local work/data/outputs stay ignored |
| Personal email | Commit metadata uses GitHub `users.noreply.github.com`; no private email in source/history |
| Author | Existing **Yufei Zhang** attribution stays in commit metadata and will be visible with history |
| Absolute paths | Phase 0/4 evidence contains generic `C:/Users/Desktop/...` paths, without a personal username or credential; history is not rewritten |
| Screenshots | Actual synthetic GUI; sidebar paths excluded by crop, results unedited |
| Data | Self-authored synthetic observations/directory/factors; real-input configs contain no downloaded raw data |

The author name, owner handle and generic historical paths are disclosed residual
metadata. This is not an anonymity claim. Scanners reduce risk and cannot prove the
absence of every unknown secret. Raw findings and original logs stay ignored/local.

## GitHub surfaces and Actions logs

GitHub says public visibility also exposes
[Actions history/logs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility).
All **12 existing runs / 12 attempts / 48 log entries** downloaded successfully.
Gitleaks scanned expanded logs and ZIPs: **no credential findings**. Supplemental
path matches were all generic hosted `/home/runner/...` paths, manually classified.
No private email/credentials found. Newly created CI runs must be scanned separately.

Starting API inventory: **0 artifacts, issues/PRs, issue comments, commit comments,
releases, deployments or environments**. Nothing was deleted or made public.

## Data rights and dependency notices

- Own code/docs/synthetic fixtures: author-confirmed **MIT**, retained in distributions.
  Screenshots contain only results from those fixtures.
- Lock: **76 packages including this project**. **74 installed third-party packages**
  on Windows match the lock; one platform-selected package is absent. No mismatches.
- Installed metadata/license files reviewed. The sole metadata gap, **Peewee 4.5.3**,
  was resolved with its installed license and
  [upstream MIT grant](https://github.com/coleifer/peewee/blob/master/LICENSE).
- Dependencies are installed separately, not vendored. Bundled native components
  retain their notices. This review covers project source/wheels, not a repackaged
  Python environment or blanket legal certification.
- [yfinance](https://ranaroussi.github.io/yfinance/) separates software and Yahoo data
  rights; [Nasdaq](https://www.nasdaqtrader.com/trader.aspx?id=symbollookup) and
  [French](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
  inputs have separate rights. No downloaded raw or derived real-market dataset/plot
  is redistributed. MIT does not authorize publishing local real caches/reports.

See [third-party notices](../THIRD_PARTY_NOTICES.md) and [data policy](DATA_POLICY.md).

## README and clean installation

English README includes all requested overview/features/screenshots/status/install/
GUI/architecture/testing/data-rights/limits/roadmap/MIT sections. It states partial
GUI coverage and English page names / primarily Chinese controls. Screenshots were
visually checked for paths/private data; no synthetic metric is called market evidence.

An empty source copy in **a path containing spaces** had no `.venv`, `.git`, local
`work/bin` or private inputs. uv/Python were supplied through PATH as ordinary
installed prerequisites; only the dependency cache was reused:

- Actual `Setup GUI.cmd` created a new environment with all extras.
- Actual `Start GUI.cmd` listened on 127.0.0.1:8501; health **200**.
- API-key/token/secret/password environment variables removed.
- No-key complete synthetic CLI workflow and manifest check passed.
- Real browser: new workspace, isolated CAD demo, read-only Paper/Home account and
  Factor output produced by that clean installed backend. No original working-tree
  imports or patched financial results.
- Launchers resolve their own directory. uv-on-PATH was exercised; this host has no
  standalone `py`, so Python-launcher fallback was inspected but not executed.

This proves a new source/environment install using cached locked packages, not an
offline first install with no cached dependencies.

## Quality gates and CI

| Gate | Current evidence |
|---|---|
| Starting complete regression | **742 passed**, 60.35s; all old tests retained |
| Final regression / Ruff / lock | **742 passed**, 60.34s; Ruff check/format PASS (136 files); 76-package lock check PASS |
| Current sdist / both wheels / independent installs | PASS: sdist rebuild, direct/rebuilt wheels, full factors/ML workflows and GUI AppTest; `work/public-readiness/distribution-install.log` |
| Candidate SHA, safe main/private synchronization | Pending |
| Actual Ubuntu and Windows CI at exact SHA | Pending |
| New CI logs and final refs | Pending |

Tests block external sockets; GUI AppTest alone allows loopback. Commands follow
README, with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and local uv cache on this host.
Distribution contents were inspected: **185 sdist entries / 92 wheel entries**;
no work/cache/private account/SQLite/log directory was included. All README relative
links/images exist. The final launchers also passed Setup success and missing
Python/uv failure checks (exit 2) in an isolated directory.

## Publication decision and limits

**Pending final commit, installation and exact-SHA remote CI.** No visibility change
is authorized/performed. The owner must personally decide whether to publish this
repository and its disclosed historical metadata after the final gate results.

Early-beta limits: local single-user app, partial Chinese GUI, pending screening/
ML/backtest forms and Paper write wizards; no certified real PIT/OOS or arbitrary
real-pool backtest; incomplete calendars/delistings/corporate actions; no broker.
Passing tests and synthetic examples does not imply investment profit.
