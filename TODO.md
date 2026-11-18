Prefix: PAR
Next: 15
### PAR-14 · P2 · Replay native pytest subtest reports in parallel workers

- **Area:** worker reports
- **Where:** src/pytest_parallel/coordinator.py and tests/test_p0_correctness.py
- **Problem:** Released 0.4.0 and a wheel built from c260153 reject repeated SubtestReport call phases on pytest 9.2.0. Toolbox's four native fio tests pass in serial but parallel execution reports duplicate calls and a worker error.
- **Recommendation:** Replay typed subtest events in arrival order without filling the regular call slot. Preserve ordinary phase validation and compare passing and failing subtests, then rerun Toolbox against the repaired wheel.
- **Fix with:** test-audit
- **Effort:** M
