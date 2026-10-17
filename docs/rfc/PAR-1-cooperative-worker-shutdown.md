# PAR-1: Cooperative worker shutdown on global test failure

Status: draft

## Summary

When `-x` or `--maxfail` triggers in the coordinator, workers are immediately terminated with `SIGTERM` / `SIGKILL` instead of allowing active tests to complete teardown cooperatively. This RFC defines a bounded drain protocol before forceful termination.

## Motivation

Pytest fixtures frequently manage external state: temporary test databases, open sockets, Docker containers, or child processes. When `-x` triggers after a test failure on Worker 0, Worker 1 may be in the middle of executing a test using such fixtures.

Currently, `coordinator.py:504-506` invokes `_terminate_live_workers()` on the very same loop iteration that `stop_path` is created. Workers receive `SIGTERM` before their next hook or poll can inspect `stop_path`, aborting fixture teardown and leaving resources orphaned.

## Design

1. When `session.shouldfail` or `session.shouldstop` is detected, coordinator touches `stop_path` and records a drain deadline (e.g. `now + drain_timeout`, defaulting to 2.0 seconds).
2. During the drain window, coordinator continues polling `_read_worker_events()`.
3. Workers check `stop_path.exists()` in `pytest_runtest_protocol()` and `pytest_runtest_logfinish()`. Upon detection, they mark `session.shouldstop`, execute teardown for the active test, and emit `session_finish` without starting new tests.
4. If a worker has not exited by the drain deadline, the coordinator proceeds to `_terminate_live_workers()` with `SIGTERM` and `SIGKILL`.

## Alternatives considered

- **Status quo (immediate SIGTERM):** Terminates fastest, but guarantees corrupted teardowns and resource leaks whenever `-x` fires.
- **Unbounded wait:** Wait indefinitely for all workers to finish their current test. A hanging or deadlocked test would prevent pytest from ever terminating.

## Open questions

1. What should the default drain timeout be (e.g., 1.0s, 2.0s, or 5.0s)?
   - *Option A (Recommended):* 2.0 seconds. Long enough for ordinary fixture teardowns, short enough to keep CI fast.
   - *Option B:* Configurable via `--parallel-drain-timeout=SECONDS` with a 2.0s default.
2. Should tests that were interrupted during drain be reported as skipped or left unreported?
   - *Option A (Recommended):* Reconcile interrupted tests as skipped or canceled in test reports.
   - *Option B:* Keep current behavior where `-x` stops test reporting once triggered.

## Decision

Pending owner review.
