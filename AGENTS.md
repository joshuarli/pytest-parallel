# pytest-parallel

A pytest plugin that collects in the parent session and assigns whole test files (or combined affinity groups) to fixed worker processes.

## Development

- `make check` runs Ruff and ty.
- `make test` runs the test suite under pytest-parallel itself.
- `make build` builds the wheel.
- `uv run python benchmarks/run_benchmarks.py` runs the benchmark harness (see [docs/benchmarks.md](docs/benchmarks.md)).

## Invariants

- Fixed workers and static assignment only: no work stealing or dynamic dispatch. All scheduling happens in the controller after collection and before workers run tests. `--parallel-plan=json` writes one JSON document (`version` 1) and a trailing newline to stdout; diagnostics go to stderr. Collection errors and `UsageError` stay non-zero and do not print a plan.
- Assign scheduling units by count-balanced LPT by default (`--parallel-balance=count`): sort units by descending estimated weight with collection-position tie-breaking, assign each to the least-loaded worker with worker-index tie-breaking, then restore relative file collection order within each worker. `--parallel-balance=round-robin` keeps collection-order round-robin. Weights default to item count per file; `pytest_parallel_file_weight` may return a positive finite number (never bool, zero, negative, NaN, or infinite).
- Preserve test order within each file. No global execution order exists across workers.
- Never mutate `item.nodeid` to encode scheduling metadata (`@pytest.mark.parallel_group`, `pytest_parallel_file_groups`). Identify files from item path metadata when available, falling back to the nodeid file part. Merge files transitively through shared group names; deduplicate and validate group names.
- The public customization surface is exactly `pytest_parallel.api.Shard` (frozen) plus the hooks `pytest_parallel_file_groups`, `pytest_parallel_file_weight` (`firstresult=True`), and `pytest_parallel_shard_worker` (all results collected; identical pins allowed, conflicting pins are a `pytest.UsageError`). `pytest_parallel_file_groups` and `pytest_parallel_file_weight` run through the conftest scope of that file. `pytest_parallel_shard_worker` includes a conftest only when the shard contains a file under that conftest's directory; each implementation runs once, and non-conftest plugins apply to every shard. Do not add a scheduler-replacement hook or a configuration DSL. Hook validation failures happen before any worker spawns.
- Cap worker count by the number of schedulable units, not raw item count, and report when an explicit request is capped.
- Register `pytest_runtestloop` with `tryfirst=True`; honor collection errors, `--collect-only`, `--setup-plan` (serial fallback), `shouldfail`, and `shouldstop`; start workers after collection and `pytest_parallel_pre_spawn`, before result polling.
- Use an explicit multiprocessing context: `forkserver` on Linux and `spawn` on macOS and other platforms by default (`--parallel-start-method` overrides). Never set the global start method. `forkserver`/`spawn` give workers a fresh interpreter so parent imports cannot mask collection mismatch. Reject worker startup under explicit `fork` while any non-main thread is alive, and document that `fork` inherits parent state.
- Give every worker a distinct `--basetemp` under one run root, disable the worker cacheprovider, write per-worker log files (CLI `--log-file` or ini `log_file`), and let only the controller write JUnit XML. Sanitize the invocation, ini `addopts`, and `PYTEST_ADDOPTS` together before workers start: strip coordinator flags, cache-selection flags (`--lf`, `--ff`, `--nf`, `--cache-clear`, stepwise), `--junitxml`, `--junit-xml`, `--log-file`, `--basetemp`, `--rootdir`, and `-p cacheprovider` / `-p pytest_cacheprovider`. Parent collection already applied cache selection. The configured basetemp root itself is not a worker basetemp.
- Block socket operations and hostname lookups outside loopback only inside parallel workers, never in serial execution, unless marked with `@pytest.mark.enable_network`. Allow loopback, Unix sockets, local bind addresses (`None`, `""`, unspecified IPs), and the local hostname.
- Reject interactive debugging (`--pdb`, `--trace`), in-memory execution/collection plugins, and xdist distribution (`-n`) in parallel mode with `pytest.UsageError`.
- Run each worker's assigned nodeids through `pytest.main()` using `config.invocation_params`, verify recollected nodeids match the assignment before any assigned test runs, and stream versioned JSONL events (`collection`, `collect_report`, `test_start`, `report` for `setup`/`call`/`teardown`, `test_finish`, `warning`, `session_finish`).
- Replay worker reports and warnings through standard pytest controller hooks (`pytest_runtest_logstart`, `pytest_runtest_logreport`, `pytest_runtest_logfinish`, `pytest_collectreport`, `pytest_warning_recorded`) and reconcile every assigned test's final state so premature exits, signals, or truncated streams never produce false-green runs.
- Stop workers cooperatively on global `-x`/`--maxfail`: touch the stop marker, keep polling during a bounded 5-second drain so in-flight tests finish teardowns and reports, then terminate. Intentionally unexecuted tests are not crash failures. SIGINT/SIGTERM get a short bounded drain, then termination; workers are always reaped and the run directory removed by its owner, the coordinator.
- Ramping delays only the first test per worker, at most once, after worker collection. The heaviest worker starts first.
- Keep pytest as the only runtime dependency.
