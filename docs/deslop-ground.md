# Ground evidence

Base `4968f8e59563c92e4617fcafd7ab322d64ff6c9c` (PR 15 merge). PR 15 head `0c57bde9d9a02b481d73bec4ec654616d69bc385` has successful CI test jobs on Ubuntu 26.04 ARM and Xcode 27, and lint, verified with `gh pr view 15 --json headRefOid,mergeCommit,statusCheckRollup,url`. The PR workflow's unconditional `make test` step uses bash and targets the default branch. The current fleet rule's `_pull_request_workflows` returned `supported=True`, no problems or unsupported steps, against this worktree; the separate Linux smoke step does not replace `make test`. No workflow edit was needed.

On macOS, Python 3.15.2, uv 0.13.7 and locked pytest 9.2.0, cold and warm `make test` took 7.50s and 7.48s wall, 119 passed each. These are individual cost observations, not a speed comparison. Each `perf-gate-ready` before and `perf-gate-ready -1` immediately after exited 0; both cold and warm checks reported a hot unrelated process tree, so these timings are noisy and are not performance acceptance. No external process was stopped. Cold means a newly created worktree-local environment and initially absent worktree-local pytest cache; package installation and two Python version checks were outside the timed region. OS and uv global caches were not cleared. Warm reused that environment and pytest cache. Reproduce from a fresh worktree with:

```sh
mkdir -p .work/tmp
export UV_PROJECT_ENVIRONMENT="$PWD/.work/ground-final" UV_PYTHON=/Users/josh/.local/share/uv/python/cpython-3.15-macos-aarch64-none/bin/python3.15 UV_PYTHON_DOWNLOADS=never UV_LOCKED=1 TMPDIR="$PWD/.work/tmp" PYTEST_ADDOPTS='-o cache_dir=.work/ground-final-cache'
uv sync --locked
uv run python --version
perf-gate-ready
/usr/bin/time -p cpu-guard --cores 2 -- make test
perf-gate-ready -1
# Repeat the last three commands for warm; check both gate exit statuses.
```

Final verification with the same environment: `perf-gate-ready` (0), `/usr/bin/time -p cpu-guard --cores 2 -- make test` (0, 119 passed, 7.53s wall), `perf-gate-ready -1` (0); then the same gates around `cpu-guard --cores 2 -- make lint` (0, Ruff and ty passed, 1.18s wall). The post-test and pre-lint gates also reported hot processes.

The initial attempt with `UV_NO_MANAGED_PYTHON=1` recreated the environment inside each timed run and is excluded from these costs. Neither sample measures installation. Tests use temporary local files and pytest's normal pass accounting; no performance limiter was profiled. The test suite is not a benchmark.

`benchmarks/run_benchmarks.py` builds uniform (8×10), uneven (80+7), many-tiny (40×1), and single-file (100 parametrized) synthetic suites, timing collection, serial, count and round-robin execution plus a single plan invocation; subprocess failures abort. These CPU-trivial tests measure scheduler/startup shapes but do not represent expensive real tests. Before a runtime change affecting scheduling, collection, workers, or replay, define and document a reproducible representative workload with realistic test costs and distribution, run at least five interleaved base/candidate pairs under passing pre/post gates, and report spread and correctness. The existing harness can supplement that workload; no workload performance acceptance is claimed here.

`pyproject.toml` declares pytest as the sole runtime dependency; Ruff, ty and uv are development dependencies. Tracked-file name and source text searches for vendor, third-party, notice, upstream, copied and adapted material found no vendored tree or stated upstream revision; LICENSE is this project's MIT license. No endpoints are exposed. The JSON plan and worker JSONL boundaries are mapped in AGENTS.md; pytest JUnit replay is exercised by `tests/test_p0_correctness.py::test_phase_outcomes_and_junitxml_match_serial`.

This documentation-only change does not alter the public API or runtime, so stuff and toolbox consumer tests were not run; toolbox billing is excluded from this campaign. Coverage, mutation, the in-memory plugin restriction and a qualified serial mutmut route remain Tests-step work (DSLP-4); they are not Ground proof. No mutation or coverage was run.
