# pytest-parallel

A small pytest plugin for static process-level sharding.

```bash
pytest
```

Parallel execution is enabled by default. The default job count is `auto`, using `os.cpu_count()`.

```bash
pytest -j 4
pytest --jobs 4
pytest --serial
```

## Model

`pytest-parallel` keeps the execution model intentionally plain:

- collect once in the coordinator
- group tests by file
- assign files round-robin to fixed workers
- run each worker in a separate `multiprocessing` process
- report results through simple JSONL files

There is no work stealing, no execnet, no remote execution, and no scheduler protocol.

## Platform Policy

- macOS uses `spawn`
- Linux uses `fork`
- other platforms use `spawn`

The fork/spawn point is after collection and before coordinator result polling begins.

On Linux, `pytest-parallel` refuses to fork if any non-main thread is alive at that point. That catches plugins that start background threads during configure, session start, collection, or `pytest_parallel_pre_spawn`.
