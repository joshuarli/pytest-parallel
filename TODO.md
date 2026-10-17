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
