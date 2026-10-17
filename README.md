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
pytest --parallel-balance=round-robin
pytest --ramp=5s
pytest --parallel-start-method=spawn
pytest --parallel-plan
pytest --parallel-plan=json
pytest --serial
```

Parallel execution is enabled by default:

- `-j`, `--jobs`: Worker count (`auto` by default). `auto` uses `os.process_cpu_count()` (falling back to `os.cpu_count()` or `1`), capped by the number of schedulable units and `pytest_parallel_max_workers()` (default `64`). An explicit request above the cap is reported, not silently reduced.
- `--parallel-balance=count|round-robin`: Sharding strategy. `count` (default) uses largest-processing-time-first (LPT) bin packing by estimated weight (test count unless customized). `round-robin` assigns units in collection order. Both preserve relative file order per worker and test order within each file. There is no global execution-order guarantee across workers.
- `--ramp=DURATION`: Stagger worker first-test start over a duration (e.g. `5s`, `1m`). The heaviest worker starts first; each worker waits at most once, after its own collection, and a stop request interrupts the wait. `--parallel-plan` never waits.
- `--parallel-start-method=auto|fork|spawn|forkserver`: Multiprocessing start method. `auto` selects `forkserver` on Linux and `spawn` elsewhere. `forkserver`/`spawn` start workers from a fresh interpreter, so parent-side imported test modules cannot mask worker collection differences. Explicit `fork` remains available on Linux, but it inherits parent process state (including already-imported modules and threads) and is rejected while non-main threads are alive; treat it as an opt-in for suites that understand those semantics.
- `--parallel-plan[=text|json]`: Print the resolved sharding plan (balance, workers, files, weights, groups, pinned vs automatic units, imbalance) and exit successfully without spawning workers or running tests. Collection errors remain errors. It cannot be combined with `--serial`, `-j 0`, or `--collect-only`.
- `--serial` (or `-j 0`): Run tests serially using pytest's standard runner.

Workers receive distinct per-worker `--basetemp` directories under one run-specific root (the explicitly configured `--basetemp`, with `worker-N` subdirectories, or a temporary run root when none is configured). The configured root itself is never a worker basetemp. Options inherited from ini `addopts` (pytest.ini, tox.ini, setup.cfg, or `pyproject.toml`) and `PYTEST_ADDOPTS` are placed on the worker command once, after coordinator flags, cache-selection flags, JUnit XML, `--log-file`, `--basetemp`, `--rootdir`, and cacheprovider plugin loads are removed. Worker caches are disabled (`-p no:cacheprovider`) so concurrent workers cannot corrupt `.pytest_cache` or change `--lf`-style selection, which the parent collection already applied. A configured log file, from `--log-file` or the ini `log_file` key, is written as one file per worker (`<name>.worker-N<ext>`). JUnit XML is produced once by the controller from replayed reports.

## Inspect the plan

```bash
pytest -j 8 --parallel-plan
pytest -j 8 --parallel-plan=json
pytest --parallel-balance=round-robin --parallel-plan
```

JSON output is a single deterministic object printed before pytest's summary. Extract it from the first `{` when automating.

## File affinity groups

Whole test files run on a single worker by default. To assign multiple test files to the same worker, mark tests, classes, modules, or `pytest.param` entries with `@pytest.mark.parallel_group`:

```python
import pytest


@pytest.mark.parallel_group("database")
def test_migrations():
    ...
```

Files connected by a shared group name merge transitively into a single schedulable unit in collection order. Files are never split across workers. Affinity means co-location on one worker, not exclusion of other tests from that worker. Grouping never mutates node IDs, and parametrized IDs containing `::`, `@`, or Unicode are preserved.

Programmatic grouping from `conftest.py` (all implementations contribute, additively with markers):

```python
from pathlib import Path

import pytest


def pytest_parallel_file_groups(path: Path, items: list[pytest.Item]) -> list[str] | None:
    if "database" in path.parts:
        return ["database"]
    return None
```

`path` is relative to the rootdir when the file lives under it. Return `None` for no group. Empty or non-string names raise `pytest.UsageError`.

## Customize scheduling

All customization is ordinary pytest hook code in `conftest.py` or a plugin. No scheduler subclassing or configuration DSL is needed.

Custom estimated weights (first non-`None` result wins; use `tryfirst`/`trylast` to control priority among plugins). Weights are positive finite numbers, summed per affinity unit, and default to the file's test count:

```python
from pathlib import Path

import pytest


def pytest_parallel_file_weight(path: Path, items: list[pytest.Item]) -> float | None:
    if "browser" in path.parts:
        return len(items) * 10.0
    if "integration" in path.parts:
        return 50.0
    return None
```

Pin a whole unit to a worker. `Shard` is the frozen public view from `pytest_parallel.api` (`files`, `nodeids`, `weight`, `groups`, `ordinal`; paths follow the same rootdir-relative rule). All implementations are consulted: identical pins are fine, conflicting pins raise `pytest.UsageError`, and unpinned units are balanced automatically:

```python
from pytest_parallel.api import Shard


def pytest_parallel_shard_worker(shard: Shard, num_workers: int) -> int | None:
    if "gpu" in shard.groups:
        return 0
    return None
```

A complete example combining all three hooks lives in `conftest.py` at your project root; each hook is independent and optional.

Worker lifecycle hooks remain separate from scheduling:

```python
def pytest_parallel_max_workers() -> int | None:
    return 8


def pytest_parallel_pre_spawn(config, num_workers: int) -> None:
    ...


def pytest_parallel_worker_env(env: dict[str, str], worker_id: int) -> None:
    env["TEST_WORKER_ID"] = str(worker_id)
```

## Configure in pytest.ini / pyproject.toml

Use pytest's existing `addopts`; no new configuration language is introduced:

```ini
[pytest]
addopts = -j 8 --parallel-balance=count --ramp=2s
```

```toml
[tool.pytest.ini_options]
addopts = "-j 8 --parallel-balance=round-robin"
```

## Control network access

In parallel workers, `pytest-parallel` blocks socket operations and hostname lookups outside loopback during each test. Loopback, Unix sockets, binding to unspecified local addresses (`0.0.0.0`/`::` for `bind`), `getaddrinfo(None/"", ...)` for local listeners, and resolving the local hostname remain available. A blocked operation raises `PermissionError`. Ordinary serial pytest (`--serial`, `-j 0`) is not guarded.

The guard intercepts Python's `socket` API. Native extensions and direct system calls bypass it; use an OS sandbox when you need a hard network boundary.

Mark a test with `@pytest.mark.enable_network` to allow network access for that test:

```python
import pytest


@pytest.mark.enable_network
def test_fetch_remote_data():
    ...
```

## Compatibility

- Supported and CI-tested: Linux and macOS, Python 3.13 and 3.14, pytest 9. Windows is not currently tested or supported.
- Global `-x` and `--maxfail` stop workers cooperatively: no new tests start, in-flight tests finish their fixture teardowns and reports (bounded by a 5s drain, then workers are terminated), and intentionally unexecuted tests are not reported as crashes.
- Uncaptured output (`-s`, `--capture=no`) is forwarded per test; captured stdout, stderr, and logs are preserved on test reports.
- Interactive debugging (`--pdb`, `--trace`) requires `--serial`. `--setup-plan` runs through the standard serial runner.
- In-memory execution or collection plugins passed to `pytest.main(plugins=[...])` are rejected in parallel mode; use `--serial` or register plugins by module name (`-p`).
- pytest-xdist may be installed, but `-n`/`--numprocesses` cannot be combined with pytest-parallel distribution; the combination raises `pytest.UsageError` (pass `--serial` to let xdist own the run).
- Third-party plugin output paths other than the core paths handled above (basetemp, log file, JUnit XML, cache) are forwarded unchanged; plugins that write shared files concurrently remain responsible for their own isolation.

See the [project repository](https://github.com/joshuarli/pytest-parallel) and [MIT license](LICENSE).
