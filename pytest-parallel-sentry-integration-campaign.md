# Campaign: Sentry within-job runner

status: ready

Replace Sentry's within-job xdist execution with pytest-parallel. Keep Sentry's cross-job selection and sharding. Performance is not a goal and is not a gate.

Deliverables:

1. Native run and worker identity, visible before application import, with serial runs left serial.
2. A manifest collection mode so a worker collects from the original directory root and runs only the parent's ordered selection.
3. Attempt-aware rerun accounting, with JSON and JUnit written only by the controller.
4. Sentry resource slots (Postgres, Redis, Kafka, Snuba, Relay) derived from that identity, with xdist left as the default runner.
5. A local two-worker service-backed slice whose outcomes match serial, or a parked blocker that names the missing service.

Checked out at preflight: pytest-parallel `8ddd4ce26556f061092a147af5b250747b7499d0` (clean except this file), Sentry `624fb343cb8e0f9c1b852e6860c426fb7804b739` (clean). Re-read both trees at start; do not reimplement work that has landed since.

## Charter

Decide, log the call in the decision log, and keep going. This doc does not grant permission. The launch prompt grants local commits on the two campaign branches. Anything outside the execution boundary parks the item.

Hard stops, each of which parks the item and continues everything else: an action outside the execution boundary, a boundary in Decisions or Non-goals, or a check that cannot be run because the tool or service is missing after the one setup attempt named on the item. Pushing, publishing, and opening PRs are always forbidden.

Fix on the way, in its own commit, only what is egregious: a focused pytest-parallel command over 60 seconds, a Sentry file whose wall time is more than 3× the serial baseline of that same file and command, or a test that is red on the recorded baseline and blocks the item. Record anything else and leave it.

Parity before optimization. This campaign has no optimization phase. Do not add a speedup, a benchmark comparison, a startup target, a timing ratio, an RSS target, or duration-based scheduling. `--fail-slow` stays in Sentry's committed CI addopts and is not a local gate.

No provenance files, checksums, or pinned hashes. Record the SHAs once in the campaign log.

Run as wide as ownership and the machine allow. This host has 10 CPUs and 32 GB. Budget 6 GB per lane and at most 3 lanes. The floor is one lane until PP-1 has merged, then two whenever both workstreams have ready work. After the first Sentry service run, read its peak RSS; if a two-worker run exceeds 12 GB, do not run a service lane beside another lane. Replace or resume a stopped lane in the same turn. Overlap a plugin merge and the editable reinstall with the next Sentry item. Run plugin tests and Sentry file tests at the same time only on disjoint checkouts. Never run two collects or two service sessions against one tree or one devservices stack.

Worktrees: `/Users/josh/dev/pytest-parallel/.work/wt/<lane>` on branch `campaign/sentry-integration`, and `/Users/josh/dev/sentry/.work/wt/<lane>` on branch `campaign/pytest-parallel`. Both `.git/info/exclude` files already contain `.work/`. Scratch and artifacts go under that repo's `.work/tmp` and `.work/artifacts`. Point `TMPDIR` at `.work/tmp`. Never use `/tmp` or `$TMPDIR` for campaign state. Follow orchestrate's worktree lifecycle. During winddown, retain a worktree only when it is clean, named in the handoff, and allowed by the closeout guard.

Every commit is a Conventional Commit. Scope is the workstream area (`identity`, `manifest`, `report`, `sentry-runner`, `sentry-resources`). The item ID goes in the body, never the subject. Code comments never cite this doc.

A failing item gets at most three hypotheses. Each hypothesis names the observation that would refute it before the edit. After the third miss, park a one-line finding and continue with the next item that does not depend on it. Do not retry a red suite to go green, and do not stretch a timeout to hide a lifecycle bug.

Lanes use the narrowest check that covers the edit. They do not run `make test`, a Sentry directory, or `devenv sync`. The integrator runs the phase check after each merge, from a scratch worktree, then briefs the next ready item.

## Decisions

### Owner-decided

None. The product choices in the draft are closed below. Overrule any of them before launch; the executor will not ask.

### Prescribed

- **CI stays on xdist.** `SENTRY_TEST_RUNNER` defaults to `xdist`. Do not edit `uv.lock`, do not add a git or path dependency, and do not change `.github/workflows/backend.yml` or `acceptance.yml`. The selectable path lives in `pytest-selected.py` and the Make targets. Switching the default or pinning a published wheel is a later owner action. Reverse this only if the owner launches with an explicit pin to commit.
- **Identity types.** Add frozen `RunInfo` (`run_id: str`, `role: Literal["controller","worker","serial"]`, `collection_seed: int | None`) and `WorkerInfo` (`index: int`, `count: int`) to `pytest_parallel.api`, plus `current_run()` and `current_worker()`. `current_worker()` is `None` for controller and serial. `index` is the scheduler bucket index (empty buckets are not spawned, and the index is not compressed). `count` is the pool size `num_workers`, including unspawned empty slots. Importing `pytest_parallel.api` does not create a run, set an environment variable, or import Django. The controller is never worker 0.
- **When identity exists.** Set the controller run id in `pytest_load_initial_conftests`, before conftest import. `pytest_parallel_pre_spawn` is too late for Sentry's cell name. Workers receive the same run id through the environment the worker entry sets before `pytest.main`. No new hook unless that path cannot satisfy deliverable 1; then add one hook, not a family, and log why.
- **Environment.** Propagation is the variables below, setdefault on the controller, copied into the worker, never deleted from a user-supplied run id. A controller process that sees `_PYTEST_PARALLEL_WORKER` without the worker-entry sentinel raises `pytest.UsageError`. Plan JSON stays version 1 and does not contain the run id or the seed. Serial does not invent a worker index.
- **Collection mode.** `--parallel-collection=nodeid|manifest`, default `nodeid` (today's behavior: absolute nodeids on the worker command line, exact list equality). `manifest` invokes the original collection arguments (for Sentry, `tests`), passes a version-1 manifest of ordered files and ordered nodeids with a duplicate occurrence index, lets pytest collect, and runs exactly the assigned identities in parent order. Unselected items collected from an assigned file are skipped and are not identity drift. A missing required id, an unexplained duplicate, a changed id, or a bad manifest fails before any assigned test. Count equality is not validation.
- **Network.** `--parallel-network=loopback|inherit`, default `loopback` (current guard). Sentry's parallel path passes `inherit` because Redis Cluster is configured at `0.0.0.0` (`sentry.py` redis clusters) and other services are not loopback. Do not call `0.0.0.0` loopback, and do not mark the suite `enable_network`. The guard is not an OS sandbox; say so in the README.
- **Drain.** `--parallel-drain` defaults to 5 seconds (`_STOP_DRAIN_TIMEOUT` in `coordinator.py`). Sentry's parallel path passes `60s`. SIGINT/SIGTERM keep the existing short bound. Drain is cooperative completion, then termination. A crash with no stop marker stays a crash. Intentional unexecuted tests are not failures.
- **Reruns.** Installed Sentry plugin is pytest-rerunfailures 16.3. Outcome `rerun` is non-terminal. An item is complete once, when that plugin stops retrying it. `logfinish` is not completion. Do not write a second retry engine. Intermediate reruns stay in the report stream. JSONL gains `"version": 1` and an integer `attempt` on run events. Unknown versions and duplicate or out-of-order events inside one attempt fail the run. Evidence already received is kept if the worker dies.
- **JSON and JUnit.** pytest-json-report 1.5.0 selects `JSONReportWorker` vs `JSONReport` by `config.workerinput` (`pytest_jsonreport/plugin.py` `pytest_configure`). Do not set `workerinput`. Ship `pytest_parallel.ext.json_report`, loaded only when `--json-report` is set and the package imports. Workers register `JSONReportWorker`. The controller registers `JSONReport` and is the only process that writes the JSON file and JUnit XML. Carry `report._json_report_extra` through the existing report serialization hooks. Sentry's `PytestRerunJSONReporter` stays registered only against the controller `JSONReport`, which is how `json_report_reruns.py` already filters.
- **Django databases.** pytest-django 4.12.0 suffixes `TEST.NAME` from `config.workerinput["workerid"]` (`django_db_modify_db_settings_xdist_suffix`). Do not set `workerinput` and do not copy pytest-django's database lifecycle. In Sentry, override `django_db_modify_db_settings_xdist_suffix` only under `SENTRY_TEST_RUNNER=parallel`, with suffix `gw{index}`, for every alias. Serial and xdist keep their current suffix behavior, with no double suffix. Do not rewrite production `NAME`.
- **Resource slot label.** Sentry's `testutils.pytest.workers` owns slot math. Slot `n` uses Redis DB `9+n`, cluster prefix `test-gw{n}:`, Kafka topic and consumer-group suffix `-gw{n}`, Snuba `http://127.0.0.1:{1230+n}` when per-worker Snuba is on, and snowflake id `n+1`. Serial and the controller use Redis DB 9, prefix `test-main:`, unsuffixed topics, and snowflake 0. `xdist.py` delegates to this module when the parallel role is active and keeps today's `PYTEST_XDIST_*` behavior otherwise. Native runs do not read `PYTEST_XDIST_WORKER`. Cap the pool with `pytest_parallel_max_workers` at 7, and also at the number of provisioned Snuba slots when `XDIST_PER_WORKER_SNUBA` is set. Read `SENTRY_TEST_WORKERS`, else `XDIST_WORKERS`, else `2`.
- **Collection seed and outer shard.** The parent remains the only process that applies `SELECTED_TESTS_FILE`, `TEST_GROUP` hashing, and `SENTRY_SHUFFLE_TESTS`. If the parent generates a shuffle seed, it exports that seed on workers and workers do not shuffle or rehash. A shared seed alone is not the order guarantee; the manifest is. Do not change `plan_shards`, shard count, or the large-file split. An empty explicit selection stays empty. `pytest-selected.py` still maps a genuine no-tests shard to exit 0. A broken manifest is not that case.
- **Django settings on workers.** `pytest_parallel_worker_env` in Sentry removes `DJANGO_SETTINGS_MODULE` and any `PYTEST_XDIST_*` from the worker env. The worker's existing `pytest_configure` sets the settings module. Do not pop the controller's environment.
- **Exclusive services.** One `fcntl.flock` on `.work/sentry-service.lock` in the Sentry controller, acquired before the first `flushdb` or database create, non-blocking. If it is held, raise immediately. Do not provision a second stack. Never run xdist and pytest-parallel together.
- **Cluster flush.** `pytest_runtest_teardown` may `flushdb` the worker's own Redis DB. It must not `flushdb` a shared Redis Cluster through an unprefixed client. Fix those clients to use the worker prefix. If a test cannot be fixed within three hypotheses, skip it only when the parallel pool is larger than one, record it in the ledger, and leave serial and xdist alone.
- **Cache.** Workers may load cacheprovider with a cache directory under that worker's basetemp. They still receive no `--lf`, `--ff`, `--nf`, or `--cache-clear`. The controller owns run-level selection. Update `Agents.md` in the same change.
- **Coverage, migrations, monolith, acceptance.** Out of the replacement. `test-backend-ci-with-coverage` and `test-migrations-ci` stay as they are. Acceptance is a smoke item only. Do not fold those modes into one Django process.
- **Telemetry.** Do not add a Sentry transport. Leave pytest-sentry configuration untouched.
- **Dependencies.** pytest-parallel's runtime dependency stays pytest only. Optional imports are `pytest-django`, `pytest-json-report`, and `pytest-rerunfailures`, all test or Sentry-side. No new runtime package. There is no binary-size gate. The plugin's import of `pytest_parallel.api` must stay free of those optional packages.
- **Ledger.** `docs/sentry-integration.md` in pytest-parallel is the living list of touch points, the intentional differences, and the verification command for each. It is updated when the behavior lands, not left as a proposal.
- **Loop speed.** Do not spend a phase speeding up the suite. The serial suite is 34 seconds. A single Sentry file is the Sentry loop. `make test` runs only at close.

### Delegated

The executor logs each of these and does not wait.

- Manifest filename and whether it is passed as a stripped internal option or an environment variable, as long as one code path parses it and user `addopts` cannot point it at another run's file.
- Exact JSONL field names for `attempt`, as long as every run event for setup, call, and teardown carries the same integer and version 1.
- Module split inside `src/pytest_parallel/` when `coordinator.py` or `worker.py` would otherwise gain a second responsibility. No new package, no plugin-emulation framework.
- The Sentry module path under `sentry.testutils.pytest` if `workers.py` is a poor fit. One module, not a package hierarchy.
- How the service canary is written, as long as worker A writes, worker B tears down, and A's key is still there.
- Which representative Snuba, Kafka, Relay, and acceptance files to smoke, chosen from tests that already use those fixtures. If none run without an extra service, park that file and say which service.

## Baseline

pytest-parallel serial, 2026-10-17, Python 3.14 venv: `uv run pytest tests/ -q --serial -p no:cacheprovider` → 119 passed, exit 0, 33.80 s. No known reds. `uv run ruff check` 0.19 s. `uv run ty check` 0.22 s. `tests/test_p0_correctness.py` alone was 17.81 s. The parallel half of `make test` was not run.

Sentry was not executed at preflight. Before ladder B, C, and F, run the same file list serial, with the local overrides below, and record the exit code in the campaign log. A candidate failure that serial also fails is baseline, not a regression. A candidate-only failure is a defect.

Local Sentry overrides, both for the serial baseline and the candidate: `PYTEST_ADDOPTS` empty (drops CI `--reruns=5 --durations=10 --fail-slow=60s`), `--reuse-db`, no `--fail-slow`. Record them on every command in `.work/artifacts/commands.txt`. Do not disable timeout or signal tests.

## Sequence

Two workstreams. Plugin owns `src/pytest_parallel/**`, `tests/**`, `README.md`, `Agents.md`, `docs/sentry-integration.md`. Sentry owns `src/sentry/testutils/pytest/**`, `src/sentry/utils/env.py`, `tests/conftest.py`, `tests/acceptance/conftest.py`, `.github/workflows/scripts/pytest-selected.py`, `Makefile`, and new tests under `tests/sentry/testutils/`. Neither lane edits `uv.lock` or workflow YAML. Shared files inside a repo stay in one lane.

### P0 Ground

**P0-1. Branches and baseline.** Size: one integrator pass. Owns no product files.
Proof: both worktrees exist, `pytest_parallel.__file__` in the Sentry venv points at the plugin worktree after `.venv/bin/pip install -e <plugin-worktree> --no-deps`, and the serial plugin command above still passes. Do not run `uv sync` or `devenv sync` afterward. Reinstall after every plugin merge before the next Sentry test.

### P1 Parity

**PP-1. Identity, network, drain.** Prerequisite: none. Owns the plugin tree.
`current_run` / `current_worker` with the semantics in Decisions. Worker entry sets identity before `pytest.main`. Tests under spawn (macOS default): a root conftest reads the worker index at import; serial has no worker; the controller's `current_worker()` is `None`; plan JSON is one document and has no run id; leaked worker env is a `UsageError`; `--parallel-network=inherit` allows a non-loopback connect that the default blocks; `--parallel-drain` is honored. Update README and `Agents.md` for the new options and the cache rule.
Proof: `uv run pytest tests/test_campaign.py tests/test_integration.py -q --serial -k "plan or network or worker"` plus the new test module by name, then `uv run ruff check` and `uv run ty check`.

**PP-2. Manifest collection.** Prerequisite: PP-1 merged. Same lane.
Default `nodeid` behavior stays. `manifest` mode uses the directory-root invocation proven below. Tests: parent order across interleaved files, a parametrized id, a duplicate nodeid occurrence, a unicode id, an unselected item in an assigned file, a missing id, a nested conftest that must run after plugin configure, and a worker that does not import an unassigned package.
Proof: new tests by name, then `uv run pytest tests/test_worker.py tests/test_p0_correctness.py -q --serial -k "collection or nodeid"`.

**PP-3. Attempts and single-writer reports.** Prerequisite: PP-2 merged. Same lane.
Protocol in Decisions, against pytest-rerunfailures 16.3's `rerun` outcome. Cases: fail then pass, exhausted reruns, setup rerun, teardown rerun, final skip after a failed attempt, stop between attempts, worker crash during a retry, maxfail while another attempt is in flight. JSON file and JUnit exist only in the controller destination and contain `_json_report_extra` fields (streams, metadata). A worker crash keeps the reports already replayed.
Proof: new tests by name. Phase check for the plugin workstream: `uv run pytest tests/ -q --serial`, then `uv run ruff check` and `uv run ty check`.

**SE-1. Resources, suffix, runner selection.** Prerequisite: PP-1 merged and reinstalled. Can run beside PP-2. Owns the Sentry files.
`workers` module and xdist delegation. Django suffix override. Worker env strips `DJANGO_SETTINGS_MODULE` and `PYTEST_XDIST_*`. `in_test_environment` is true for a parallel worker without `PYTEST_XDIST_WORKER`. `selenium.py` treats a parallel worker like an xdist worker for the controller-only option block. `test_timeout.py` keeps skipping in a worker process, using the role API. Runner rewrite at the start of `pytest-selected.py`: when `SENTRY_TEST_RUNNER=parallel`, strip `-n` / `--numprocesses` / `--dist` from `PYTEST_ADDOPTS` and append `-j <slots> --parallel-collection=manifest --parallel-network=inherit --parallel-drain=60s`; `serial` strips xdist distribution and adds `--serial`; `xdist` leaves addopts alone. Makefile `test-python-ci` calls that script and does not grow a second invocation. Flock as prescribed. `pytest_parallel_max_workers` returns 7.
Proof: `.venv/bin/pytest --reuse-db tests/sentry/testutils/test_runner_selection.py` (add this file; it must not need devservices). It covers slot math, addopts rewrite, and "parallel does not require `PYTEST_XDIST_WORKER`".

**SE-2. Parent selection, worker manifest.** Prerequisite: PP-2 and SE-1 merged. Same Sentry lane.
Sentry workers skip `TEST_GROUP` hashing, `SENTRY_SHUFFLE_TESTS`, and a second `SELECTED_TESTS_FILE` filter when a manifest is present. The parent still does all three. A test with two files and a fixed seed shows that shuffling a subset is not the parent order, and that the manifest run is.
Proof: the new test module by name, using `pytest-parallel`'s manifest mode and Sentry's modifyitems hooks, without devservices. Use a tiny Django-free fixture tree if the Sentry conftest cannot load; if the real conftest is required, use the dates file from SE-3 instead and say so in the log.

**SE-3. Collection and database slice.** Prerequisite: SE-2. Same lane. One `devservices up` if the files need it. If it fails, park SE-3 through SE-5 with the command output.
Files: `tests/sentry/utils/test_dates.py`, `tests/sentry/utils/test_strings.py`. Serial, `-j 1`, and `-j 2` under `SENTRY_TEST_RUNNER=parallel` execute the same nodeids. Then add `tests/sentry/api/endpoints/test_frontend_version.py` and `tests/sentry/cache/test_redis.py`. Assert effective `TEST.NAME` for default, control, and secondary ends in `_gw{index}` only on workers. Canary: two workers, Redis key written by index 0 survives index 1 teardown.
Proof: those four files, commands recorded. A one-worker run does not satisfy the canary.

**SE-4. Service smoke and retries.** Prerequisite: PP-3 and SE-3. Same lane.
One file each for Snuba, Kafka, Redis Cluster, and Relay, plus one acceptance bootstrap file if the existing within-job acceptance job would have run it. Then a disposable fail-then-pass file with `--reruns=5` whose JSON has a `reruns` array and whose final outcome is passed, and one real Sentry file with `--reruns=1`. Compare parsed JSON fields `nodeid`, outcome, and `reruns`, not summary text. JUnit is present and written once.
Proof: recorded commands and exit codes. Park an unavailable service by name.

**SE-5. Stand-in for one backend job.** Prerequisite: SE-4, or SE-3 if SE-4's service files are parked. Same lane.
A fixed file list of at least the SE-3 files, written under `.work/artifacts/selected-tests.txt`, run through `pytest-selected.py` with `TOTAL_TEST_GROUPS=1` and `SENTRY_TEST_RUNNER=parallel` at `-j 2`. Compare nodeids and terminal outcomes to the serial baseline of that list. Classify flakes with the attempt log; do not excuse a failure that serial does not have.
Proof: both exit codes and the compared nodeid set in `.work/artifacts/`. This is the local stand-in for a GitHub shard. Do not start GitHub.

### P2 Hardening

**H-1. Docs and ledger.** Prerequisite: PP-3 and SE-1. Either lane, after those merge. Owns README, `Agents.md`, `docs/sentry-integration.md`, and Sentry's testutils module docstring only if one is required for a public function.
The ledger lists every xdist touch point below as done or parked. README examples show `Shard`, `current_run`, `current_worker`, `--parallel-collection=manifest`, and `--parallel-network`. No performance claims.

### P3 Optimization

No items. Measurements taken while debugging go in the campaign log and do not become gates.

### P4 Close

**C-1. Dead path and review.** Prerequisite: every P1 and P2 item merged or parked.
Delete a compatibility branch only when a test shows the xdist and parallel paths both still work without it. Do not delete `xdist.py`, pytest-xdist, or the rollback runner. Load `ultrareview` on the two diffs if it is installed; otherwise review the diffs against boundaries, types, effects, errors, concurrency, persisted state, untrusted input, and tests, and fix P1 and P2 findings. Write the engineering report at `docs/sentry-integration.md` (architecture, commands, scopes actually run, parked blockers, temporary shims). Phase check: `make check` and `make test` in pytest-parallel. Sentry check is the SE-5 command, not the Sentry suite.

## Acceptance

| Deliverable | Proof |
| --- | --- |
| 1. Identity | PP-1 tests. A conftest reads `current_worker().index` at import under spawn. `current_run()` is `None` only before the first call, never as an import side effect. |
| 2. Manifest | PP-2 tests, including the directory-root order: invoking `.` configures plugins before a nested conftest; invoking a leaf file does not. Worker command line in manifest mode does not contain an assigned leaf path. |
| 3. Reports | PP-3 tests plus SE-4's JSON `reruns` array and a single JUnit file. |
| 4. Resources | SE-1 slot test and SE-3 database names and Redis canary. Native command works with `PYTEST_XDIST_WORKER` unset. |
| 5. Slice | SE-5 nodeid set equals serial. If parked, the report names the missing service and the command that failed, and deliverable 5 is not claimed. |

Plugin phase command (areas touched: the package): `uv run pytest tests/ -q --serial` then `uv run ruff check` and `uv run ty check`. Close only: `make test` (serial and parallel; the parallel half was not timed and exists to catch spawn integration). Sentry phase command: the file list of the items just merged, via `.venv/bin/pytest`, never bare `pytest` and never the whole `tests/` tree.

## Execution boundary

The launch prompt grants: local commits on `campaign/sentry-integration` and `campaign/pytest-parallel`; creating those worktrees; `pip install -e --no-deps` of the plugin into Sentry's existing venv; one `devservices up`; writes under `.work/` in both repos.

It does not grant: push, publish, `uv publish`, tags, PRs, `devenv sync`, `uv lock`, `uv sync`, `git clean`, `git reset`, editing unrelated dirty files, changing GitHub workflows, changing `uv.lock`, killing processes other than the campaign's workers, or transmitting credentials. Artifacts must not contain DSNs, passwords, or customer data.

Contract changes the owner will see in the diffs:

- `pytest_parallel.api` exports `RunInfo`, `WorkerInfo`, `current_run`, `current_worker`.
- CLI `--parallel-collection`, `--parallel-network`, `--parallel-drain`.
- JSONL events gain `version` and `attempt`. Plan JSON does not change.
- Workers may enable a private cacheprovider. `Agents.md` cache sentence is updated in that commit.
- Default collection, network, and drain match today's behavior.
- Sentry gains `SENTRY_TEST_RUNNER` and `SENTRY_TEST_WORKERS`. Default runner remains xdist. No lockfile change.

## Non-goals

Cross-job hashing, `plan_shards`, matrix size, required-check names, coverage combination, migration mode, monolith mode, work stealing, remote workers, crash retries, execnet, a scheduler-replacement hook, a config DSL, historical-duration scheduling, publishing the package, and renaming `XDIST_WORKERS` across the repository.

## Reference

### What is true now

pytest-parallel 0.2.0 exports only `Shard` (`api.py`). Workers are `pytest.main` on absolute nodeids (`worker.py` `run_worker`). Collection fails unless the collected list equals the assignment (`pytest_collection_finish`). Drain default is 5.0 seconds. Plan JSON `"version": 1` is the scheduling plan, not the event stream. Runtime dependency is pytest. The plugin already refuses `-n`, `--pdb`, and `--trace`.

Sentry CI (`backend.yml`) appends `-n ${XDIST_WORKERS} --dist=loadfile` with `XDIST_WORKERS` 2 on pull requests and 3 otherwise. `setup-sentry` sets `PYTEST_ADDOPTS=--reruns=5 --durations=10 --fail-slow=60s`. `pytest-selected.py` shards files, writes a per-shard `SELECTED_TESTS_FILE`, and keeps the invocation as directory `tests` because a leaf path imports nested conftests before plugin configure. Confirmed with pytest 9 in this venv: `pytest tests` prints `ROOT TESTS CONFIGURE NESTED`; `pytest tests/pkg/test_a.py` prints `ROOT TESTS NESTED CONFIGURE`.

`xdist.py` reads `PYTEST_XDIST_WORKER` at import. Redis DBs are 9 through 15. Snuba base port is 1230. `sentry.py` seeds the cell name from `PYTEST_XDIST_TESTRUNUID`, sets snowflake from the worker number, filters collection from `SELECTED_TESTS_FILE`, hashes `TEST_GROUP`, shuffles when `SENTRY_SHUFFLE_TESTS` is set, pops `DJANGO_SETTINGS_MODULE` in `pytest_xdist_setupnodes`, and `flushdb`s Redis on configure and teardown, including prefix clients. `json_report_reruns.py` appends a `reruns` array only when the controller `JSONReport` is registered. `env.py` treats `PYTEST_XDIST_WORKER` as a test process.

### Parity register

The reference is Sentry at `624fb343` running xdist, plus serial pytest for outcomes. The oracle for outcomes is a serial run of the same file list with the local overrides. The oracle for slot names is the table in Prescribed resource slots, checked by test, not by running xdist beside the candidate.

Intentional differences: static whole-file assignment instead of `--dist=loadfile`; no `workerinput`; no execnet; no worker crash retry; manifest collection instead of leaf nodeid arguments; network `inherit` instead of per-test `enable_network`; drain 60s on the Sentry path.

Each row needs a test that fails if the behavior is wrong. Build the register in `docs/sentry-integration.md` as the rows land.

| Behavior | Item |
| --- | --- |
| Slot names and the 7-worker cap | SE-1 |
| Controller is not a worker slot | PP-1, SE-1 |
| Shared cell name, distinct snowflake | SE-3 |
| Database suffix `_gw{n}` on every alias, none on serial, no tox double suffix | SE-3 |
| Outer file selection and hash split happen once | SE-2 |
| Shuffle order is the parent order | SE-2 |
| Empty CI shard exits 0; bad manifest does not run the suite | SE-2 |
| `rerun` is non-terminal; JSON `reruns` kept; final outcome once | PP-3, SE-4 |
| One JSON file and one JUnit file | PP-3 |
| Redis canary across workers | SE-3 |
| Unprefixed cluster flush does not wipe the other worker | SE-3 or parked in the ledger |
| Worker conftest sees identity before Django settings | PP-1, SE-1 |
| `--reuse-db` names stable across two sequential runs | SE-3 |
| xdist rollback still suffixes via `workerinput` | SE-1 |

### Repeat these only once

Agents will fake `workerinput`, pass leaf paths, compare collection counts, reapply `TEST_GROUP` on workers, import xdist from the native path, and turn off reruns or audits to get green. The tests named on PP-1, PP-2, SE-1, and SE-2 are the guards. Do not add a lint for them.

## Decision log

Append one line per judgment call a reader would otherwise miss: the call and why.

## Campaign log

Append one line per phase end: what merged, what parked, which proof command passed.

## For the owner afterwards

- Diffs on `campaign/sentry-integration` and `campaign/pytest-parallel`. Nothing is pushed.
- `docs/sentry-integration.md` for what ran, what parked, and the contract list above.
- To make CI use the runner later: publish a pin, then set `SENTRY_TEST_RUNNER=parallel` and keep `XDIST_WORKERS` as the slot count. The workflow YAML does not need a new test command if `pytest-selected.py` is the entry point; it does need to stop forcing `-n` or rely on the strip that SE-1 added. That follow-up is not this campaign.
