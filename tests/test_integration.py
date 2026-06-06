from __future__ import annotations

import os
import subprocess
import sys


def test_jobs_option_runs_parallel_worker(tmp_path):
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_ok():\n    assert True\n")
    env = os.environ.copy()
    env.pop("_PYTEST_PARALLEL_WORKER", None)
    env.pop("PYTEST_PARALLEL_WORKER_ID", None)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "-q", "-j", "1"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )

    assert result.returncode == 0
    assert "pytest-parallel: 1 workers, 1 tests" in result.stdout
    assert "1 passed" in result.stdout
