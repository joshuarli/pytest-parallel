Prefix: PAR
Next: 22
### PAR-17 · P2 · Passing tests are reported as worker errors

- **Area:** result reporting
- **Where:** pytest_parallel worker report forwarding
- **Problem:** Passing tests are reported as `ERROR at setup` with `worker N failure (exit code 0)`, while the worker output shows them passing; unittest subTest tests also log `duplicate 'call' report for '<nodeid>'`. Reproduced with joshuarli-pytest-parallel 0.4.0 (laputa-systems/stuff .venv, Python 3.15.2, macOS arm64): `uv run --group dev pytest -q deploy/openorange/tests` on stuff b632aba9 reported 139 passed, 2 skipped and 13 errors with no traceback or assertion, about one error per worker, and the errors included plain pytest functions such as test_lease.py::test_observe_cli_reads_identity_without_a_mutation_bound as well as subTest tests; `pytest -p no:parallel` on the same tree gives 163 passed, 2 skipped. A green suite cannot be told from a red one without rerunning serially.
- **Recommendation:** Reproduce with a worker count below the test count and with one passing unittest subTest; make each worker's final report and subtest call reports aggregate into one outcome per item; add a regression test asserting the exact pass, fail and error counts for a passing plain test, a passing subTest test and a failing test.
- **Fix with:** root-cause
- **Effort:** S

### PAR-15 · P3 · Benchmark representative suites and resource costs

- **Area:** benchmark coverage
- **Where:** benchmarks/run_benchmarks.py
- **Problem:** The synthetic CPU-trivial suites measure wall time only and do not represent real test workloads, aggregate process memory or CPU, attribution, tail latency, or a paired regression budget.
- **Recommendation:** Add a reproducible representative suite with completed-work and correctness oracles; measure process-tree resources and document profiling and paired host-gated comparisons.
- **Fix with:** bench-pyramid
- **Effort:** M

### PAR-16 · P3 · Strengthen benchmark preflight and result provenance

- **Area:** benchmark operability
- **Where:** benchmarks/bench.py
- **Problem:** The entrypoint checks imports and host tool availability but does not verify disk capacity, leftover processes, tool versions or package artifact identity; host diagnostics are not retained in the summary.
- **Recommendation:** Add selected-workload prerequisite and process checks, preserve readiness diagnostics and exact tool and artifact identity, and test failures before workload execution.
- **Fix with:** bench-pyramid
- **Effort:** M

### PAR-18 · P3 · Qualify worker stop and lifecycle coverage

- **Area:** worker lifecycle
- **Where:** src/pytest_parallel/coordinator.py:_monitor, _trigger_global_stop, _terminate_live_workers; tests/test_p0_correctness.py
- **Problem:** The stop and drain tests leave monitor mutations and wider worker lifecycle decisions unclassified, so important shutdown regressions may escape detection.
- **Recommendation:** Review surviving mutations and exercise reachable stop, drain, supervision and cleanup behavior; classify equivalent cases and cover observable gaps.
- **Fix with:** test-audit
- **Effort:** M

### PAR-19 · P3 · Qualify mutation coverage for changed behavior

- **Area:** test quality
- **Where:** scripts/mutants_scheduling.py; src/pytest_parallel/coordinator.py; src/pytest_parallel/worker.py; src/pytest_parallel/network.py
- **Problem:** Mutation checks cover selected scheduling decisions only; the whole-change selector remains an incomplete draft and network mutation observations lacked instrumented-source activation and timeout confirmation.
- **Recommendation:** Develop and qualify a bounded serial mutation workflow covering changed and protected regions, verify instrumented-source activation, classify surviving and timed-out cases, and exercise deletion, uncovered decision, mixed-change and documentation-only controls.
- **Fix with:** test-audit
- **Effort:** L

### PAR-20 · P4 · Qualify worker coverage on other platforms

- **Area:** coverage
- **Where:** tests/test_coverage.py; Makefile:coverage
- **Problem:** Worker coverage data checks were qualified on macOS; Linux and other plugin combinations remain unverified, and the guard depends on coverage data filename layout.
- **Recommendation:** Exercise the installed-wheel worker and branch oracle and raw data checks on Linux and relevant supported plugin combinations; document any limitations.
- **Fix with:** test-audit
- **Effort:** M

### PAR-21 · P4 · Review typing escapes in correctness tests

- **Area:** test typing
- **Where:** tests/test_p0_correctness.py
- **Problem:** The soundness of typing escapes added in correctness tests has not been reviewed individually, so unsafe assumptions may be hidden from the type checker.
- **Recommendation:** Audit each relevant cast, Any annotation and suppression against its runtime contract and narrow or justify it where needed.
- **Fix with:** typing-audit
- **Effort:** S

