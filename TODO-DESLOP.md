Prefix: DSLP
Next: 9

Deslop campaign backlog ([plan](https://github.com/laputa-systems/stuff/blob/main/docs/campaigns/deslop.md), tier Calibration). One agent works this file with the `deslop` skill: take the lowest-numbered open ticket whose area does not start with `Needs owner ·`. After DSLP-5, work the open P1 and P2 findings, then fill in `## Report` below.

Ground evidence at 4968f8e: the plan fixture has a local pytest.ini; PR 15 CI passed at 0c57bde9, and the supported workflow shape and baseline costs are recorded in [Ground evidence](docs/deslop-ground.md).

## Report

Bench audit: the existing harness generates uniform, uneven, many-tiny and single-file synthetic suites, measures collection, serial and two scheduling modes plus plan wall time, and checks subprocess exit status. It does not assert exact completed counts, represent costly real suites, measure aggregate memory/CPU or tail latency, offer profiling attribution, or compare interleaved baselines against a budget. DSLP-7 records those outcome and observability gaps; DSLP-8 records preflight and provenance gaps. The tiered entrypoint adds Edit harness tests and short Change workloads on the existing harness, selection, preflight, dry-run and per-run logs. `make bench BENCH_ARGS='--tier edit'` and `make bench BENCH_ARGS='--tier change --name uneven'` passed; the latter produced measurements. Host readiness was uncertain: no timing or regression verdict is claimed. Scenario, Full, Linux and other platforms were not run. The local entrypoint does not change the plugin or its consumers.


Dead code at `3528488`: Ruff F401/F841 was clean. Vulture 2.16 reported pytest-discovered hooks, required hook/signal arguments, mock attributes and two write-only fields plus the unused coordinator wrapper; deptry 0.25.1 reported `_pytest`, which is supplied by the declared pytest dependency. Those dynamic hooks and attributes are retained as false positives, grouped by discovery mechanism; no lint gate was added. Removed the unused coordinator `build_plan` wrapper, `WorkerState.session_shouldfail` storage and worker `_collection_finished` flag. Repository search covered source, tests, docs, scripts and build registration; the public API is restricted by AGENTS.md to Shard and named hooks. The `session_finish` wire field remains. Worker hooks, entry points, scheduling and reconciliation remain registered. No dependency was removed. The ordinary macOS Python 3.15 suite and lint passed; stuff repomod at its local clone revision ran against the editable candidate (import path `src/pytest_parallel/__init__.py`): 1,512 passed, three skipped in 151.07 seconds. Linux and third-party plugins remain unverified. Structural review kept the static scheduler, JSONL protocol, isolation and cleanup machinery because they implement declared invariants; no further behavior-preserving cut was established. No walk-back was proposed.

Tests closure at `eb11974795c1b2e5e26183c992ec021c80b007d6`: the finite inventory is [Tests inventory](docs/deslop-tests-inventory.md), supplemented by the dispositions below. No new mutation or test is claimed in this closure. Consumers are stuff repomod and toolbox; this documentary step changes no plugin behavior. Acceptance is `make test`, `make lint`, and `todo --file TODO-DESLOP.md list --json`; coverage is diagnostic (`make coverage`), not a threshold. Historical macOS coverage was 1,545/1,759 statements and 586/718 branches at `e54d5b2f`; historical suite-cost comparisons are recorded in the linked scenarios and are not a current performance verdict.

| Public contract / critical decision | Guard and remaining gap |
| --- | --- |
| CLI errors, collection, plan v1, hook validation and scoped grouping, weights and pins | `tests/test_options.py`, `tests/test_campaign.py`, `tests/test_partition.py`; hook exceptions have installed-wheel evidence. Dynamic third-party plugin combinations remain untested. |
| Static assignment, file order, cap and plan | `tests/test_partition.py`, `test_hooks_weights_groups_and_pin_via_plan`; scheduling mutation record below. |
| Startup, recollection, stop, cleanup and exit reconciliation | `test_start_methods_smoke`, `test_collection_mismatch_spawn_and_forkserver`, `test_sigterm_reaps_worker_and_removes_work_dir`, `tests/test_p0_correctness.py`; lifecycle mutation outside selected scenarios remains untested. |
| JSONL, report, warning and subtest replay, JUnit and worker coverage | `tests/test_p0_correctness.py`, `tests/test_coverage.py`; malformed and truncated streams and contradictory status are checked. Arbitrary external report plugins remain untested. |
| Network isolation and exceptions | `test_network_policy_and_loopback_exception`, `test_network_address_and_resolver_boundary`, `test_network_guard_installed_wheel_spawn`, `test_marker_allows_network`, `test_serial_network_is_not_guarded`; loopback evidence uses owned sockets and fake transports. |

Disposition by behavior: **equivalent**: scheduling's 11 survivors concern union root choice, pin order, unused round-robin load and unreachable identity lookup defaults; the confirmed infinite-loop timeout is a detected hang, not a passing mutant ([details](docs/deslop-scheduling-tests.md)). Reader final offsets after the sole final read and UTF-8 codec spellings are equivalent in the recorded context; the diagnostic-length survivor was subsequently caught ([details](docs/deslop-event-stream.md)). The option parser's conversion-error survivor is unreachable for its matched grammar. **Accepted risk**: coordinator monitoring's 51 historical surviving identities and unmutated lifecycle decisions remain advisory; ordinary tests cover drain, termination and reconciliation, but this is not exhaustive mutation proof. The historical loopback trial's 71 survivors and two earlier unconfirmed timeouts are unqualified because generated-source activation was not verified; direct and installed-wheel behavior witnesses are the evidence, not those counts. **Untested**: other worker and coordinator decisions, broad plugin combinations and exact whole-change aggregate retention. The retained `make mutants-scheduling` checks its fixed scheduling selection and confirmed timeout; it is not a whole-change selector or hosted CI qualification. The wider retention controls in the inventory were not run and no CI lane is expanded. **Needs environment**: current local evidence is macOS arm64, Python 3.15; Linux forkserver and other supported runtime/platform shapes need their own runs; Windows and other platforms have not been validated here. Historical hosted Linux/macOS results apply only to their recorded revisions. No unsupported-platform pass is implied.

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

### DSLP-7 · P3 · Benchmark representative suites and resource costs

- **Area:** deslop · benchmark coverage
- **Where:** benchmarks/run_benchmarks.py
- **Problem:** The synthetic CPU-trivial suites measure wall time only and do not represent real test workloads, aggregate process memory or CPU, attribution, tail latency, or a paired regression budget.
- **Recommendation:** Add a reproducible representative suite with completed-work and correctness oracles; measure process-tree resources and document profiling and paired host-gated comparisons.
- **Fix with:** bench-pyramid
- **Effort:** M

### DSLP-8 · P3 · Strengthen benchmark preflight and result provenance

- **Area:** deslop · benchmark operability
- **Where:** benchmarks/bench.py
- **Problem:** The entrypoint checks imports and host tool availability but does not verify disk capacity, leftover processes, tool versions or package artifact identity; host diagnostics are not retained in the summary.
- **Recommendation:** Add selected-workload prerequisite and process checks, preserve readiness diagnostics and exact tool and artifact identity, and test failures before workload execution.
- **Fix with:** bench-pyramid
- **Effort:** M

