# pytest-parallel

A pytest plugin that collects in the parent session and assigns whole test files (or combined affinity groups) to fixed worker processes.

## Development

- `make check` runs Ruff and ty.
- `make test` runs the test suite serially and in parallel.
- `make build` builds the wheel.

## Invariants

- Assign file groups round-robin in collection order by default (or LPT by item count with `--parallel-balance=count`), preserving relative file order within each worker and test order within each file.
- Never mutate `item.nodeid` to encode scheduling metadata (`@pytest.mark.parallel_group`).
- Cap worker count by the number of schedulable file groups, not raw item count.
- Register `pytest_runtestloop` with `tryfirst=True`; honor collection errors, `--collect-only`, `shouldfail`, and `shouldstop`; start workers after collection and `pytest_parallel_pre_spawn`, before result polling.
- Use an explicit multiprocessing context: `fork` on Linux and `spawn` on macOS and other platforms by default (`--parallel-start-method` overrides). Never set the global start method.
- Reject worker startup under `fork` while any non-main thread is alive.
- Block socket operations and hostname lookups outside loopback during each test unless marked with `@pytest.mark.enable_network`.
- Reject interactive debugging (`--pdb`, `--trace`) and in-memory execution/collection plugins in parallel mode with `pytest.UsageError`.
- Run each worker's assigned nodeids through `pytest.main()` using `config.invocation_params`, verify recollected nodeids match the assignment, and stream versioned JSONL events (`collection`, `collect_report`, `test_start`, `report` for `setup`/`call`/`teardown`, `test_finish`, `warning`, `session_finish`).
- Replay worker reports and warnings through standard pytest controller hooks (`pytest_runtest_logstart`, `pytest_runtest_logreport`, `pytest_runtest_logfinish`, `pytest_collectreport`, `pytest_warning_recorded`) and reconcile every assigned test's final state so premature exits, signals, or truncated streams never produce false-green runs.
- Stop all workers cooperatively on global `-x` or `--maxfail`.
- Keep pytest as the only runtime dependency.

## RFCs

- [docs/rfc/PAR-1-cooperative-worker-shutdown.md](docs/rfc/PAR-1-cooperative-worker-shutdown.md)
- [docs/rfc/PAR-2-network-guard-local-resolution.md](docs/rfc/PAR-2-network-guard-local-resolution.md)
