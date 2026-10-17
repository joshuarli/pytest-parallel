from __future__ import annotations

import json
import os
import sys
import time
import warnings
from collections.abc import Generator, Sequence
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

_PROTOCOL_VERSION = 1


class ResultReporter:
    def __init__(
        self,
        results_path: str,
        *,
        expected_nodeids: Sequence[str] | None = None,
        stop_path: Path | None = None,
        output_path: Path | None = None,
        ramp_delay: float = 0.0,
    ) -> None:
        self.results_path = results_path
        self.expected_nodeids = list(expected_nodeids) if expected_nodeids is not None else None
        self.stop_path = stop_path
        self.output_path = output_path
        self.ramp_delay = ramp_delay
        self.config: pytest.Config | None = None
        self._capture_mode = "fd"
        self._collection_finished = False
        self._ramp_applied = False
        self._uncaptured_chunks: list[str] = []

    def _emit(self, payload: dict[str, Any]) -> None:
        if not self.results_path:
            return
        record = {"v": _PROTOCOL_VERSION, **payload}
        line = json.dumps(record, default=repr) + "\n"
        with open(self.results_path, "a", encoding="utf-8") as result_file:
            result_file.write(line)
            result_file.flush()

    def _should_stop(self) -> bool:
        return self.stop_path is not None and self.stop_path.exists()

    def _wait_for_ramp(self) -> bool:
        if self.ramp_delay <= 0.0:
            return False
        deadline = time.monotonic() + self.ramp_delay
        while True:
            if self._should_stop():
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return False
            time.sleep(min(0.02, remaining))

    @contextmanager
    def _record_uncaptured_phase_output(self) -> IteratorOrGenerator:
        if self._capture_mode != "no" or self.output_path is None:
            yield
            return
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            start_offset = self.output_path.stat().st_size
        except OSError:
            start_offset = 0
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            try:
                with self.output_path.open("rb") as handle:
                    handle.seek(start_offset)
                    chunk = handle.read().decode("utf-8", errors="replace")
                if chunk:
                    self._uncaptured_chunks.append(chunk)
            except OSError:
                pass

    def pytest_configure(self, config: pytest.Config) -> None:
        self.config = config
        self._capture_mode = str(config.getoption("capture", default="fd"))

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        if report.passed:
            return
        serialized = self._serialize_report(report)
        self._emit(
            {
                "type": "collect_report",
                "nodeid": report.nodeid,
                "outcome": report.outcome,
                "longrepr": str(report.longrepr) if report.longrepr else None,
                "report": serialized,
            }
        )

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self._collection_finished = True
        collected = [item.nodeid for item in session.items]
        self._emit({"type": "collection", "nodeids": collected})
        if self.expected_nodeids is not None and collected != self.expected_nodeids:
            session.items.clear()
            raise session.Interrupted("worker collection mismatch")

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_protocol(self, item: pytest.Item, nextitem: pytest.Item | None) -> bool | None:
        if self._should_stop():
            item.session.shouldstop = "stopped by coordinator"
            return True
        if not self._ramp_applied:
            self._ramp_applied = True
            if self._wait_for_ramp():
                item.session.shouldstop = "stopped by coordinator"
                return True
        return None

    def pytest_runtest_logstart(self, nodeid: str, location: tuple[str, int | None, str]) -> None:
        self._uncaptured_chunks.clear()
        self._emit(
            {
                "type": "test_start",
                "nodeid": nodeid,
                "location": [location[0], location[1], location[2]],
            }
        )

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_setup(self, item: pytest.Item) -> Generator[None]:
        with self._record_uncaptured_phase_output():
            yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item: pytest.Item) -> Generator[None]:
        with self._record_uncaptured_phase_output():
            yield

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_teardown(self, item: pytest.Item, nextitem: pytest.Item | None) -> Generator[None]:
        with self._record_uncaptured_phase_output():
            yield

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        serialized = self._serialize_report(report)
        self._emit(
            {
                "type": "report",
                "nodeid": report.nodeid,
                "when": report.when,
                "outcome": report.outcome,
                "duration": float(report.duration),
                "longrepr": str(report.longrepr) if report.longrepr else None,
                "wasxfail": getattr(report, "wasxfail", None),
                "report": serialized,
            }
        )

    def pytest_runtest_logfinish(self, nodeid: str, location: tuple[str, int | None, str]) -> None:
        stdout = "".join(self._uncaptured_chunks)
        self._uncaptured_chunks.clear()
        payload: dict[str, Any] = {
            "type": "test_finish",
            "nodeid": nodeid,
            "location": [location[0], location[1], location[2]],
        }
        if stdout:
            payload["stdout"] = stdout
        self._emit(payload)
        if self._should_stop() and self.config is not None:
            session = getattr(self.config, "_ parallel_session", None)
            if session is not None:
                session.shouldstop = "stopped by coordinator"

    def pytest_warning_recorded(
        self,
        warning_message: warnings.WarningMessage,
        when: str,
        nodeid: str,
        location: tuple[str, int, str] | None,
    ) -> None:
        if when != "runtest":
            return
        self._emit(
            {
                "type": "warning",
                "message": str(warning_message.message),
                "category_module": warning_message.category.__module__,
                "category_name": warning_message.category.__qualname__,
                "filename": warning_message.filename,
                "lineno": int(warning_message.lineno),
                "line": warning_message.line,
                "when": when,
                "nodeid": nodeid,
                "location": list(location) if location is not None else None,
            }
        )

    def pytest_internalerror(self, excrepr: Any) -> None:
        self._emit(
            {
                "type": "internal_error",
                "excrepr": str(excrepr),
            }
        )

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int | pytest.ExitCode) -> None:
        self._emit(
            {
                "type": "session_finish",
                "exitstatus": int(exitstatus),
                "shouldstop": str(session.shouldstop) if session.shouldstop else None,
                "shouldfail": str(session.shouldfail) if session.shouldfail else None,
            }
        )

    def _serialize_report(self, report: pytest.TestReport | pytest.CollectReport) -> dict[str, Any]:
        if self.config is not None:
            data = self.config.hook.pytest_report_to_serializable(config=self.config, report=report)
            if isinstance(data, dict):
                return data
        data = report._to_json()
        data["$report_type"] = report.__class__.__name__
        return data


IteratorOrGenerator = Generator[None]


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
    worker_env = dict(env)
    raw_ramp = worker_env.pop("_PYTEST_PARALLEL_RAMP_DELAY", "0")
    try:
        ramp_delay = float(raw_ramp)
    except ValueError:
        ramp_delay = 0.0
    os.environ.clear()
    os.environ.update(worker_env)
    stop_path = results_path.parent / "stop"
    rootdir_args = [f"--rootdir={rootdir}"] if rootdir else []
    args = [*rootdir_args, *forwarded_args, *_absolute_nodeids(rootdir, nodeids)]
    reporter = ResultReporter(
        str(results_path),
        expected_nodeids=nodeids,
        stop_path=stop_path,
        output_path=output_path,
        ramp_delay=ramp_delay,
    )
    with output_path.open("a", encoding="utf-8") as output_file, redirect_stdout(output_file), redirect_stderr(output_file):
        exit_code = pytest.main(args, plugins=[reporter])
        output_file.flush()
        sys.exit(int(exit_code))


def _absolute_nodeids(rootdir: str, nodeids: list[str]) -> list[str]:
    if not rootdir:
        return nodeids

    root = Path(rootdir)
    absolute = []
    for nodeid in nodeids:
        file_name, sep, rest = nodeid.partition("::")
        path = Path(file_name)
        if not path.is_absolute():
            path = root / path
        absolute.append(f"{path}{sep}{rest}" if sep else str(path))
    return absolute


if __name__ == "__main__":
    main()
