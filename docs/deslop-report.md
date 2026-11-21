# Deslop Report

Campaign backlog: `TODO-DESLOP.md`, deleted by `26119f6` in [#43](https://github.com/joshuarli/pytest-parallel/pull/43). This report is reconstructed from the deleted backlog's own `## Report` (recovered with `git show 22e9e57^:TODO-DESLOP.md`), PR #43, the `docs/deslop-*.md` evidence records, and the merged deslop PRs. Every number below names its source. Anything the record does not establish is marked **unverified**.

## Scorecard

| Metric | Before | After | Source |
| --- | ---: | ---: | --- |
| First-party source lines (`src/**/*.py`) | 2,654 at `4968f8e` | 2,635 at `22e9e57` | `git ls-tree -r <rev> src \| grep '\.py$' \| … wc -l`; the 2,644 → 2,635 step figures are in the `f80cdcb` review paragraph |
| Test lines (`tests/**/*.py`) | 2,308 at `4968f8e` | 3,445 at `22e9e57` | same command over `tests`; step figure 3,445 in `f80cdcb` (benchmark self-tests excluded) |
| Test files | 8 at `4968f8e` | 9 at `22e9e57` | `git ls-tree -r <rev> tests` |
| Tests passing | 119 (`4968f8e`, `docs/deslop-ground.md`) | 212 (PR #43 description; re-confirmed locally, see below) | recorded in each source |
| Warm `make test` | 7.50s cold and 7.48s warm for 119 tests; 7.46s base observation | 7.53s for 120 tests; 6.42s for 120 tests | `docs/deslop-ground.md`; `docs/deslop-coverage.md`; individual observations, not a speed claim |
| Line coverage | 1,545/1,759 at `e54d5b2f` (historical) | 1,484/1,760 (`make coverage`) | `docs/deslop-tests-inventory.md`; `docs/deslop-coverage.md` (which also prints 1,483/1,760 in an earlier paragraph; both are recorded observations, not a threshold) |
| Branch coverage | 586/718 (historical) | 554/716 plus 139 partial | same sources |
| Serial-baseline coverage | — | 82% combined (1,760 statements, 277 missed) | `docs/deslop-coverage.md` |
| Mutants (scheduling) | 87 caught / 19 survived / 1 timeout / 169 no-tests | 264 caught / 11 survived / 1 timeout / 0 no-tests | `docs/deslop-scheduling-tests.md` |
| Mutants (event stream) | 124 caught / 28 survived of 152 | 146 caught, 6 survivors | `docs/deslop-event-stream.md` |
| Mutants (worker reports) | 0 killed / 60 no-tests | 59 killed / 1 survivor, then 60 caught | `docs/deslop-worker-reports.md` |
| Mutants (options) | 82 caught / 27 survived / 18 no-tests | 126 caught / 1 survivor of 127 | `docs/deslop-tests-inventory.md` |
| Mutants (coordinator file planning) | 33 of 83 caught | 67 caught, 12 survivors; follow-up 79/79 | `docs/deslop-tests-inventory.md` |
| Mutants (pins and worker limits) | 9 of 64 caught | 61 caught, 3 redundant survivors; follow-up 51/51 | `docs/deslop-tests-inventory.md` |
| Mutants (report events) | 68 of 111 caught | 107 caught; follow-up 105/105 | `docs/deslop-tests-inventory.md` |
| Mutants (stop and drain) | 39 of 167 caught | 114 caught, 51 survivor identities open | `docs/deslop-tests-inventory.md` |
| Escape hatches (matching lines) | 76 at `4968f8e` | 83 at `22e9e57` | `rg -c 'cast\(\|# type: ignore\|# ty: ignore\|\bAny\b\|# noqa' src tests benchmarks scripts` on each tree |
| Dead code removed | — | 1 uncalled wrapper, 2 write-only fields, 9 source lines | `5b7096d` |
| Dependencies | — | no runtime dependency added or removed; `coverage==7.17.3` added to the `dev` group | `git diff 4968f8e..HEAD -- pyproject.toml`; runtime `Requires-Dist` stayed `pytest>=9.0` (`docs/deslop-coverage.md`) |

The escape-hatch rise is explained by the Tests step: `tests/test_p0_correctness.py` went from 6 to 14 matching lines while `coordinator.py` fell from 40 to 39. The other files are unchanged. I confirmed the per-file counts at both revisions; I did **not** re-classify each new line as a justified hatch versus a defect, so their soundness is **unverified**. The Tools step documents that a lower count is evidence only when the replacing claim is sound.

### Mutant totals caveat

These are separate bounded scenarios over selected functions, run with growing test selections, not one whole-package mutation score. `docs/deslop-scheduling-tests.md` records it plainly: "not a whole-package or CI qualification." The network trial's 121 identities with 50 killed and 71 survivors are explicitly unqualified, because generated-source activation was never verified and its timeouts were never confirmed (`docs/deslop-network-guard.md`). The timeout total across scenarios is one confirmed infinite loop in scheduling plus two unconfirmed historical network timeouts.

### Findings

| Priority | Filed | Fixed | Source |
| --- | ---: | ---: | --- |
| P1 | 0 | — | Diagnose paragraph, `TODO-DESLOP.md` |
| P2 | 1 (DSLP-6) | 1 ([#22](https://github.com/joshuarli/pytest-parallel/pull/22)) | `docs/deslop-hook-errors.md` |
| P3 | 2 (DSLP-7, DSLP-8) | 0, moved to `TODO.md` as PAR-15, PAR-16 | `TODO.md`; PR #43 |
| P4 | 0 | — | Diagnose paragraph |

### Performance verdict

No performance verdict is claimed. The suite-cost and paired-workload observations overlap: 7.46s → 7.53s suite cost, 1.188s vs 1.213s median in the hook-error workload, 1.260s vs 1.263s in the event-stream workload, and base 14.77s vs candidate 15.81s in the parent suite-cost run (`docs/deslop-hook-errors.md`, `docs/deslop-event-stream.md`). Several attempts were discarded for hot-host diagnostics. The campaign record also states no representative workload exists for a meaningful runtime comparison.

### Escaped regressions

None known from this lane. The Diagnose and cumulative review both report no other demonstrated defect beyond the ones fixed, and PR #43's CI passed. This is a statement about the record, not an exhaustive proof.

## Per step

**Ground** ([#16](https://github.com/joshuarli/pytest-parallel/pull/16), `docs/deslop-ground.md`). Qualified the workflow shape, baseline costs, dependency surface and the absence of vendored code. Cold and warm `make test` took 7.50s and 7.48s for 119 tests; `make lint` took 1.18s. Cost: one local run plus CI already run by PR 15. CI minutes for the ground step are **unverified**; the record does not state them.

**Diagnose** ([#17](https://github.com/joshuarli/pytest-parallel/pull/17)). Reviewed first-party Python, tests, manifests, CI and release configuration, docs, both backlogs and recent churn across the public hooks, CLI, scheduling, errors, lifecycle, JSONL reconciliation, argument forwarding, network guard, tests, dependencies and documentation. Found one P2 (DSLP-6) and nothing at P1, P3 or P4. Cost not recorded.

**Types** ([#18](https://github.com/joshuarli/pytest-parallel/pull/18), evidence in the Types section of the recovered `TODO-DESLOP.md` Report at `60129d8`). Tested each ty rule and the Ruff `ANN`, `ANN401`, `PGH003`, `TC`, `B` and `RET` families. Adopted no new setting; two `unsound-*` diagnostics at `scheduling.py:80,81` were the same false inference and an explicit `list[int]` annotation still reproduced them. Escape hatches stayed at 76 matching lines. Cost: per-rule checker invocations; no CI minutes.

**Tests** ([#19](https://github.com/joshuarli/pytest-parallel/pull/19), [#20](https://github.com/joshuarli/pytest-parallel/pull/20), [#23](https://github.com/joshuarli/pytest-parallel/pull/23), [#24](https://github.com/joshuarli/pytest-parallel/pull/24), [#25](https://github.com/joshuarli/pytest-parallel/pull/25), [#27](https://github.com/joshuarli/pytest-parallel/pull/27), [#28](https://github.com/joshuarli/pytest-parallel/pull/28), [#29](https://github.com/joshuarli/pytest-parallel/pull/29), [#30](https://github.com/joshuarli/pytest-parallel/pull/30), [#31](https://github.com/joshuarli/pytest-parallel/pull/31), [#33](https://github.com/joshuarli/pytest-parallel/pull/33), [#38](https://github.com/joshuarli/pytest-parallel/pull/38), [#40](https://github.com/joshuarli/pytest-parallel/pull/40); closed by `3528488` in PR #43. The native subtest replay fix is [#39](https://github.com/joshuarli/pytest-parallel/pull/39), which is not deslop-labelled but is recorded in the inventory as campaign-era work. The other merged deslop PRs are [#13](https://github.com/joshuarli/pytest-parallel/pull/13) (seed), [#14](https://github.com/joshuarli/pytest-parallel/pull/14) (qualify), [#15](https://github.com/joshuarli/pytest-parallel/pull/15) (fixture isolation) and [#26](https://github.com/joshuarli/pytest-parallel/pull/26) (empty-address bind fix). Built the finite [inventory](deslop-tests-inventory.md) of public contracts and critical decisions, filled witnesses for scheduling, option parsing, coordinator planning, pins, report events, stop and drain, worker reports, the event stream, the network boundary and native subtest replay. Coverage became a portable `make coverage` target with an installed-wheel worker/branch oracle and a negative control; a real consumer (stuff `repomod`) measured 22,010/25,735 lines and 8,043/10,612 branches. Cost: the scheduling mutation target took 93.67s wall including timeout confirmation; option parsing runs took about seven seconds; report-event and worker-report mutation runs did not record wall time; the aggregate attempt in the unmerged PR #32 exhausted 1,200s at 130 of 559 coordinator mutations. Hosted CI ran per PR; per-step CI minutes are **unverified**.

**Dead code** (`5b7096d`). Ruff `F401`/`F841` was clean; vulture 2.16 and deptry 0.25.1 found only dynamic false positives plus the removed items. Removed `Coordinator.build_plan`, `WorkerState.session_shouldfail` and `ResultReporter._collection_finished`. The wire `session_finish` field remains. No lint gate added, no dependency removed.

**Bench** (`2589bca`, PR #43). Added `benchmarks/bench.py` with Edit/Change/Scenario/Full tiers, harness tests, and `make bench`, `bench-check`, `bench-list`. The Edit tier and the uneven Change workload ran; host readiness was uncertain and no timing verdict was claimed. The remaining gaps became PAR-15 and PAR-16.

**Close** (`26119f6`, PR #43). Moved the P3 tickets to `TODO.md` and deleted `TODO-DESLOP.md`.

**Report** (`f80cdcb`, PR #43). Cumulative review of the diff from `eb11974`. It found that preflight checked for the readiness tool without reporting readiness, and made it report the probe as informational.

## Follow-up

[#32](https://github.com/joshuarli/pytest-parallel/pull/32) is an open **draft** trial of a serial whole-change mutation selector and bounded mutmut driver. Its options shard passed with 126 caught and one equivalent; isolated test-deletion and uncovered-branch controls failed as intended; a mixed control selected both regions; a docs-only control selected none. Its first aggregate attempt exhausted its 1,200-second budget after 130 of 559 coordinator mutations, and coordinator witnesses, the mixed execution control, complete platform results and cost remain open. It is follow-up work, not a blocker for this campaign, which closed on the finite inventory and the November 20 ruling on mutation scope.

## Method feedback

- The escape-hatch count rose during Tests without a rule requiring each new line to be justified. A per-step diff of matching lines, not just a before/after total, would have shown the increase where it happened.
- Coverage has two adjacent totals for the same revision (1,483 and 1,484 covered lines). A single canonical export would avoid a reader having to treat both as observations.
- The network mutation trial ran without first verifying that executed tests loaded the instrumented source. An activation control at the start, as the later scenarios used, would have prevented publishing unqualified counts.
- The `avoid` class of findings dominated: vulture's dynamic-hook hits and ty's `unsound-*` false positives consumed effort with no defect behind them. Grouping them by discovery mechanism, as the dead-code step did, is the right shape.

## Shared-file gaps

- `~/.agents/skills/deslop/references/tools.md` still says "pytest-parallel has no coverage support yet: run coverage serially there." Native worker coverage is established here (see [coverage evidence](deslop-coverage.md)); the row is stale. The related note that mutmut cannot run through pytest-parallel remains true and is why every scenario above runs serially with `-p no:parallel`.
- No fleet-level template covers a deliverable `docs/deslop-report.md`; the spec only defines a `## Report` section inside a backlog file, which the close step deletes. A tracked report path in the reference would keep the report reachable without reconstruction.

## Unverified

- CI minutes per step, and total campaign CI minutes: not stated anywhere in the record.
- Coverage, mutation and suite costs at the final HEAD: the recorded coverage and mutation figures are at their own step revisions. I re-ran the suite (`212 passed`) and lint locally; I did not re-run coverage or mutation at `22e9e57`.
- Soundness of each individual escape hatch added by the Tests step.
- Linux, Windows, arbitrary third-party plugin combinations and the remaining unselected coordinator/worker decisions.
- Whether the shared `tools.md` coverage row has been corrected upstream: the reference in this environment still carries the stale text.

## Current local check

At `22e9e57`, with `TMPDIR=$PWD/.work/tmp` and a locked environment, `cpu-guard --cores 2 -- make test` exited 0 with `212 passed in 32.60s`, and `cpu-guard --cores 2 -- make lint` exited 0 with Ruff and ty passing. `perf-gate-ready` exited 75 (host busy), so the duration is an observation, not a gated result. No code changed for this report.
