# pytest-parallel

`pytest-parallel` runs pytest suites across fixed worker processes using static whole-file sharding. It requires Python 3.13+ and pytest 9+.

## Install

```bash
python -m pip install joshuarli-pytest-parallel
```

Pytest loads the plugin automatically after installation.

## Run tests

```bash
pytest
pytest -j 4
pytest --jobs 4
pytest --parallel-balance=count
pytest --ramp=5s
pytest --parallel-start-method=spawn
pytest --serial
```

Parallel execution is enabled by default:
- `-j` / `--jobs` defaults to `auto`, which queries `os.process_cpu_count()` (respecting CPU affinity, `PYTHON_CPU_COUNT`, and `-X cpu_count`) and falls back to `os.cpu_count()` or `1`.
- Worker count is capped by the number of schedulable file groups and `pytest_parallel_max_workers()` (default `64`).
- `--parallel-balance=round-robin|count` selects how whole files (or combined affinity groups) are assigned to workers. `round-robin` (default) assigns file groups in collection order; `count` uses deterministic largest-processing-time-first (LPT) bin packing by collected test count while preserving relative file order within each worker and test order within each file.
- `--ramp=DURATION` (accepting seconds or `s`, `m`, `h` suffixes) linearly staggers the start of the first test across active workers **after** worker collection completes.
- `--parallel-start-method=auto|fork|spawn|forkserver` overrides the multiprocessing context (`auto` selects `fork` on Linux and `spawn` on macOS and other platforms). When `fork` is selected, worker startup is rejected if any non-main thread is active.
- `--serial` (or `-j 0`) disables parallel execution and uses pytest's standard serial runner.

## File affinity groups

Whole test files are kept together on a single worker by default. To require multiple test files to run on the same worker, mark tests, classes, modules, or `pytest.param` entries with `@pytest.mark.parallel_group`:

```python
import pytest


@pytest.mark.parallel_group("database")
def test_migrations():
    ...
```

Semantics:
- Whole-file sharding is always preserved; files are never split across workers.
- Multiple group names in a single mark (`@pytest.mark.parallel_group("db", "redis")`) or across multiple marks compose transitively: any files connected by at least one shared group name are merged into a single schedulable file unit in collection order.
- Group names are stripped of leading/trailing whitespace and never mutate `item.nodeid`.

## Control network access

`pytest-parallel` blocks socket operations and hostname lookups outside loopback during each test. Loopback addresses and Unix domain sockets remain available. A blocked operation raises `PermissionError`.

This guard intercepts Python's `socket` API. Native extensions and direct system calls can bypass it; use an OS sandbox when you need a hard network boundary.

Mark a test with `@pytest.mark.enable_network` to allow network access for that test:

```python
import pytest


@pytest.mark.enable_network
def test_fetch_remote_data():
    ...
```

## Configure workers

Use these hooks in a pytest plugin or `conftest.py` to cap worker count, prepare state before workers spawn, or customize worker environments:

```python
def pytest_parallel_max_workers() -> int | None:
    return 8


def pytest_parallel_pre_spawn(config, num_workers: int) -> None:
    ...


def pytest_parallel_worker_env(env: dict[str, str], worker_id: int) -> None:
    env["TEST_WORKER_ID"] = str(worker_id)
```

## Execution and reporting contract

- **Collection consistency:** The parent session collects the suite to partition files and then spawns fixed workers that run `pytest.main()` on their assigned node IDs. Each worker verifies that its recollected node IDs exactly match its assignment before running tests; any mismatch fails the run.
- **Reporting and stop semantics:** Workers stream versioned JSONL phase reports (`setup`, `call`, `teardown`), collection reports, and runtime warnings to the parent controller, which replays them through standard pytest hooks (`pytest_runtest_logstart`, `pytest_runtest_logreport`, `pytest_runtest_logfinish`, `pytest_collectreport`, `pytest_warning_recorded`). Global `-x` / `--maxfail` stops all workers cooperatively. Any worker that exits early (`pytest.exit`, signal, `os._exit`, or truncated stream) with unreported assigned tests fails the session with crash diagnostics.
- **Output, terminal width, and interactive modes:** Captured stdout/stderr/log sections are preserved on `TestReport` objects, `-s` (`--capture=no`) test output is forwarded per test, and `COLUMNS`/`LINES` are propagated to workers. Interactive debugging (`--pdb`, `--trace`) and in-memory plugin instances implementing worker execution/collection hooks via `pytest.main(..., plugins=[...])` are rejected in parallel mode with `pytest.UsageError`; use `--serial` or register plugins by module name (`-p`).

See the [project repository](https://github.com/joshuarli/pytest-parallel) and [MIT license](LICENSE).
