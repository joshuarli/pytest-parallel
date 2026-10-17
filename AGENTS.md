# pytest-parallel

A pytest plugin that collects once and assigns whole test files to fixed worker processes.

## Development

- `make check` runs Ruff and ty.
- `make test` runs the test suite serially and in parallel.
- `make build` builds the wheel.

## Invariants

- Assign files round-robin in collection order and preserve test order within each file.
- Register `pytest_runtestloop` with `tryfirst=True`; start workers after collection and `pytest_parallel_pre_spawn`, before result polling.
- Use an explicit multiprocessing context: `fork` on Linux and `spawn` on macOS and other platforms. Do not set the global start method.
- On Linux, reject worker startup while any non-main thread is alive.
- Run each worker's assigned nodeids through `pytest.main()` and report outcomes through JSONL files.
- Keep pytest as the only runtime dependency.
