Prefix: PAR
Next: 14

### PAR-1 · P2 · Abrupt worker SIGTERM preempts cooperative stop and teardown on -x/--maxfail

- **Area:** Concurrency
- **Where:** `src/pytest_parallel/coordinator.py:498-506`, `src/pytest_parallel/worker.py:48-50`
- **Problem:** When `-x` or `--maxfail` triggers, the coordinator invokes `_terminate_live_workers()` on the same loop cycle that `stop_path` is touched. Workers never get an iteration to observe `_should_stop()`, set `session.shouldstop`, or execute fixture and context manager teardowns for in-flight tests before receiving `SIGTERM` / `SIGKILL`. Resources (database connections, open temp files, worker child processes) leak, and `_reconcile_worker` suppresses diagnostics because `global_stopped` is true.
- **Recommendation:** Implement a bounded drain window after creating `stop_path` before escalating to SIGTERM, allowing active workers to finish teardown cooperatively.
- **Fix with:** `lifecycle-concurrency`
- **Effort:** M (days)
- **Design:** [docs/rfc/PAR-1-cooperative-worker-shutdown.md](docs/rfc/PAR-1-cooperative-worker-shutdown.md)

### PAR-2 · P2 · Network guard blocks valid local address resolution and server binding

- **Area:** Security
- **Where:** `src/pytest_parallel/network.py:110-122`, `src/pytest_parallel/network.py:124-142`
- **Problem:** `_guard_resolver` intercepts `socket.getaddrinfo`, `socket.gethostbyname`, etc., and tests `_is_loopback_host(address)`. If `address` is `None` (used by standard libraries and web servers like `http.server` and Starlette with `AI_PASSIVE`), `""` (bind to all local interfaces), or the local machine hostname (`socket.gethostname()`), `_is_loopback_host` returns `False` and raises `PermissionError`. This breaks standard test suites setting up local mock servers or socket listeners without outbound traffic.
- **Recommendation:** Allow `None`, `""`, and local hostnames in `_guard_resolver` when binding or listening locally.
- **Fix with:** `os-boundaries`
- **Effort:** S (hours)
- **Design:** [docs/rfc/PAR-2-network-guard-local-resolution.md](docs/rfc/PAR-2-network-guard-local-resolution.md)

### PAR-10 · P3 · Native and subprocess writes bypass output redirection when -s is used

- **Area:** Operability
- **Where:** `src/pytest_parallel/worker.py:267`, `src/pytest_parallel/worker.py:63-87`
- **Problem:** `run_worker` redirects stdout and stderr using Python `contextlib.redirect_stdout` and `redirect_stderr`. These modify `sys.stdout` and `sys.stderr` in Python, but do not redirect OS file descriptors 1 and 2 (`os.dup2`). Any native extension (C/Cython/Rust) writing directly to fd 1 or child subprocesses inheriting descriptors bypass `output_path` and write directly to the parent terminal, causing scrambled terminal output.
- **Recommendation:** Duplicate and redirect OS file descriptors 1 and 2 to `output_path` in `run_worker` via `os.dup2`.
- **Fix with:** `os-boundaries`
- **Effort:** S (hours)

### PAR-11 · P3 · Cascading diagnostic errors when test finish report is incomplete

- **Area:** Errors
- **Where:** `src/pytest_parallel/coordinator.py:841-853`, `src/pytest_parallel/coordinator.py:960-964`
- **Problem:** In `_handle_test_finish_event`, if `setup` or `teardown` reports are missing, it appends a protocol error and returns early without resetting `state.current_test` or advancing `state.completed`. During reconciliation, `_reconcile_worker` sees `state.current_test is not None` and generates a secondary premature termination diagnostic that obscures the root protocol error.
- **Recommendation:** Clear `state.current_test` and synthesize an explicit failure report on the missing phase so failure diagnostics accurately pinpoint the defect.
- **Fix with:** `error-model`
- **Effort:** S (hours)

### PAR-12 · P3 · Build system requires pin upper bound triggers uv version warning

- **Area:** Build
- **Where:** `pyproject.toml:29`
- **Problem:** `pyproject.toml` pins `requires = ["uv_build>=0.11.25,<0.12"]`. When running `uv build --wheel` with current `uv` (0.13.0+), uv outputs: `warning: build_system.requires = ["uv-build>=0.11.25,<0.12"] does not contain the current uv version 0.13.0`.
- **Recommendation:** Widen the upper bound constraint in `build-system.requires` to permit `uv_build>=0.11.25,<0.14`.
- **Fix with:** `upgrade`
- **Effort:** S (hours)

### PAR-13 · P4 · Dead code main() and __main__ block in worker.py

- **Area:** Dead code
- **Where:** `src/pytest_parallel/worker.py:237-239`, `src/pytest_parallel/worker.py:288-289`
- **Problem:** `worker.py` defines `def main() -> None: sys.exit(pytest.main())` and an `if __name__ == "__main__":` entrypoint. Workers are spawned directly via `multiprocessing.Process(target=run_worker)`. Nothing in the package or test suite executes `worker.py` as a standalone script or calls `main()`.
- **Recommendation:** Delete `main()` and `if __name__ == "__main__":` from `worker.py`.
- **Fix with:** `dead-code-archaeology`
- **Effort:** S (hours)
