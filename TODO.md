Prefix: PAR
Next: 18
### PAR-17 · P2 · Unittest subtests are reported as worker setup errors

- **Area:** result reporting
- **Where:** pytest_parallel worker report forwarding
- **Problem:** A unittest.TestCase test that uses self.subTest and passes is reported as `ERROR at setup` with `worker N failure (exit code 0)` and `duplicate 'call' report for '<nodeid>'`, while the worker output shows the test passed. Reproduced with joshuarli-pytest-parallel 0.4.0 (laputa-systems/stuff .venv, Python 3.15.2, macOS arm64): `uv run --group dev pytest -q deploy/openorange/tests/test_receipt.py` on stuff 501db113 gives `2 passed, 1 error, 3 subtests passed`; `python -m unittest test_receipt` passes. Every subTest-using rollout test in stuff fails the suite this way, so a green suite cannot be told from a red one without rerunning under unittest.
- **Recommendation:** Accept one call report per subtest (the subtests plugin emits several per item) and aggregate them into the item outcome; add a regression test with a passing and a failing unittest subTest that asserts the exact pass, fail and error counts.
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

