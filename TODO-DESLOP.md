Prefix: DSLP
Next: 7

Deslop campaign backlog ([plan](https://github.com/laputa-systems/stuff/blob/main/docs/campaigns/deslop.md), tier Calibration). One agent works this file with the `deslop` skill: take the lowest-numbered open ticket whose area does not start with `Needs owner ·`. After DSLP-5, work the open P1 and P2 findings, then fill in `## Report` below.

Ground evidence at 4968f8e: the plan fixture has a local pytest.ini; PR 15 CI passed at 0c57bde9, and the supported workflow shape and baseline costs are recorded in [Ground evidence](docs/deslop-ground.md).

## Report

Hook errors (DSLP-6) were repaired in [#22](https://github.com/joshuarli/pytest-parallel/pull/22). The [installed-wheel evidence](docs/deslop-hook-errors.md) verifies that exceptions propagate before a plan or worker starts.

Event-stream scenario: bounded coordinator intake and dispatch mutation, real-worker stream witnesses, and the invalid UTF-8 fix are recorded in [event-stream evidence](docs/deslop-event-stream.md). Broader DSLP-4 remains open.

Scheduling scenario: serial mutmut 3.8.1 selected 276 identities, with 264 killed, 11 equivalent survivors and one confirmed timeout; mutated-module activation and the negative control are recorded in [scheduling evidence](docs/deslop-scheduling-tests.md). DSLP-4, the broader Tests audit and whole-change CI remain open.

Coverage prerequisite at `85ef2ff`: native coverage.py measured both worker-only branch outcomes in an installed-wheel witness; the negative control removed worker measurements and failed its oracle. Package-wide coverage and the test-pyramid audit are in [coverage evidence](docs/deslop-coverage.md). Actual pre/test/post gates all exit 0; individual warm observations are 7.46s before and 7.53s after. Parent's portable target and cleanup correction pass all 120 instrumented tests and lint, with 1484/1760 lines and 554/716 branches covered. Mutation, decision dispositions, CI and other platforms remain open; DSLP-4 is not complete.

Diagnose at `0ecb2b3`: reviewed first-party Python, tests, manifests, CI/release configuration, docs, both backlogs and recent churn. Lenses covered public hooks and CLI, scheduling, errors, worker lifecycle and JSONL reconciliation, argument/environment forwarding, network guard, tests, dependencies and documentation. One P2 finding (DSLP-6); no P1, P3 or P4 findings. Built-wheel synthetic hook probes reproduced the finding; baseline Ruff and ty passed. Linux, Windows, consumer integration, live release/registry paths, broader plugin combinations, performance, coverage and mutation were not exercised; coverage and the in-memory plugin limitation remain DSLP-4. No runtime, consumer or performance claim follows from this docs-only pass. Types is recorded below; DSLP-4 Tests is next, with DSLP-6 deferred to Findings.

Types at `60129d817c3f82f075a8a8dc12578866ed135a10` (macOS, Python 3.15, ty 0.0.101, Ruff 0.17.4): no setting adopted; zero findings alone do not justify one. The existing profile passed before and after. First-party hatch **matching lines** (`cast\(|# type: ignore|# ty: ignore|\bAny\b|# noqa`, all tracked Python in `src`, `tests`, `benchmarks`, `scripts`): 76 before and after, including 75 in the ty scope. This counts lines, not individual occurrences. No source or configuration changed, so no new witness is required; none of the candidates met the adoption test.

| Candidate | Diagnostics | Decision and evidence |
| --- | ---: | --- |
| ty `blanket-ignore-comment`, `disjoint-cast`, `dynamic-function-decorator-return` | 0 each | Reject: no demonstrated defect or removed trust. |
| ty `missing-type-argument` | 4 | Reject: two bare lists are public hooks (`plugin.py:33,37`), whose signatures are out of scope; two bare dicts (`test_campaign.py:36,154`) consume unvalidated dynamic JSON. A fabricated shape would not remove trust. |
| ty `possibly-unresolved-reference` | 0 | Reject: no demonstrated defect or removed trust. |
| ty `unsound-assignment`, `unsound-return-statement` | 1 each | Reject: same false inference at `scheduling.py:80,81`: `parent` starts as integers from `range` and only integer indices are assigned at lines 79, 87; explicit `parent: list[int]` still produced both diagnostics. One false positive in 4,962 scoped lines exceeds the limit. |
| ty `unsound-yield`, `unsupported-dynamic-base`, `unused-ignore-comment` | 0 each | Reject: no demonstrated defect or removed trust. |
| Ruff `ANN` / `ANN401` | 55 / 28 (overlap) | Reject: 28 explicit dynamic annotations include pytest hooks, socket forwarding and test doubles (`coordinator.py:305`, `network.py:92`, `test_p0_correctness.py:304`); other findings include test fixture and return annotations (`test_partition.py:100`) and a pytest hook generator (`plugin.py:197`). They are not all defects; broad enforcement would require extensive intentional API cleanup. Dynamic first-party plan/event dictionaries remain a typing gap. |
| Ruff `PGH003` | 0 | Reject: no demonstrated defect or removed trust; existing ignores specify codes. |
| Ruff `TC` | 24 | Reject: type-only import suggestions and quoting casts, e.g. `api.py:4`, `coordinator.py:613`; no demonstrated defect or removed trust and import changes may affect runtime introspection. |
| Ruff `B`, `RET` | 0 each | Already selected (with existing exceptions); no extra setting justified. |

Measurement commands: set `TMPDIR="$PWD/.work/tmp"`, `UV_PROJECT_ENVIRONMENT=/Users/josh/repos/pytest-parallel/.work/wt/ds-ground-finish/.work/ground-final`, `UV_NO_SYNC=1`, `UV_PYTHON_DOWNLOADS=never`, `PYTHONPATH="$PWD/src"`; `cpu-guard --cores 2 -- uv run ty check --output-format concise` and `cpu-guard --cores 2 -- uv run ruff check` exited 0. For each ty rule in the table, `uv run ty explain rule "$rule"` exited 0, then `cpu-guard --cores 2 -- uv run ty check --output-format concise --error "$rule"` exited 1 for the three nonzero rules and 0 for the rest. For each Ruff family in the table, `cpu-guard --cores 2 -- uv run ruff check --isolated --select "$rule" --output-format concise src tests benchmarks scripts` exited 1 for ANN, ANN401 and TC, 0 otherwise. `rg -c 'cast\(|# type: ignore|# ty: ignore|\bAny\b|# noqa' src tests benchmarks scripts | awk -F: '{n += $2} END {print n}'` gave 76. The explicit-list experiment was reverted. Final `cpu-guard --cores 2 -- make test` exited 0 (119 passed), and `cpu-guard --cores 2 -- make lint` exited 0 (Ruff and ty passed), with the same environment. `todo --file TODO-DESLOP.md close DSLP-3` and `todo --file TODO-DESLOP.md check` exited 0. No runtime, import, public API or configuration change: consumers and performance are unaffected and were not tested; coverage and mutation remain DSLP-4. DSLP-6 remains deferred. Tooling gap: ty's recursive-list inference emits the two false positives above.

To reproduce without the earlier scratch environment, set
`UV_PROJECT_ENVIRONMENT="$PWD/.work/typing-env"` and
`UV_PYTHON_DOWNLOADS=never`, run `uv sync --locked`, then use the individual
checker commands above with that environment and `PYTHONPATH="$PWD/src"`.
The manifest and lockfile pin the same tools; no prior scratch file is needed.

## Tickets




### DSLP-4 · P2 · Tests: coverage, boundary gaps, mutation

- **Area:** deslop · tests
- **Where:** src/pytest_parallel, test suites, Makefile and hosted CI
- **Problem:** docs/deslop-tests-inventory.md names protected plugin, scheduling, supervision, event, reporting and local socket boundaries with current evidence and gaps. make coverage verifies both worker profiles. The whole-change gate and its hosted controls remain open.
- **Recommendation:** Reconcile the named regions to current source, fill the remaining witnesses and retain the serial mutation union. Establish paired suite cost and exercise the complete workflow controls in docs/deslop-tests-inventory.md.
- **Fix with:** deslop
- **Effort:** M

### DSLP-5 · P2 · Dead code: tools and debloat

- **Area:** deslop · dead code
- **Where:** whole repository
- **Problem:** No dead-code scan has run.
- **Recommendation:** Run the deslop Dead code step. Accept: tools clean or allowlisted with reasons; walk-backs filed as Needs owner tickets.
- **Fix with:** deslop
- **Effort:** M
