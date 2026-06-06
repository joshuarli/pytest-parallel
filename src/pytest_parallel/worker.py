"""Worker process for pytest-parallel."""

from __future__ import annotations

import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

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
    sys.exit(pytest.main())


def run_worker(
    env: dict[str, str],
    nodeids: list[str],
    forwarded_args: list[str],
    rootdir: str,
    results_path: Path,
    output_path: Path,
) -> None:
    os.environ.clear()
    os.environ.update(env)
    rootdir_args = [f"--rootdir={rootdir}"] if rootdir else []
    args = [*rootdir_args, *forwarded_args, *_absolute_nodeids(rootdir, nodeids)]
    with output_path.open("a") as output_file, redirect_stdout(output_file), redirect_stderr(output_file):
        sys.exit(pytest.main(args, plugins=[ResultReporter(str(results_path))]))


def _absolute_nodeids(rootdir: str, nodeids: list[str]) -> list[str]:
    if not rootdir:
        return nodeids

    root = Path(rootdir)
    absolute = []
    for nodeid in nodeids:
        file_name, *rest = nodeid.split("::")
        path = Path(file_name)
        if not path.is_absolute():
            path = root / path
        absolute.append("::".join([str(path), *rest]))
    return absolute


if __name__ == "__main__":
    main()
