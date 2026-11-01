# Phase 6 independent Code Review

Historical review date: **2026-10-28**. The reviewer was a separate AI agent.
The original report and JSON/hash receipts remain unchanged; their status statements
describe that date. Current support is in the [README](../README.md).

The [independent review report](reviews/phase6/INDEPENDENT_REVIEW.md) records
scope, actual probes, initial/final evidence reconciliation and limitations.

**Conclusion:** no unresolved actionable P1/P2/P3 findings in the reviewed scope.
Reviewer-run tests: **80 passed**. Author full-suite evidence: **689 passed**.
The reviewer also independently verified a mixed CAD/USD readable-input lifecycle
and Fraction-derived NAV of **2929.9000 CAD**, plus failure paths and recovery.

- [Final reviewed file hashes](reviews/phase6/reviewed-file-hashes-final.json)
- [Initial reviewed file hashes](reviews/phase6/reviewed-file-hashes.json)
- [Final hash reconciliation](reviews/phase6/final-hash-reconciliation.json)
- [Independent numerical probe results](reviews/phase6/probe-results.json)
- [Documented command checks](reviews/phase6/final-evidence-check.json)

The report is copied verbatim from the separate reviewer. Its initial missing
PHASE_6_REPORT link was a documented in-progress integration item; that report
now exists and final local link checking passes. The original probe script and
raw run logs remain in ignored `work/phase6-review/` / `work/`, not in the product
package as executable fixtures. This review is not a remote CI, legal clearance,
real PIT/OOS certification or release approval.

## Historical license reconciliation

On 2026-10-28 the project adopted MIT. The implementation agent updated the license
status wording in README, third-party notices and delivery documentation. LICENSE,
packaging license metadata, financial code, tests and dependencies are unchanged.
The independent report and its hashes remain the original reviewed snapshot;
At that checkpoint README, THIRD_PARTY_NOTICES and RELEASE_READINESS differed
only in that wording. Later documentation maintenance does not update the original hashes.
This documentation follow-up is not represented as a new independent review.

## Final acceptance reconciliation

The later Phase 6 acceptance rechecked all reviewed production, tests,
configuration and build scripts against the independent snapshot, reran all 689
tests and the actual CLI lifecycle, and changed only documentation/status wording.
The independent review narrative is retained as historical evidence; its remarks
about uncommitted status describe the review date, not the later synchronization.
Raw snapshot hashes record workstation bytes; Git normalizes text line endings.
Final staging separately checks canonical LF content without treating line-ending
normalization as a new algorithm or silently rewriting the reviewer's hashes.

## Public regression entry points

After the full [development setup](../CONTRIBUTING.md#development-setup), these
checked-in tests cover related contracts:

| Contract | Public test module |
|---|---|
| Readable input validation, provenance/time and explicit target checks | [test_paper_inputs.py](../tests/test_paper_inputs.py) |
| Shared synthetic workflow, independent NAV, pending ML preview and manifest integrity | [test_product_workflow.py](../tests/test_product_workflow.py) |
| CAD/FX accounting identities | [test_cad_accounting.py](../tests/test_cad_accounting.py) |
| Transaction/replay/idempotency boundaries | [test_paper_store.py](../tests/test_paper_store.py) |

```bash
uv run --locked --offline pytest -p pytest_socket -q tests/test_paper_inputs.py tests/test_product_workflow.py tests/test_cad_accounting.py tests/test_paper_store.py
```

This is a current public regression entry point, not a reconstruction of the
original 80-test review or unpublished probe script. The historical Fraction NAV
and snapshot hashes remain the original agent-run evidence; they are not a new
human review or proof that the original local tooling is publicly reproducible.
