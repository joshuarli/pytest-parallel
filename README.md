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
pytest --parallel-balance=count
pytest --ramp=5s
pytest --parallel-start-method=spawn
pytest --serial
```

Parallel execution is enabled by default:
- `-j`, `--jobs`: Worker count (`auto` by default). `auto` uses `os.process_cpu_count()` (falling back to `os.cpu_count()` or `1`), capped by schedulable file units and `pytest_parallel_max_workers()` (default `64`).
- `--parallel-balance=round-robin|count`: Sharding strategy. `round-robin` (default) assigns file units in collection order; `count` uses largest-processing-time-first (LPT) bin packing by test count. Both preserve relative file order per worker and test order within each file.
- `--ramp=DURATION`: Stagger worker first-test start over a duration (e.g. `5s`, `1m`).
- `--parallel-start-method=auto|fork|spawn|forkserver`: Multiprocessing start method (`auto` selects `fork` on Linux, `spawn` elsewhere). Startup under `fork` is rejected if non-main threads are active.
- `--serial` (or `-j 0`): Run tests serially using pytest's standard runner.

## File affinity groups

Whole test files run on a single worker by default. To assign multiple test files to the same worker, mark tests, classes, modules, or `pytest.param` entries with `@pytest.mark.parallel_group`:

```python
import pytest


@pytest.mark.parallel_group("database")
def test_migrations():
    ...
```

Files connected by a shared group name merge transitively into a single schedulable file unit in collection order. Files are never split across workers.

## Control network access

`pytest-parallel` blocks socket operations and hostname lookups outside loopback during each test. Loopback addresses and Unix domain sockets remain available. A blocked operation raises `PermissionError`.

The guard intercepts Python's `socket` API. Native extensions and direct system calls bypass it; use an OS sandbox when you need a hard network boundary.

Mark a test with `@pytest.mark.enable_network` to allow network access for that test:

```python
import pytest


@pytest.mark.enable_network
def test_fetch_remote_data():
    ...
```

## Configure workers

Define these hooks in a pytest plugin or `conftest.py` to cap worker count, prepare state before workers spawn, or customize worker environments:

```python
def pytest_parallel_max_workers() -> int | None:
    return 8


def pytest_parallel_pre_spawn(config, num_workers: int) -> None:
    ...


def pytest_parallel_worker_env(env: dict[str, str], worker_id: int) -> None:
    env["TEST_WORKER_ID"] = str(worker_id)
```

## Compatibility

- Global `-x` and `--maxfail` stop all workers cooperatively.
- Uncaptured output (`-s`, `--capture=no`) is forwarded per test; captured stdout, stderr, and logs are preserved on test reports.
- Interactive debugging (`--pdb`, `--trace`) requires `--serial`.
- In-memory execution or collection plugins passed to `pytest.main(plugins=[...])` are rejected in parallel mode; use `--serial` or register plugins by module name (`-p`).

See the [project repository](https://github.com/joshuarli/pytest-parallel) and [MIT license](LICENSE).
