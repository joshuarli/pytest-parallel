from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class BenchSelectionTests(unittest.TestCase):
    def run_bench(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(ROOT / "benchmarks/bench.py"), *args], cwd=ROOT,
                              env=env, capture_output=True, text=True, check=False)

    def test_selection_and_rejection(self) -> None:
        result = self.run_bench("list", "--tier", "change", "--area", "scheduling", "--skip", "uniform")
        assert result.returncode == 0
        assert "uniform: change, scheduling, excluded" in result.stdout
        assert "uneven: change, scheduling, selected" in result.stdout
        assert self.run_bench("list", "--name", "missing").returncode != 0
        assert self.run_bench("list", "--tier", "edit", "--name", "uneven").returncode != 0

    def test_dry_run_and_missing_preflight_do_not_write_results(self) -> None:
        out = ROOT / ".work/bench"
        before = set(out.iterdir()) if out.exists() else set()
        result = self.run_bench("run", "--dry-run")
        assert result.returncode == 0, result.stderr
        assert before == (set(out.iterdir()) if out.exists() else set())
        env = dict(os.environ, PATH="")
        result = self.run_bench("run", env=env)
        assert result.returncode != 0
        assert "perf-gate-ready missing" in result.stderr
        assert before == (set(out.iterdir()) if out.exists() else set())


if __name__ == "__main__":
    unittest.main()
