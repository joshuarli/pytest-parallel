# Worker report emission scenario

At `c07dceb`, the worker source still has blob `2e239c0`. A collection
report without a diagnostic now has a direct JSONL witness requiring
`longrepr` to be null. The two direct observer tests caught all 60
identities in the same three methods with mutmut 3.8.1, pytest 9.2.0 and
CPython 3.15.2 on macOS arm64. No selected identity survived or timed out.
Activating `pytest_collectreport__mutmut_15` in generated source made the
new assertion fail with the string `"None"` in place of null.

To repeat the two-observer run, use the scratch recipe below with
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and the test selection
`-k "worker_report_observer_jsonl_from_pytest_hooks or worker_report_observer_keeps_missing_collection_detail_null"`.
The full local suite passed 157 tests. Other worker decisions and the
whole-change gate remain open.

This local DSLP-4 scenario covers `ResultReporter._serialize_report`,
`pytest_collectreport`, and `pytest_runtest_logreport` in `worker.py`. The
runtime source is unchanged from base `e49e7fb1080a8766c28c2257b8261966aef8dcd0`
(worker blob `2e239c05db55341035ade42b55bd493bd3bb6823`). It does not qualify
the rest of the worker, coordinator decoding, the whole suite's mutation
coverage, or CI. The observations below are from macOS arm64, Python 3.15.2,
pytest 9.2.0 and mutmut 3.8.1.

The selected inventory is all generated identities in those three methods:
serialization 1–10, collection 1–18, and test report 1–32. Before the two new
observers, all 60 were `no tests`: the selected existing integration tests
reach the reporter in a subprocess outside mutmut's test association. After the
observers, 59 were killed and one survived. There were no unrun, timeout, or
suspicious selected identities. The survivor is collection 15. It changes a
false `longrepr` from JSON null to the string `None`. Ordinary passed collection
reports are suppressed, and the observed failed collection report has a real
long representation. A plugin-created non-passing report without one could
expose this difference. It remains an uncovered diagnostic case, not an
assertion of equivalence or an accepted risk. All other generated package
identities were outside this selection.

The direct observer uses pytest's hooks to emit JSONL for a failing test, xfail,
and collection failure. It checks custom public-hook serialization and the
fallback for a non-dict hook result, phase outcomes, captured output and report
fields. The spawned-worker observer verifies the controller receives an actual
child's custom serialized report, phase output, failure, user properties, xfail
and warning. The worker PID in the custom field must differ from the observer's
PID. Neither test changes the plugin's runtime code.

Activation used the generated `mutants/src` first on `PYTHONPATH`. With
`MUTANT_UNDER_TEST=''`, the direct observer passed and printed the generated
`worker.py` path. With
`MUTANT_UNDER_TEST=pytest_parallel.worker.xǁResultReporterǁ_serialize_report__mutmut_2`,
it failed with `KeyError: 'custom_witness'`; that mutation bypasses the public
serialization hook. Both commands used the same mutmut interpreter and test.
Two separate scratch-source faults removed the `serialization_witness` and
`custom_witness` fields from serialized hook results. The spawned observer
failed with `AttributeError` for the missing field, and the direct observer
failed with `KeyError`, respectively. Both fault commands exited 1, and the
scratch source was restored. These are semantic controls, not import failures.

To reproduce the inventory, make a fresh scratch copy of `src`, `tests`, and
`pyproject.toml` under `.work/tmp`. Append the following to the copy's TOML:

```toml
[tool.mutmut]
source_paths = ["src"]
pytest_add_cli_args = ["-p", "no:parallel"]
pytest_add_cli_args_test_selection = ["tests/test_p0_correctness.py", "-k", "worker_report_observer or worker_stream_replays_collection_failure or phase_outcomes_and_junitxml"]
```

Acquire the campaign's shared mutation lock by atomic `mkdir` before running.
Set `TMPDIR` to the worktree's `.work/tmp`, set `PYTHONPATH` to the copy's
`src`, and run the following from the copy under `cpu-guard --cores 2` with
`CARGO_BUILD_JOBS=1`, `RUST_TEST_THREADS=1`, `RUSTC_WRAPPER=kache`, and
`PYTHON_CPU_COUNT=2`. Impose a 1,200-second outer deadline, kill and reap the
owned process group on expiry, then release the lock. The runs here completed
within that deadline. Inspect `results --all true`; the run exit code alone
does not classify mutants.

```sh
mutmut run --max-children 1 \
  'pytest_parallel.worker.xǁResultReporterǁ_serialize_report__mutmut_*' \
  'pytest_parallel.worker.xǁResultReporterǁpytest_collectreport__mutmut_*' \
  'pytest_parallel.worker.xǁResultReporterǁpytest_runtest_logreport__mutmut_*'
mutmut results --all true
```

The pinned tool was the existing isolated mutmut environment. The base and
final runs exited 0. The generated-source activation command ran pytest from
`mutants` with `PYTHONPATH=$PWD/src`, imported `pytest_parallel.worker`, printed
its `__file__`, and ran
`tests/test_p0_correctness.py::test_worker_report_observer_jsonl_from_pytest_hooks`.
The same test with the named mutation above must fail at the custom field.

The final native `make test` exited 0 with 154 passed, and `make lint` exited 0
with Ruff and ty passing. The base suite exited 0 with 152 passed. An installed
wheel built after mutation was installed into a scratch target. Python printed
that target's `pytest_parallel/worker.py`, and the two observers plus existing
collection, warning, and uncaptured-output witnesses passed: five passed, 51
deselected. No runtime change was made, so consumer and runtime performance
qualification were not requested by this scenario. Pre- and post-test timing
gates reported hot host processes in the attempted suite-cost observations;
their timings are discarded. A subsequent quiet attempt was deferred when its
pre-gate reported a hot process. Linux, Windows, broader plugin combinations,
and the survivor's artificial collection-report case remain unverified.
