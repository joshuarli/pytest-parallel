# Coordinator event stream scenario

Bounded inventory, defined before mutation: every mutmut identity generated for
`Coordinator._read_worker_events` and `Coordinator._process_worker_event` in
`src/pytest_parallel/coordinator.py` at base `2c6957155dce22853dbadd9ade66e8b0cbc59fbe`.
Other functions and modules are outside this scenario. The run uses mutmut
3.8.1, one child and a 20-minute outer deadline; all identities in the two named
functions must be classified, including unrun identities. This is not a whole
crate or CI gate. Broader DSLP-4 remains open.

On macOS arm64, CPython 3.15.2, pytest 9.2.0, base real-worker
negative control `cpu-guard --cores 1 -- uv run pytest -p no:parallel
 tests/test_p0_correctness.py::test_real_worker_invalid_utf8_inside_json_event_is_rejected -q`
(with `PYTHONPATH=$PWD/src` and the locked Python environment) exited 1: the
inner pytest returned 0 and reported `1 passed` after a byte in its JSON event
was changed to `0xff`. The candidate reader rejects the line before parsing;
the same case plus the seven final-read cases exit 0, eight passed. The real
worker writes the original events, then the test alters or appends to its file
before the final read. The clean case checks a successful run; the others
check nonzero status and the specific diagnostic. Existing crash, partial-line,
reconciliation, cancellation and reaping witnesses remain in the suite.

With `TMPDIR=$PWD/.work/tmp`, `UV_PROJECT_ENVIRONMENT=$PWD/.work/tmp/project-env`,
`UV_NO_SYNC=1`, `UV_PYTHON_DOWNLOADS=never`, `PYTHONPATH=$PWD/src`,
`CARGO_BUILD_JOBS=1`, `RUST_TEST_THREADS=1`, `RUSTC_WRAPPER=kache`,
`cpu-guard --cores 1 -- make test` exited 0 (138 passed) and the same guard
with `make lint` exited 0 (Ruff and ty). An initial run using a different
existing environment lacked coverage and failed the coverage witness; the
locked local environment was created with `uv sync --locked` and the full run
was repeated. No tests were removed.

Base and candidate wheels were built from a `git archive` of the base and the
candidate tree with `cpu-guard --cores 1 -- uv build --wheel --out-dir DIR
SOURCE`, then installed into separate local `uv venv` environments with
`uv pip install --python ENV/bin/python WHEEL`. Base wheel 31,168 bytes,
SHA-256 `73102cdaac562c8296e6dae56e870ff47e7b3878b02aaf6d8430cffc6e38a1d0`;
candidate 31,199 bytes, SHA-256
`ca926a80951100def79e7bce01b5392f087991a04bc7ac83ddb45aa00bbd8335`.
The candidate imported `coordinator.py` from its installed site-packages.
With `PYTHONPATH`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD`, and `PYTEST_ADDOPTS` unset,
`cpu-guard --cores 1 -- .work/tmp/consumer/bin/python -m pytest -p no:parallel
 tests/test_p0_correctness.py::test_real_worker_invalid_utf8_inside_json_event_is_rejected
 tests/test_p0_correctness.py::test_real_worker_stream_final_read_rejects_corruption
 tests/test_p0_correctness.py::test_worker_os_exit_0_mid_suite_cannot_produce_false_success -q`
exited 0, nine passed.

The installed-wheel 28-test workload and environment recipe in
[hook evidence](deslop-hook-errors.md) were used unchanged, with `/usr/bin/time
-l` around each guarded pytest and up to 30 attempts. Each measurement had a
zero `perf-gate-ready` before and zero `perf-gate-ready -1` immediately after;
pairs with a hot-process diagnostic were discarded. Five accepted alternating
pairs (seconds, base then candidate) were (1.257, 1.248), (1.258, 1.636),
(1.603, 1.216), (1.266, 1.263), (1.260, 1.271). All passed 28 tests. Medians
were 1.260 and 1.263 seconds; ranges overlap and do not establish a difference.
The corresponding `/usr/bin/time -l` maximum resident set observations ranged
48,005,120–48,365,568 bytes base and 48,136,192–48,644,096 candidate. These
are command-level observations, not aggregate peak memory of all workers.

To reproduce mutation, use a fresh scratch copy of `src`, `tests`, and
`pyproject.toml`, and append this configuration to the copy (the source SHA-256
for the two-method run was
`df03be97e4151e060f820d571fc56d80681d225ab39933caf2da6d09537971c4`):

```toml
[tool.mutmut]
source_paths = ["src"]
pytest_add_cli_args = ["-p", "no:parallel"]
pytest_add_cli_args_test_selection = ["tests/test_p0_correctness.py", "-k", "protocol_validation or partial_jsonl or invalid_utf8 or real_worker_stream or incomplete_finish or missing_call_report or reconcile_rejects"]
```

With mutmut 3.8.1 and pytest in the same environment, set `PYTHONPATH` to the
copy's `src` and run under the shared mutation lock and a one-core guard, with
a 1,200-second outer deadline and process-group kill/reap on expiry:

```sh
mutmut run --max-children 1 \
  'pytest_parallel.coordinator.xǁCoordinatorǁ_read_worker_events__mutmut_*' \
  'pytest_parallel.coordinator.xǁCoordinatorǁ_process_worker_event__mutmut_*'
mutmut results --all true
```

The displayed 3,543 denominator includes the generated package inventory;
the two name patterns select the bounded component, and other identities are
outside this scenario. The report and generated diffs, not the mutmut exit
code alone, determine classifications.

After adding the dispatch and offset witnesses, the same guarded `make test`
exited 0 with 149 passed, and `make lint` exited 0. The installed candidate
consumer also ran `cpu-guard --cores 1 -- .work/tmp/consumer/bin/python -m
pytest -p no:parallel tests/test_p0_correctness.py -k 'real_worker_stream or
real_worker_invalid_utf8 or complete_events_before_partial or
worker_os_exit_0_mid_suite' -q`. It exited 0 with 20 passed and 31 deselected.
The selection covers only the named witnesses, not the full suite.

After the final diagnostic cases, the same full gates exited 0: 152 passed,
Ruff passed and ty passed. Repeating the installed-wheel selection with
`or missing_worker_stream` added to the expression exited 0: 23 passed and
31 deselected. The runtime wheel was unchanged after the earlier build.

Parent suite-cost verification used the same locked environment and source
imports, `PYTHON_CPU_COUNT=2` (two automatic workers), `cpu-guard --cores 2`,
and separate valid repo-owned TMPDIRs. The base at `2c69571` passed 130 tests
in 14.77 s wall; the candidate passed 152 in 15.81 s. Both
`perf-gate-ready` / `make test` / immediate `perf-gate-ready -1` sequences
exited 0/0/0, with no post-run hot-process diagnostic. The 1.04 s suite-cost
increase is within the 30 s allowance. An earlier default-worker-count sample
with a hot-process diagnostic was discarded. These costs are not a speedup claim.

For the outer deadline, the runner used `subprocess.Popen` with
`start_new_session=True`, `wait(timeout=1200)`, and on any exception sent
`SIGKILL` to the process group and called `wait()` before returning. The
shared lock was acquired by atomic `mkdir` and released by its owner after the
runner exited. Generated code and results stayed under the copied scratch tree.

The complete first inventory after adding warning and collection witnesses was
61 reader identities and 91 dispatcher identities. Of 152 selected, 124 were
killed and 28 survived. There were zero no-tests, timeouts, or suspicious
results. The 3,391 identities outside these functions were not evaluated.
The original survivors, using `R` for `_read_worker_events` and `D` for
`_process_worker_event`, were:

- R: 2, 17, 18, 22, 23, 25, 26, 27, 29, 30, 36, 38, 41, 45, 48, 49, 54.
- D: 9, 10, 11, 24, 25, 56, 64, 76, 78, 81, 82.

Each number is the `__mutmut_N` suffix on the corresponding generated name.
The selection included the real worker tests available at that time. Later
witnesses were added for incomplete reads after a complete record, invalid
truncated bytes, precise diagnostics, missing files, invalid warning payloads,
controller collection-hook replay, and uncaptured output.

Review of the generated diffs establishes these remaining classifications:
R17 and R18 change the offset only after the final truncated fragment. The
monitor calls the final read once, then reconciles and never reads that state
again. R22 uses the default UTF-8 codec in place of explicit `utf-8`. R25 and
R36 use the equivalent codec spelling `UTF-8`. R29 increases the displayed
truncation snippet limit from 120 to 121 characters. The latter is an observable
diagnostic difference and is not covered by the tests; neither its survivor
nor the final-offset cases justify a claim about arbitrary external callers.

The first follow-up explicitly selected D9, D10, D11, D24, D25, D56, D64,
D76, D78, D81, D82, R2, R23, R26, R27, R30, R38, R41, R45, R48, R49,
R54, and R60, with the new tests included. R60 had already been killed in the
full inventory. Of these 23, 18 were killed and D81, R38, R41, R45 and R49
survived. The initial interleaving oracle could match worker output instead of
a controller report. The test now observes `pytest_runtest_logreport` and
requires the passing call report. The D81 witness now requires the full default
error diagnostic. A fresh five-identity run killed all five. Combined with
the full inventory, 146 identities are killed and the six R identities above
remain. No selected identity is unrun. These are separate runs with a growing
test selection, not a single mutmut score.

For each follow-up, copy the updated tests to a fresh scratch tree, append the
same configuration, and add `or complete_events_before_partial or
missing_worker_stream` to the `-k` expression. Run the same bounded command
with the exact identity names listed above in place of the two wildcards. For
the final run select D81, R38, R41, R45 and R49. Each run exited 0; inspect
`mutmut results --all true` and the individual `mutmut show NAME` diffs.

Activation control used the generated `mutants/src` first on `PYTHONPATH` and
the mutmut environment's Python. The following command printed the generated
`coordinator.py` path and passed once with `MUTANT_UNDER_TEST=''`. With
`MUTANT_UNDER_TEST='pytest_parallel.coordinator.xǁCoordinatorǁ_process_worker_event__mutmut_5'`
it exited 1: `collection_verified` was false because the mutant reverses the
version check. This is a semantic failure, not an import failure.

```sh
python -c 'import pytest_parallel.coordinator as c; import pytest; print(c.__file__); raise SystemExit(pytest.main(["-p", "no:parallel", "tests/test_p0_correctness.py::test_partial_jsonl_line_is_buffered_until_newline", "-q"]))'
```

The final observer change passed the full 152-test suite, Ruff and ty, and the
23 selected installed-wheel cases again. This scenario covers macOS only. It
does not qualify the unselected functions, other operating systems, external
consumers, or CI. Broader DSLP-4 remains open.
