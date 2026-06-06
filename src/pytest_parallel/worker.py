"""Worker process for pytest-parallel."""

from __future__ import annotations

import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout

import pytest


class ResultReporter:
    def __init__(self, results_path: str) -> None:
        self.results_path = results_path

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if not self.results_path:
            return
        if report.when != "call" and not (report.when == "setup" and report.failed):
            return

        with open(self.results_path, "a") as result_file:
            result_file.write(
                json.dumps(
                    {
                        "nodeid": report.nodeid,
                        "outcome": report.outcome,
                        "duration": round(report.duration, 3),
                        "longrepr": str(report.longrepr) if report.longrepr else None,
                    }
                )
                + "\n"
            )


def main() -> None:
    sys.exit(_run_from_env())


def run_worker(env: dict[str, str]) -> None:
    os.environ.clear()
    os.environ.update(env)
    output_path = os.environ.get("_PYTEST_PARALLEL_OUTPUT")
    if output_path:
        with open(output_path, "a") as output_file, redirect_stdout(output_file), redirect_stderr(output_file):
            sys.exit(_run_from_env())
    sys.exit(_run_from_env())


def _run_from_env() -> int:
    nodeids_file = os.environ["_PYTEST_PARALLEL_NODEIDS"]
    with open(nodeids_file) as test_file:
        nodeids = [line.strip() for line in test_file if line.strip()]

    forwarded_args = json.loads(os.environ.get("_PYTEST_PARALLEL_ARGS", "[]"))
    results_path = os.environ.get("_PYTEST_PARALLEL_RESULTS", "")
    rootdir = os.environ.get("_PYTEST_PARALLEL_ROOTDIR")
    rootdir_args = [f"--rootdir={rootdir}"] if rootdir else []
    return pytest.main([*rootdir_args, *forwarded_args, *nodeids], plugins=[ResultReporter(results_path)])


if __name__ == "__main__":
    main()
