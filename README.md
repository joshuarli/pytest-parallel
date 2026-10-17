# pytest-parallel

`pytest-parallel` runs pytest tests in fixed worker processes. It requires Python 3.13 or newer.

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
pytest --serial
```

Parallel execution is enabled by default. The default request, `auto`, uses `os.cpu_count()` or one worker if unavailable. The worker count is capped by the number of collected tests. The default cap is 64 workers. Use `-j` or `--jobs` to set the requested count. Use `--serial` to run pytest's standard serial runner.

The plugin prints worker progress and a pytest test summary. Add `-v` to show each worker ID, test node ID, outcome, and duration.

## Control network access

Pytest-parallel blocks socket operations and hostname lookups outside loopback during each test. Loopback addresses and Unix domain sockets remain available. A blocked operation raises `PermissionError`.

This guard intercepts Python's socket API. Native extensions and direct system calls can bypass it. Use an OS sandbox when you need a hard network boundary.

Mark a test with `@pytest.mark.enable_network` to allow network access for that test:

```python
import pytest


@pytest.mark.enable_network
def test_fetch_remote_data():
    ...
```

## Configure workers

Use these hooks in a pytest plugin or `conftest.py` to set a worker cap, prepare the project before workers start, or change each worker's environment:

```python
def pytest_parallel_max_workers() -> int | None:
    return 8


def pytest_parallel_pre_spawn(config, num_workers: int) -> None:
    ...


def pytest_parallel_worker_env(env: dict[str, str], worker_id: int) -> None:
    env["TEST_WORKER_ID"] = str(worker_id)
```

See the [project repository](https://github.com/joshuarli/pytest-parallel) for help and the [MIT license](LICENSE).
