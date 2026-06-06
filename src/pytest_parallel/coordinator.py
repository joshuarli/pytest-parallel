"""Coordinator for static pytest worker shards."""

from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, Protocol, cast

import pytest

from . import _DEFAULT_MAX_WORKERS

_OUTCOME_CHARS = {
    "failed": "F",
    "passed": ".",
    "skipped": "s",
}

ReportOutcome = Literal["passed", "failed", "skipped"]


class ShardItem(Protocol):
    nodeid: str
    location: tuple[str, int | None, str]


class Coordinator:
    def __init__(self, config: pytest.Config, requested_workers: int) -> None:
        self.config = config
        self.requested_workers = requested_workers
        self._work_dir = Path(tempfile.mkdtemp(prefix="pytest_parallel_"))
        self._completed = 0
        self._failed = 0
        self._total = 0

    def run(self, session: pytest.Session) -> bool:
        if not session.items:
            shutil.rmtree(self._work_dir, ignore_errors=True)
            return True

        max_workers = self.config.hook.pytest_parallel_max_workers() or _DEFAULT_MAX_WORKERS
        num_workers = max(1, min(self.requested_workers, len(session.items), max_workers))
        groups = self._partition(session.items, num_workers)
        test_lists = self._write_test_lists(groups)
        self._total = len(session.items)

        terminal = session.config.get_terminal_writer()
        terminal.sep("=", f"pytest-parallel: {num_workers} workers, {self._total} tests")
        for index, group in enumerate(groups):
            file_count = len({item.nodeid.split("::")[0] for item in group})
            terminal.line(f"  worker {index}: {len(group)} tests ({file_count} files)")

        self.config.hook.pytest_parallel_pre_spawn(config=self.config, num_workers=num_workers)

        active = [(index, test_lists[index]) for index, group in enumerate(groups) if group]
        # Fork/spawn at the last possible point before monitoring starts. At this point
        # pytest has completed collection and the shard files exist, but the coordinator
        # has not started polling loops or helper threads.
        workers = self._spawn(active)
        self._monitor(workers, {item.nodeid: item for item in session.items}, session)

        session.testsfailed = self._failed
        shutil.rmtree(self._work_dir, ignore_errors=True)
        return True

    @staticmethod
    def _partition(items: Sequence[ShardItem], num_workers: int) -> list[list[ShardItem]]:
        by_file: dict[str, list[ShardItem]] = {}
        file_order: list[str] = []
        for item in items:
            file_name = item.nodeid.split("::")[0]
            if file_name not in by_file:
                by_file[file_name] = []
                file_order.append(file_name)
            by_file[file_name].append(item)

        buckets: list[list[ShardItem]] = [[] for _ in range(num_workers)]
        for index, file_name in enumerate(file_order):
            buckets[index % num_workers].extend(by_file[file_name])
        return buckets

    def _write_test_lists(self, groups: Sequence[Sequence[ShardItem]]) -> list[Path]:
        paths = []
        for index, items in enumerate(groups):
            path = self._work_dir / f"worker_{index}_tests.txt"
            path.write_text("\n".join(item.nodeid for item in items) + "\n")
            paths.append(path)
        return paths

    def _forwarded_args(self) -> list[str]:
        args = []
        skip_next = False
        known = self.config.known_args_namespace
        positionals = set(getattr(known, "file_or_dir", []) or [])

        for arg in sys.argv[1:]:
            if skip_next:
                skip_next = False
                continue
            if arg in {"-n", "--numprocesses"}:
                skip_next = True
                continue
            if arg.startswith("-n") and arg != "-n":
                continue
            if arg.startswith("--numprocesses="):
                continue
            if arg in positionals:
                positionals.discard(arg)
                continue
            args.append(arg)
        return args

    def _spawn(self, active: list[tuple[int, Path]]) -> list[tuple[int, Any, Path, Path]]:
        from .worker import run_worker

        context = cast(Any, _multiprocessing_context())
        forwarded_args = json.dumps(self._forwarded_args())
        workers = []
        for index, test_list in active:
            result_path = self._work_dir / f"worker_{index}_results.jsonl"
            output_path = self._work_dir / f"worker_{index}_output.txt"
            result_path.touch()
            output_path.touch()
            env = os.environ.copy()
            env["PYTEST_PARALLEL_WORKER_ID"] = str(index)
            env["_PYTEST_PARALLEL_ARGS"] = forwarded_args
            env["_PYTEST_PARALLEL_NODEIDS"] = str(test_list)
            env["_PYTEST_PARALLEL_OUTPUT"] = str(output_path)
            env["_PYTEST_PARALLEL_RESULTS"] = str(result_path)
            env["_PYTEST_PARALLEL_ROOTDIR"] = str(self.config.rootpath)
            env["_PYTEST_PARALLEL_WORKER"] = "1"
            self.config.hook.pytest_parallel_worker_env(env=env, worker_id=index)

            process = context.Process(target=run_worker, args=(env,))
            process.start()
            workers.append((index, process, result_path, output_path))
        return workers

    def _monitor(
        self,
        workers: list[tuple[int, Any, Path, Path]],
        items_by_nodeid: dict[str, ShardItem],
        session: pytest.Session,
    ) -> None:
        terminal = session.config.get_terminal_writer()
        terminal_reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if terminal_reporter is not None:
            session.config.pluginmanager.unregister(terminal_reporter, "terminalreporter")

        offsets = {index: 0 for index, _, _, _ in workers}
        reports: list[pytest.TestReport] = []
        reports_by_nodeid: dict[str, pytest.TestReport] = {}

        alive = {index for index, _, _, _ in workers}
        while alive:
            for index, process, result_path, _ in workers:
                if index not in alive:
                    continue
                self._read_results(index, result_path, offsets, terminal, items_by_nodeid, reports, reports_by_nodeid)
                if not process.is_alive():
                    alive.discard(index)
            time.sleep(0.05)

        for index, _, result_path, _ in workers:
            self._read_results(index, result_path, offsets, terminal, items_by_nodeid, reports, reports_by_nodeid)

        terminal.line(f"  {self._completed}/{self._total} completed, {self._failed} failed")

        for index, process, _, output_path in workers:
            process.join()
            if process.exitcode not in {0, 1}:
                self._failed += 1
                terminal.sep("-", f"worker {index} crashed with exit code {process.exitcode}")
                for line in output_path.read_text().splitlines():
                    terminal.line(line)

        if terminal_reporter is not None:
            for report in reports:
                terminal_reporter.stats.setdefault(report.outcome, []).append(report)
            session.config.pluginmanager.register(terminal_reporter, "terminalreporter")

    def _read_results(
        self,
        worker_id: int,
        result_path: Path,
        offsets: dict[int, int],
        terminal: Any,
        items_by_nodeid: dict[str, ShardItem],
        reports: list[pytest.TestReport],
        reports_by_nodeid: dict[str, pytest.TestReport],
    ) -> None:
        with result_path.open() as result_file:
            result_file.seek(offsets[worker_id])
            for raw_line in result_file:
                event = json.loads(raw_line)
                self._record_event(worker_id, event, terminal)
                item = items_by_nodeid.get(event["nodeid"])
                if item is not None:
                    report = self._make_report(event, item)
                    if report.nodeid in reports_by_nodeid:
                        reports[reports.index(reports_by_nodeid[report.nodeid])] = report
                    else:
                        reports.append(report)
                    reports_by_nodeid[report.nodeid] = report
            offsets[worker_id] = result_file.tell()

    def _record_event(self, worker_id: int, event: dict[str, object], terminal: Any) -> None:
        outcome = str(event["outcome"])
        nodeid = str(event["nodeid"])
        duration = float(cast(str | int | float, event.get("duration", 0.0)))
        if outcome != "rerun":
            self._completed += 1
        if outcome == "failed":
            self._failed += 1

        if self.config.option.verbose > 0:
            terminal.line(f"[w{worker_id}] {nodeid} {outcome.upper()} ({duration:.2f}s)")
        else:
            terminal.write(_OUTCOME_CHARS.get(outcome, "?"))
            terminal.flush()

        if outcome == "failed" and event.get("longrepr"):
            terminal.line("")
            terminal.line(f"FAILED {nodeid} ({duration:.2f}s)", red=True)
            for line in str(event["longrepr"]).splitlines():
                terminal.line(f"    {line}")

    @staticmethod
    def _make_report(event: dict[str, object], item: ShardItem) -> pytest.TestReport:
        outcome = _coerce_outcome(event["outcome"])
        return pytest.TestReport(
            nodeid=str(event["nodeid"]),
            location=item.location,
            keywords={},
            outcome=outcome,
            longrepr=cast(Any, event.get("longrepr")),
            when="call",
            duration=float(cast(str | int | float, event.get("duration", 0.0))),
        )


def _multiprocessing_context() -> multiprocessing.context.BaseContext:
    if sys.platform == "darwin":
        return multiprocessing.get_context("spawn")
    if sys.platform.startswith("linux"):
        return multiprocessing.get_context("fork")
    return multiprocessing.get_context("spawn")


def _coerce_outcome(value: object) -> ReportOutcome:
    outcome = str(value)
    if outcome in {"passed", "failed", "skipped"}:
        return cast(ReportOutcome, outcome)
    return "failed"
