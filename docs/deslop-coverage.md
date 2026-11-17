# Coverage prerequisite evidence

Scope: base `85ef2ff7303da5af52d97fa1ecefb02fb123ec4b`, macOS arm64, CPython 3.15.2, uv 0.13.7, pytest 9.2.0, coverage.py 7.17.3 (C extension). The stuff index `/current/simple/coverage/` served the pinned cp315 macOS and Linux wheels; `uv.lock` records their hashes. Only coverage was added to dev dependencies. The built wheel before and after was 30,994 bytes, with identical member names and `Requires-Dist: pytest>=9.0`; runtime code and dependencies did not change. Builds: `uv build --wheel --out-dir .work/wheel-before` and `uv build --wheel --out-dir .work/wheel-after`, both exit 0. Installation/build elapsed cost was not measured.

Test-pyramid audit: edit gate `uv run pytest -p no:parallel tests/test_coverage.py -q` exercises the installed-wheel witness. Change gates and existing CI run `make test`, `make lint`; `make coverage` is a diagnostic that instruments the full suite. The existing boundary map and 119-test costs are in [Ground](deslop-ground.md) and AGENTS.md. Unit/component checks cover scheduling and protocol validation; subprocess integration checks cover collection, process cleanup, CLI and network behavior. Coverage can falsely pass through controller imports, stale files, omitted unimported modules, missing worker data, or an empty selection. The witness and fresh target data address those cases within this scope; coverage alone does not establish assertion quality. No tests were removed; a broader per-test audit and mutation remain open.

Baseline serial command used an isolated `uv run --with coverage==7.17.3` tool, `coverage run -m pytest -p no:parallel tests/ -q`, then `coverage combine` and `coverage report`, with an absolute config and data path under `.work/coverage-baseline`. All exited 0; 119 passed, seven package modules, 1,760 statements, 277 missed, 716 branches and 139 partial, combined total 82%. `source` was the absolute `src/pytest_parallel` directory, including unimported modules; the subprocess patch includes subprocess tests. The serial baseline is not a worker-only measurement.

`make coverage` creates a fresh owned `.work/coverage/run.*` directory and runs two workers under `coverage run`. Campaign callers acquire their shared mutation/coverage lock and apply the CPU guard outside this portable target; neither host-specific path is required by the repository. Its absolute configuration is:

```ini
[run]
branch = True
parallel = True
concurrency = multiprocessing
patch = subprocess
source = <absolute repository>/src/pytest_parallel
data_file = <absolute fresh run directory>/data
```

It checks each worker's PID and raw data before combining after pytest exits. `make coverage` exited 0, 120 passed, no skips, 1,483/1,760 lines and 554/716 branches covered (82% combined, 77% branches); output is in the fresh run directory. This reports observations, not a coverage threshold or disposition of all unrun decisions. Guard uses coverage 7.17.3 data filename layout and is qualified here on macOS only. Linux and other plugin combinations are unverified.

The installed-wheel fixture builds and installs the actual wheel into an isolated target and asserts the loaded plugin path. Separate files invoke opposite outcomes of a subject branch only inside tests. Serial and `-j 2` both pass two tests; the latter records two distinct worker PIDs, neither the controller. The JSON oracle requires executed lines `[1, 2, 3, 5]`, arcs `[[2, 3], [2, 5]]`, and an unimported module with no executed lines and missing lines `[1, 2]`. The negative control stops `Coverage.current()` inside both workers immediately before subject import; the same oracle fails on `worker lines missing` and the test requires that failure. Focused command above exited 0. This qualifies native coverage.py settings, not pytest-cov or mutmut's rejected in-memory plugin.

Warm base `perf-gate-ready; /usr/bin/time -p cpu-guard --cores 2 -- make test; perf-gate-ready -1` exited 0 throughout: 119 passed, 7.46s. The same final sequence exited 0, 120 passed, 7.53s, no skips. Hot-process diagnostics did not change either gate's actual exit 0; the earlier worker report incorrectly treated them as a failed gate. These are individual test-cost observations, not a speedup claim. Final `cpu-guard --cores 2 -- make lint` exited 0. No mutation run, CI lane, other platform or real consumer was exercised; DSLP-4 and the separate DSLP-6 remain open.

Parent acceptance removes the campaign host's absolute lock path and CPU-guard dependency from the public Makefile target. The test subprocess helper now kills and reaps its owned process group on any exceptional exit. Under an external shared lock and two-core guard, `make coverage` passes all 120 cases again, followed by `make lint`, both exit 0. The new report has 1,484/1,760 covered lines and 554/716 branches; the one-line difference from the earlier report is retained as an observation, not a threshold. The raw worker guards pass before combination, and the installed-wheel negative control remains decisive.

The parent also reran the ordinary final `make test` with the same pre/time/post
sequence: all three exit 0, 120 passed, zero skips, 6.42s wall. This is within
the suite-cost allowance against the 7.46s baseline observation; it is not a
measured speedup. Runtime wheel bytes remain identical, so existing consumers'
runtime behavior is unaffected. Real-consumer coverage qualification remains
separate from the installed-wheel fixture.
