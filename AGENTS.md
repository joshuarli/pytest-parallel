# pytest-parallel

`pytest-parallel` is a small pytest plugin for static process-level sharding.

It intentionally does less than `pytest-xdist`:

- No execnet.
- No work stealing.
- No persistent worker protocol.
- No dynamic scheduler.
- No remote execution.

The coordinator collects tests once, assigns whole test files to fixed worker buckets, and starts worker processes with `multiprocessing`. Each worker calls `pytest.main()` with only its assigned nodeids and reports test outcomes back through a JSONL file.


## Usage

Parallel execution is enabled by default:

```bash
pytest
```

The default worker count is `auto`, which uses `os.cpu_count()`.

To choose a worker count:

```bash
pytest -j 4
pytest --jobs 4
```

To disable the plugin and use pytest's standard serial runner:

```bash
pytest --serial
```

## Scheduling

Sharding is deterministic and file-based:

1. Pytest performs normal collection in the coordinator process.
2. Items are grouped by `nodeid.split("::")[0]`.
3. Files are assigned round-robin to worker buckets.
4. Tests inside a file keep their original collection order.

This favors simplicity and predictable isolation over perfect balancing.

## Process Start

Worker processes use an explicit `multiprocessing` context:

- macOS uses `spawn`.
- Linux uses `fork`.
- Other platforms use `spawn`.

Do not call `multiprocessing.set_start_method()` globally. Choose the context in the coordinator and create workers from that context.

The fork/spawn point is deliberately late in pytest's coordinator process:

1. Pytest configures plugins and completes collection.
2. The coordinator partitions collected nodeids.
3. `pytest_parallel_pre_spawn` runs once for project-level setup.
4. Workers are started immediately after that, before the coordinator starts result polling.

On Linux, this means `fork` happens after collection but before any pytest test item is executed by the coordinator. On macOS, `spawn` avoids inheriting unsafe interpreter state from the pytest coordinator process.

`pytest_runtestloop` is registered with `tryfirst=True`, so pytest-parallel reaches the fork/spawn decision before ordinary runtest-loop plugins execute tests. This cannot prevent other plugins from starting threads earlier during configure, session start, collection, or `pytest_parallel_pre_spawn`.

On Linux, pytest-parallel checks for active non-main threads immediately before forking and raises `pytest.UsageError` if any are present. Project hooks should not leave background threads running from `pytest_parallel_pre_spawn`; forking a process with active threads is not safe.

## Hooks

Projects can customize worker limits and environments with pytest hooks:

```python
def pytest_parallel_max_workers() -> int | None:
    return 8


def pytest_parallel_pre_spawn(config, num_workers: int) -> None:
    ...


def pytest_parallel_worker_env(env: dict[str, str], worker_id: int) -> None:
    env["TEST_WORKER_ID"] = str(worker_id)
```

## Design Constraints

- Keep this package standalone.
- Keep dependencies minimal; pytest should remain the only runtime dependency.
- Start workers through `multiprocessing` contexts, not by executing package files by path.
- Avoid adding scheduler features unless they preserve the static, easy-to-debug model.
- Prefer pytest primitives and simple files over custom IPC.
