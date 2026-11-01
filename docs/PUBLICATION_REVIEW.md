# Historical pre-publication review — 2026-10-31

Review date: **2026-10-31 (America/Toronto)**. Version **0.7.0**, **Early Beta / Work
in Progress**. This is a historical review performed before public visibility;
the repository is now Public. Inventory counts, local paths and installation/CI
results below describe that review scope, not the current repository inventory.
Current capabilities and release evidence: [README](../README.md) and
[Release Readiness](RELEASE_READINESS.md).

The review recommended publication of an Early Beta source/synthetic-fixture
repository. Windows GUI startup/operation was manually confirmed. Functional
commit `88f1104` passed the dual-platform CI below; documentation commit
`a1a6863` later passed its own [run 41176056821](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/41176056821).
The repository was Private during the recorded review. No formal Release was created.

## Scope and preservation

- Starting `codex/phase-7-gui`, HEAD/main
  `30049898b042b85acb29b5d7cda1c48545fb3016`.
- All **36** existing changed/untracked Phase 7 files preserved byte-for-byte in
  ignored `work/public-readiness/phase7-start-backup`, with SHA-256 inventory and
  binary diff. The older 18-file report preservation remains intact.
- Candidate: unified reports, first GUI/services/tests, English README, synthetic
  screenshots, notices and launcher portability. Financial/model/backtest/risk/ledger
  logic was unchanged. Synchronization retained existing history/branches and used
  a fast-forward and normal push; no history rewrite or Release was part of this review.

## Git and credential audit

Origin **yufeizhang06/PortfolioResearchDesk** was verified as Private at review time through the GitHub
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
scans also passed before push; the working tree was not inferred from historical HEAD.
After committing Phase 7, the full-history rescan covered **14 commits** with no
findings; the recorded reachable-object inventory listed **306 unique blobs**.
No suppression baseline was used. These are retained historical receipt counts.

Manual checks supplement scanner patterns with all historical filenames, commit
identity, paths/emails, data provenance, images and distribution contents:

| Category | Findings/disposition |
|---|---|
| Credentials | No Gitleaks findings or confirmed keys, tokens, passwords or private keys |
| `.env`, environments, caches, SQLite/private accounts, debug logs | No such tracked paths in any starting commit; local work/data/outputs stay ignored |
| Personal email | Commit metadata uses GitHub `users.noreply.github.com`; no private email in source/history |
| Author | Existing **Yufei Zhang** attribution stays in commit metadata and will be visible with history |
| Absolute paths | The reviewed Phase 0/4 versions contained generic Windows checkout/runtime paths, without a personal username or credential; those historical versions remain accessible |
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
No private email/credentials found. Functional CI **41175396204** subsequently added
**34 log entries**, all downloaded and scanned with no findings. Supplemental path
matches were hosted-runner paths. The separate documentation-closeout run is linked above.

Starting API inventory: **0 artifacts, issues/PRs, issue comments, commit comments,
releases, deployments or environments**. Nothing was deleted or made public.
Actions cache count is **0**; wiki, Pages and Discussions are disabled.

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
| Functional SHA and synchronization | `88f1104616c489c8896626d10d765100fefd5aea`; main safely fast-forwarded and normally pushed, Phase 7 branch preserved/pushed |
| Actual exact-SHA Ubuntu CI | **741 passed, 1 skipped**, 108.41s; all CLI/lock/Ruff/build/independent-install/GUI steps successful |
| Actual exact-SHA Windows CI | **742 passed**, 137.81s; all CLI/lock/Ruff/build/independent-install/GUI steps successful |
| Functional CI logs | All **34** entries scanned; no secret findings; receipt `reviews/phase7-publication/ci-functional.json` |
| Branches, tags and visibility at review time | 9 local / 7 remote branches preserved; no tags; repository was Private |

Actual workflow: [41175396204](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/41175396204),
`workflow_dispatch` on **main**, verified against the full SHA above. The Ubuntu
skip is the Windows-drive-specific path case, not a removed regression. Automatic
push-triggered runs did not appear during this task; the workflow declares push/PR
triggers, but only manual triggering is claimed as observed. The CI badge alone is
not substituted for exact-SHA validation.

Hosted runners emitted nonblocking Node-runtime/Ubuntu-image migration annotations;
all steps passed on the actual supplied runners. Future runner migrations remain a
maintenance consideration, not evidence of support for an untested platform.

Tests block external sockets; GUI AppTest alone allows loopback. Commands follow
README, with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and local uv cache on this host.
Distribution contents were inspected: **185 sdist entries / 92 wheel entries**;
no work/cache/private account/SQLite/log directory was included. All README relative
links/images exist. The final launchers also passed Setup success and missing
Python/uv failure checks (exit 2) in an isolated directory.

## Publication decision and limits

**READY FOR PUBLICATION.** No confirmed credential, private-account, restricted-data
or source/wheel licensing blocker was found in the reviewed scope. The English
homepage, clean installation and exact functional SHA passed the recorded gates.
This recommendation covers an **Early Beta / Work in Progress code repository**;
it is not a formal v1.0 release or certification of a trading system.

This review did not rewrite history, delete logs or create a Release. Public
availability preserves author attribution and earlier content in Git history.
Credential scanning is narrower than editorial/privacy suitability: a clean scan
does not establish that temporary collaboration text belongs in public guides.
The listed CI receipts apply only to their exact SHAs, including the separately
linked documentation revision; later changes require their own validation.

Early-beta limits: local single-user app, partial Chinese GUI, pending screening/
ML/backtest forms and Paper write wizards; no certified real PIT/OOS or arbitrary
real-pool backtest; incomplete calendars/delistings/corporate actions; no broker.
Passing tests and synthetic examples does not imply investment profit.
