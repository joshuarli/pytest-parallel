# Scheduling hook error evidence

DSLP-6: a scheduling hook's `AttributeError` previously selected defaults. The controller now looks up each hook before calling it, and lets exceptions from its implementation reach pytest. Missing hooks and `None` still select defaults; custom weights, groups and pins retain their existing behavior. A hook failure aborts before worker startup. The JSON plan path emits no plan and reports the exception on stderr.

On macOS arm64, CPython 3.15.2 and pytest 9.2.0, base `ef73bbe6e4c29641ad79a806b13053151ab053d1` was archived and built with `cpu-guard --cores 1 -- uv build --wheel --out-dir "$PWD/.work/tmp/base-wheel" .work/tmp/base`; the candidate used `cpu-guard --cores 1 -- uv build --wheel --out-dir "$PWD/.work/tmp/candidate-wheel" .`. Both had `TMPDIR="$PWD/.work/tmp"`, `UV_PYTHON_DOWNLOADS=never`, `CARGO_BUILD_JOBS=1`, `RUST_TEST_THREADS=1` and `RUSTC_WRAPPER=kache`. Base wheel SHA-256 `21c633674796f647d039c924627986cd23826269956308e17d5632d841ccf74c` (31,199 bytes); candidate `.work/tmp/candidate-wheel/joshuarli_pytest_parallel-0.4.0-py3-none-any.whl` SHA-256 `73102cdaac562c8296e6dae56e870ff47e7b3878b02aaf6d8430cffc6e38a1d0` (31,168 bytes). Separate local virtual environments installed each wheel with `uv pip install --python ENV/bin/python WHEEL`. The candidate's `python -c 'import pytest_parallel.coordinator as c; print(c.__file__)'` printed `.work/tmp/consumer/lib/python3.15/site-packages/pytest_parallel/coordinator.py`, not the source tree; the base likewise loaded from `base-consumer`.

With `PYTEST_DISABLE_PLUGIN_AUTOLOAD` unset, `cpu-guard --cores 1 -- .work/tmp/base-consumer/bin/python -m pytest -p no:parallel tests/test_campaign.py::test_hook_attribute_error_fails_plan -q` exited 1: all three hook cases failed because their plan commands returned 0. This is the bounded fault control. The same test against the candidate, together with `test_hooks_weights_groups_and_pin_via_plan`, `test_missing_hooks_use_defaults`, and `test_json_plan_stdout_is_one_document`, exited 0 with six cases passed. The regression also runs normal execution and asserts the pre-spawn hook was not reached. `make test` and `make lint`, under `cpu-guard --cores 1` and a locked Python 3.15 environment, passed: 130 tests, Ruff and ty. An initial consumer run accidentally set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=0`, which pytest treats as enabled, and failed due to missing CLI options; it was rerun with that variable unset.

Runtime comparison used separate installed wheels and eight files with 2, 3, 4, or 5 parametrized tests each (28 total). Each test creates a temporary file, serializes and reads 500 JSON records, parses them and hashes the bytes. This mixed local data-processing workload is a reproducible proxy for modest tests, not a measurement of a particular consumer. Each run used `python -m pytest -j 2 -q` under `cpu-guard --cores 1`, with a passing `perf-gate-ready` immediately before and `perf-gate-ready -1` immediately after; all commands exited 0 and all 28 tests passed. Five accepted alternating base/candidate pairs had no hot-process diagnostic; four other pairs with such diagnostics were discarded despite zero gate exits. Base median 1.188 s (range 1.181–1.203), candidate median 1.213 s (range 1.177–1.243). Ranges overlap; this workload does not establish a speed difference or identify a runtime limiter. No unrelated process was stopped. The earlier sequence also contained hot-process diagnostics and was discarded.

To reproduce the workload and comparison, create the two wheel environments above, request a quiet window, and run the following with `TMPDIR` set inside this worktree. It rejects a nonzero gate or test exit, missing pass count, or a hot-process diagnostic, and alternates base then candidate. The time includes pytest startup, collection, scheduling and worker execution.

```python
import os, pathlib, statistics, subprocess, time
root = pathlib.Path.cwd()
work = root / '.work/tmp/perf-workload'
work.mkdir(parents=True, exist_ok=True)
(work / 'pytest.ini').write_text('[pytest]\n')
for i in range(8):
    (work / f'test_case_{i}.py').write_text('''import hashlib, json
import pytest
@pytest.mark.parametrize("case", range(%d))
def test_processing(case, tmp_path):
    payload = {"case": case, "rows": [{"id": i, "text": "sample" * 20} for i in range(500)]}
    path = tmp_path / "data.json"
    path.write_text(json.dumps(payload))
    data = path.read_bytes()
    assert json.loads(data)["case"] == case
    assert len(hashlib.sha256(data).digest()) == 32
''' % (2 + i % 4))
env = os.environ.copy()
for name in ('PYTEST_ADDOPTS', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD'):
    env.pop(name, None)
results = {'base-consumer': [], 'consumer': []}
while len(results['consumer']) < 5:
    pair = {}
    for side in results:
        pre = subprocess.run(['perf-gate-ready'], capture_output=True, text=True)
        start = time.monotonic()
        run = subprocess.run(['cpu-guard', '--cores', '1', '--', str(root / '.work/tmp' / side / 'bin/python'), '-m', 'pytest', '-j', '2', '-q'], cwd=work, env=env, capture_output=True, text=True)
        elapsed = time.monotonic() - start
        post = subprocess.run(['perf-gate-ready', '-1'], capture_output=True, text=True)
        assert pre.returncode == run.returncode == post.returncode == 0 and '28 passed' in run.stdout
        pair[side] = (elapsed, pre.stdout + pre.stderr + post.stdout + post.stderr)
    if any('hot process' in result[1] for result in pair.values()):
        continue
    for side, (elapsed, _) in pair.items():
        results[side].append(elapsed)
for side, values in results.items():
    print(side, values, statistics.median(values), min(values), max(values))
```

This proof covers the three hooks and local installed-wheel consumers on macOS; Linux, Windows, and external consumer repositories were not exercised. It does not qualify broader mutation or CI.
