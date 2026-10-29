# Delivery and release readiness

Phase 6 delivers **development version v0.7.0**, not an official v1.0.0 release.
The user has authorized final acceptance, normal commits, safe main integration
and synchronization to the existing private repository. Package upload, public
visibility and a formal GitHub Release remain outside this authorization.

| Gate | Phase 6 position |
|---|---|
| Installable wheel/sdist and packaged examples | Checked locally; exact evidence in PHASE_6_REPORT |
| Complete offline workflow and separate manual Paper lifecycle | Required acceptance checks, including restart and exports |
| All prior tests plus new regression/boundary/E2E tests | Exact counts and commands in PHASE_6_REPORT |
| Independent Code Review | Report/fix/retest evidence in PHASE_6_REPORT |
| Linux / Windows CI for Phase 6 | Exact-SHA actual results recorded in PHASE_6_REPORT; configuration alone is not acceptance |
| English README, user/developer guides and known limitations | Included in this candidate |
| Own-code license | MIT confirmed by the user on 2026-10-28; no publication performed |
| Third-party data and binary redistribution | Separate permissions; no blanket clearance or raw observations shipped |
| Dashboard | Deliberately deferred; local HTML plus shared CLI services |
| Real PIT/OOS trading evidence | **Not certified; not implied by passing software tests** |

The authorized synchronization process reruns the full local suite, checks the
actual user workflow, reviews candidate files and installs both wheels outside the
source tree. Only after passing these gates may the Phase 6 branch be committed,
safely fast-forwarded to main and normally pushed. Exact-SHA Ubuntu/Windows CI must
then actually pass; real failures must be fixed. Preserve all history/branches and
stop for the user's own experience acceptance. See PHASE_6_REPORT for actual status.

Before a public product release, separately review all Definition of Done items in
PROJECT_PLAN, current data licenses, personal identifiers in history/docs, release
contents and dependency notices. Authorize any visibility/Release action explicitly.
Unverified real-data PIT assumptions must remain visible even if a software-only
release is later approved. Further real-data validation or a dashboard is future
work, not an automatic next phase.

## Work remaining before v1.0.0

- The author must complete hands-on user experience acceptance of installation,
  configuration, error messages, report navigation and ongoing Paper operations.
- Reconcile the original Definition of Done against implemented versus explicitly
  unsupported behavior. The fixed demo is not arbitrary real-universe automation;
  real PIT/OOS certification and historical membership remain unsupported.
- Decide the release scope and required evidence for real-data timing, calendars,
  delistings, sector histories, FX provenance and supported corporate actions.
  If any remain unverified, retain explicit limits rather than implying certification.
- Review greedy sizing/cash utilization, account backup/recovery practices and
  future migration policy against the intended daily use. Streamlit stays optional.
- Review exact release contents, notices, data redistribution permissions and any
  platform claims. macOS remains untested. Explicit release/visibility authorization
  is required; passing Phase 6 does not automatically publish v1.0.0.
