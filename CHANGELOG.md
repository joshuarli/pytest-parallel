# Changelog

## Unreleased

### Correctness and reliability (P0)
- Reconcile per-worker test accounting (`assigned`, `started`, `completed`, `failed`, `unreported`, `session_finish`) so premature worker exits (`os._exit(0)`, `os._exit(1)`, `SIGKILL`, `SIGSEGV`, `pytest.exit`) and truncated/malformed JSONL streams never produce false-success runs.
- Emit and replay full phase-aware `TestReport` objects (`setup`, `call`, `teardown`) via `pytest_report_to_serializable` / `pytest_report_from_serializable`, preserving `wasxfail`, `xfailed`, `xpassed`, strict `xpass`, setup skips, setup/teardown errors, captured stdout/stderr/log sections, and `--durations`.
- Replay reports, collection failures, and runtime warnings through standard controller hooks (`pytest_runtest_logstart`, `pytest_runtest_logreport`, `pytest_runtest_logfinish`, `pytest_collectreport`, `pytest_warning_recorded`) for JUnit XML and plugin compatibility without mutating private `terminalreporter.stats`.
- Honor parent collection failures, `--continue-on-collection-errors`, `--collect-only`, `session.shouldfail`, and `session.shouldstop` without overwriting `session.testsfailed`.
- Reconstruct worker arguments from `config.invocation_params` rather than `sys.argv`, verify worker recollection matches assigned node IDs, and reject unsupported in-memory execution/collection plugins and interactive modes (`--pdb`, `--trace`) with `pytest.UsageError`.
- Enforce global `-x` / `--maxfail` cooperatively across workers and clean up already-started workers if a subsequent worker fails to spawn.

### Scheduling, execution, and compatibility (P1)
- Prefer `os.process_cpu_count()` for `--jobs=auto` and cap worker count by the number of schedulable file groups.
- Add `--ramp=DURATION` (`s`, `m`, `h`) to stagger first-test execution across active workers after collection.
- Add `--parallel-balance=round-robin|count` for optional largest-processing-time-first (LPT) static file sharding by test count.
- Add `@pytest.mark.parallel_group(name, ...)` for cross-file worker affinity without mutating `item.nodeid`.
- Add `--parallel-start-method=auto|fork|spawn|forkserver` and forward uncaptured `-s` output and `COLUMNS`/`LINES` terminal dimensions.
