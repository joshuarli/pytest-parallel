from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

import pytest

from pytest_parallel.coordinator import Coordinator, PlannedWorker


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("_PYTEST_PARALLEL_WORKER", None)
    env.pop("PYTEST_PARALLEL_WORKER_ID", None)
    return env


def _run_pytest(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=cwd,
        env=env or _clean_env(),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def test_worker_os_exit_1_cannot_produce_false_success(tmp_path: Path) -> None:
    test_file = tmp_path / "test_crash.py"
    test_file.write_text(
        "import os\n"
        "def test_before():\n"
        "    assert True\n"
        "def test_hard_exit():\n"
        "    os._exit(1)\n"
        "def test_after():\n"
        "    assert True\n"
    )
    result = _run_pytest([str(test_file), "-j", "1", "-q"])
    assert result.returncode != 0, result.stdout
    assert "test_hard_exit" in result.stdout


def test_worker_os_exit_0_mid_suite_cannot_produce_false_success(tmp_path: Path) -> None:
    test_file = tmp_path / "test_exit_zero.py"
    test_file.write_text(
        "import os\n"
        "def test_ hard_zero():\n"
        "    os._exit(0)\n"
        "def test_unreached():\n"
        "    assert True\n"
    )
    test_file.write_text(
        "import os\n"
        "def test_hard_zero():\n"
        "    os._exit(0)\n"
        "def test_unreached():\n"
        "    assert True\n"
    )
    result = _run_pytest([str(test_file), "-j", "1", "-q"])
    assert result.returncode != 0, result.stdout
    assert "test_unreached" in result.stdout or "unreported" in result.stdout.lower()


def test_worker_sigkill_reports_signal_and_last_test(tmp_path: Path) -> None:
    test_file = tmp_path / "test_sigkill.py"
    test_file.write_text(
        "import os, signal\n"
        "def test_killed():\n"
        "    os.kill(os.getpid(), signal.SIGKILL)\n"
    )
    result = _run_pytest([str(test_file), "-j", "1", "-q"])
    assert result.returncode != 0, result.stdout
    assert "test_killed" in result.stdout
    assert str(int(signal.SIGKILL)) in result.stdout or "SIGKILL" in result.stdout


def test_worker_early_pytest_exit_does_not_pass_unrun_tests(tmp_path: Path) -> None:
    f1 = tmp_path / "test_one.py"
    f2 = tmp_path / "test_two.py"
    f1.write_text(
        "import pytest\n"
        "def test_stop():\n"
        "    pytest.exit('early exit', returncode=0)\n"
        "def test_never_runs():\n"
        "    assert False\n"
    )
    f2.write_text("def test_other():\n    assert True\n")
    result = _run_pytest([str(tmp_path), "-j", "2", "-q"])
    assert result.returncode != 0, result.stdout


def test_phase_outcomes_and_junitxml_match_serial(tmp_path: Path) -> None:
    suite = tmp_path / "test_phases.py"
    suite.write_text(
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def broken_setup():\n"
        "    raise RuntimeError('setup boom')\n\n"
        "@pytest.fixture\n"
        "def skipping_setup():\n"
        "    pytest.skip('skip in setup')\n\n"
        "@pytest.fixture\n"
        "def broken_teardown():\n"
        "    yield\n"
        "    raise RuntimeError('teardown boom')\n\n"
        "def test_pass():\n"
        "    print('captured pass stdout')\n"
        "    assert True\n\n"
        "def test_fail():\n"
        "    print('captured fail stdout')\n"
        "    assert 1 == 2\n\n"
        "def test_setup_error(broken_setup):\n"
        "    pass\n\n"
        "def test_setup_skip(skipping_setup):\n"
        "    pass\n\n"
        "def test_teardown_error(broken_teardown):\n"
        "    assert True\n\n"
        "@pytest.mark.skip(reason='marker skip')\n"
        "def test_marker_skip():\n"
        "    pass\n\n"
        "@pytest.mark.xfail(reason='known bug')\n"
        "def test_xfail():\n"
        "    assert False\n\n"
        "@pytest.mark.xfail(reason='unexpectedly fixed')\n"
        "def test_xpass():\n"
        "    assert True\n\n"
        "@pytest.mark.xfail(reason='strict unexpected pass', strict=True)\n"
        "def test_strict_xpass():\n"
        "    assert True\n"
    )
    serial_xml = tmp_path / "serial.xml"
    parallel_xml = tmp_path / "parallel.xml"

    serial_res = _run_pytest([str(suite), "--serial", f"--junitxml={serial_xml}", "--durations=0"])
    parallel_res = _run_pytest([str(suite), "-j", "1", f"--junitxml={parallel_xml}", "--durations=0"])

    assert serial_res.returncode == parallel_res.returncode
    for expected_fragment in ("2 failed", "2 passed", "2 skipped", "1 xfailed", "1 xpassed", "2 errors"):
        assert expected_fragment in serial_res.stdout, serial_res.stdout
        assert expected_fragment in parallel_res.stdout, parallel_res.stdout
    assert "captured fail stdout" in parallel_res.stdout
    assert "slowest durations" in parallel_res.stdout

    serial_root = ET.parse(serial_xml).find("testsuite")
    parallel_root = ET.parse(parallel_xml).find("testsuite")
    assert serial_root is not None
    assert parallel_root is not None
    for attr in ("tests", "errors", "failures", "skipped"):
        assert parallel_root.attrib[attr] == serial_root.attrib[attr], attr


def test_collection_error_aborts_execution_by_default(tmp_path: Path) -> None:
    bad = tmp_path / "test_bad.py"
    good = tmp_path / "test_good.py"
    marker = tmp_path / "ran.txt"
    bad.write_text("import non_existent_module_xyz\n")
    good.write_text(f"from pathlib import Path\ndef test_ok():\n    Path({str(marker)!r}).write_text('ran')\n")

    res = _run_pytest([str(tmp_path), "-j", "2"])
    assert res.returncode == int(pytest.ExitCode.INTERRUPTED), res.stdout
    assert not marker.exists()


def test_continue_on_collection_errors_preserves_failure_status(tmp_path: Path) -> None:
    bad = tmp_path / "test_bad.py"
    good = tmp_path / "test_good.py"
    bad.write_text("import non_existent_module_xyz\n")
    good.write_text("def test_ok():\n    assert True\n")

    res = _run_pytest([str(tmp_path), "-j", "1", "--continue-on-collection-errors"])
    assert res.returncode == int(pytest.ExitCode.TESTS_FAILED), res.stdout


def test_programmatic_pytest_main_ignores_unrelated_sys_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_file = tmp_path / "test_prog.py"
    test_file.write_text("def test_alpha():\n    assert True\ndef test_beta():\n    assert True\n")

    monkeypatch.delenv("_PYTEST_PARALLEL_WORKER", raising=False)
    monkeypatch.delenv("PYTEST_PARALLEL_WORKER_ID", raising=False)
    monkeypatch.setattr(sys, "argv", ["custom-wrapper", "--definitely-not-a-pytest-flag"])

    recorded: list[tuple[str, str, str]] = []

    class RecordingPlugin:
        def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
            recorded.append((report.nodeid, str(report.when), report.outcome))

    rc = pytest.main([str(test_file), "-k", "alpha", "-j", "1", "-q"], plugins=[RecordingPlugin()])
    assert rc == 0
    assert [r[1] for r in recorded] == ["setup", "call", "teardown"]
    assert all(r[0].endswith("test_alpha") for r in recorded)


def test_in_memory_execution_plugin_is_rejected_with_usage_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_file = tmp_path / "test_plug.py"
    test_file.write_text("def test_one():\n    assert True\n")

    monkeypatch.delenv("_PYTEST_PARALLEL_WORKER", raising=False)
    monkeypatch.delenv("PYTEST_PARALLEL_WORKER_ID", raising=False)

    class ExecutionMutatingPlugin:
        def pytest_runtest_setup(self, item: pytest.Item) -> None:
            pass

    rc = pytest.main([str(test_file), "-j", "1", "-q"], plugins=[ExecutionMutatingPlugin()])
    assert rc == int(pytest.ExitCode.USAGE_ERROR)


def test_worker_collection_mismatch_fails_loudly(tmp_path: Path) -> None:
    test_file = tmp_path / "test_mismatch.py"
    test_file.write_text(
        "import os, pytest\n"
        " WORKER = os.environ.get('_PYTEST_PARALLEL_WORKER') == '1'\n"
    )
    test_file.write_text(
        "import os, pytest\n"
        "IDS = ['worker_id'] if os.environ.get('_PYTEST_PARALLEL_WORKER') == '1' else ['parent_id']\n"
        "@pytest.mark.parametrize('val', IDS)\n"
        "def test_dynamic(val):\n"
        "    assert True\n"
    )
    res = _run_pytest([str(test_file), "-j", "1", "-q"])
    assert res.returncode != 0, res.stdout
    assert "mismatch" in res.stdout.lower() or "not found" in res.stdout.lower()


def test_global_maxfail_stops_across_workers(tmp_path: Path) -> None:
    f1 = tmp_path / "test_w1.py"
    f2 = tmp_path / "test_w2.py"
    f1.write_text(
        "import time\n"
        "def test_fail_1():\n"
        "    assert False\n"
        "def test_slow_after_1():\n"
        "    time.sleep(0.6)\n"
        "    assert True\n"
    )
    f2.write_text(
        "import time\n"
        "def test_fail_2():\n"
        "    assert False\n"
        "def test_slow_after_2():\n"
        "    time.sleep(0.6)\n"
        "    assert True\n"
    )
    res = _run_pytest([str(tmp_path), "-j", "2", "--maxfail=1", "-q"])
    assert res.returncode == int(pytest.ExitCode.TESTS_FAILED), res.stdout
    assert "stopping after" in res.stdout


def test_spawn_failure_cleans_up_earlier_workers(tmp_path: Path) -> None:
    config = Mock()
    config.hook.pytest_parallel_worker_env = Mock()
    config.known_args_namespace.file_or_dir = []
    config.invocation_params.args = ()
    config.invocation_params.plugins = ()
    config.rootpath = tmp_path
    coordinator = Coordinator(cast(Any, config), 2)
    coordinator._work_dir = tmp_path

    p0 = Mock()
    p0.is_alive.return_value = True
    p1 = Mock()
    p1.start.side_effect = RuntimeError("spawn failed")

    context = Mock()
    context.Process.side_effect = [p0, p1]

    with (
        patch("pytest_parallel.coordinator._multiprocessing_context", return_value=context),
        pytest.raises(RuntimeError, match="spawn failed"),
    ):
        coordinator._spawn(
            [PlannedWorker(0, ["a.py::test_1"], 0), PlannedWorker(1, ["b.py::test_1"], 1)]
        )

    p0.terminate.assert_called_once()


def test_pdb_is_rejected_in_parallel_mode(tmp_path: Path) -> None:
    test_file = tmp_path / "test_pdb.py"
    test_file.write_text("def test_ok():\n    assert True\n")
    res = _run_pytest([str(test_file), "-j", "1", "--pdb"])
    assert res.returncode == int(pytest.ExitCode.USAGE_ERROR), res.stdout


def test_jsonl_protocol_rejects_truncated_and_malformed_streams(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_file = tmp_path / "test_proto.py"
    test_file.write_text("def test_ok():\n    assert True\n")

    monkeypatch.delenv("_PYTEST_PARALLEL_WORKER", raising=False)
    monkeypatch.delenv("PYTEST_PARALLEL_WORKER_ID", raising=False)

    class TruncatingProcess:
        def __init__(self, *, target: Any, args: tuple[Any, ...]) -> None:
            self._results_path: Path = args[4]
            self.exitcode: int | None = None
            self.pid = 99999

        def start(self) -> None:
            self._results_path.write_text('{"v": 1, "type": "test_start", "nodeid": ', encoding="utf-8")
            self.exitcode = 0

        def is_alive(self) -> bool:
            return False

        def join(self, timeout: float | None = None) -> None:
            pass

        def terminate(self) -> None:
            pass

    fake_ctx = Mock()
    fake_ctx.Process = TruncatingProcess

    with patch("pytest_parallel.coordinator._multiprocessing_context", return_value=fake_ctx):
        rc = pytest.main([str(test_file), "-j", "1", "-q"])

    assert rc == int(pytest.ExitCode.TESTS_FAILED)


def _make_harness(tmp_path: Path, assigned: list[str]) -> tuple[Coordinator, Any, Any, dict[str, Any]]:
    from pytest_parallel.coordinator import WorkerState

    config = Mock()
    config.option.setuponly = False
    config.hook.pytest_runtest_logstart = Mock()
    config.hook.pytest_runtest_logreport = Mock()
    config.hook.pytest_runtest_logfinish = Mock()
    config.hook.pytest_collectreport = Mock()
    config.hook.pytest_warning_recorded.call_historic = Mock()
    config.hook.pytest_report_from_serializable = Mock(return_value=None)

    session = Mock()
    session.config = config
    session.testsfailed = 0
    session.shouldfail = False
    session.shouldstop = False

    process = Mock()
    process.exitcode = 0
    process.is_alive.return_value = False

    result_path = tmp_path / "worker_0_results.jsonl"
    output_path = tmp_path / "worker_0_output.txt"
    result_path.touch()
    output_path.touch()

    state = WorkerState(
        worker_id=0,
        process=process,
        result_path=result_path,
        output_path=output_path,
        assigned=assigned,
    )
    items_by_nodeid: dict[str, Any] = {}
    for nodeid in assigned:
        item = Mock()
        item.nodeid = nodeid
        item.location = (nodeid.partition("::")[0], 1, nodeid)
        items_by_nodeid[nodeid] = item

    coordinator = Coordinator(cast(Any, config), 1)
    coordinator._work_dir = tmp_path
    return coordinator, state, session, items_by_nodeid


def test_incomplete_finish_clears_active_test(tmp_path: Path) -> None:
    coordinator, state, session, items = _make_harness(tmp_path, ["a.py::test_1"])
    events = [
        '{"v": 1, "type": "collection", "nodeids": ["a.py::test_1"]}',
        '{"v": 1, "type": "test_start", "nodeid": "a.py::test_1"}',
        '{"v": 1, "type": "test_finish", "nodeid": "a.py::test_1"}',
    ]
    state.result_path.write_text("\n".join(events) + "\n", encoding="utf-8")
    coordinator._read_worker_events(state, items, session, Mock(), final=True)
    assert state.current_test is None
    assert any("incomplete phase reports" in err for err in state.protocol_errors)


def test_missing_call_report_clears_active_test(tmp_path: Path) -> None:
    coordinator, state, session, items = _make_harness(tmp_path, ["a.py::test_1"])
    events = [
        '{"v": 1, "type": "collection", "nodeids": ["a.py::test_1"]}',
        '{"v": 1, "type": "test_start", "nodeid": "a.py::test_1"}',
        '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "setup", "outcome": "passed", "duration": 0}',
        '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "teardown", "outcome": "passed", "duration": 0}',
        '{"v": 1, "type": "test_finish", "nodeid": "a.py::test_1"}',
    ]
    state.result_path.write_text("\n".join(events) + "\n", encoding="utf-8")
    coordinator._read_worker_events(state, items, session, Mock(), final=True)
    assert state.current_test is None
    assert any("missing call report" in err for err in state.protocol_errors)


def test_partial_jsonl_line_is_buffered_until_newline(tmp_path: Path) -> None:
    coordinator, state, session, items = _make_harness(tmp_path, ["a.py::test_1"])
    terminal = Mock()

    state.result_path.write_text('{"v": 1, "type": "collection", ', encoding="utf-8")
    coordinator._read_worker_events(state, items, session, terminal, final=False)
    assert state.offset == 0
    assert state.protocol_errors == []

    with state.result_path.open("a", encoding="utf-8") as handle:
        handle.write('"nodeids": ["a.py::test_1"]}\n')
    coordinator._read_worker_events(state, items, session, terminal, final=False)
    assert state.collection_verified is True
    assert state.protocol_errors == []


@pytest.mark.parametrize(
    ("events", "expected_error_substring"),
    [
        (['{"v": 2, "type": "collection", "nodeids": ["a.py::test_1"]}'], "unsupported protocol version"),
        (['{"v": 1, "type": "unknown_event"}'], "unknown event type"),
        (['not-json'], "malformed JSON"),
        (['[1, 2, 3]'], "non-object JSON"),
        (
            [
                '{"v": 1, "type": "collection", "nodeids": ["a.py::test_1"]}',
                '{"v": 1, "type": "collection", "nodeids": ["a.py::test_1"]}',
            ],
            "duplicate collection",
        ),
        (
            ['{"v": 1, "type": "test_start", "nodeid": "other.py::test_x"}'],
            "unassigned test",
        ),
        (
            [
                '{"v": 1, "type": "test_start", "nodeid": "a.py::test_1"}',
                '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "setup", "outcome": "mystery", "duration": 0.01}',
            ],
            "invalid report outcome",
        ),
        (
            [
                '{"v": 1, "type": "test_start", "nodeid": "a.py::test_1"}',
                '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "bogus", "outcome": "passed", "duration": 0.01}',
            ],
            "invalid report phase",
        ),
        (
            [
                '{"v": 1, "type": "test_start", "nodeid": "a.py::test_1"}',
                '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "setup", "outcome": "passed", "duration": -0.5}',
            ],
            "invalid report duration",
        ),
        (
            [
                '{"v": 1, "type": "test_start", "nodeid": "a.py::test_1"}',
                '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "call", "outcome": "passed", "duration": 0.01}',
            ],
            "invalid call phase transition",
        ),
        (
            [
                '{"v": 1, "type": "test_start", "nodeid": "a.py::test_1"}',
                '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "setup", "outcome": "failed", "duration": 0.01}',
                '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "call", "outcome": "passed", "duration": 0.01}',
            ],
            "invalid call phase transition",
        ),
        (
            [
                '{"v": 1, "type": "test_start", "nodeid": "a.py::test_1"}',
                '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "setup", "outcome": "passed", "duration": 0.01}',
                '{"v": 1, "type": "test_finish", "nodeid": "a.py::test_1"}',
            ],
            "incomplete phase reports",
        ),
    ],
)
def test_protocol_validation_rejects_invalid_events(
    tmp_path: Path,
    events: list[str],
    expected_error_substring: str,
) -> None:
    coordinator, state, session, items = _make_harness(tmp_path, ["a.py::test_1"])
    terminal = Mock()
    state.result_path.write_text("\n".join(events) + "\n", encoding="utf-8")

    coordinator._read_worker_events(state, items, session, terminal, final=True)
    assert any(expected_error_substring in err for err in state.protocol_errors), state.protocol_errors

    coordinator._reconcile_worker(state, items, session, terminal, None)
    assert session.testsfailed > 0


def test_reconcile_rejects_contradictory_exit_status(tmp_path: Path) -> None:
    coordinator, state, session, items = _make_harness(tmp_path, ["a.py::test_1"])
    terminal = Mock()
    events = [
        '{"v": 1, "type": "collection", "nodeids": ["a.py::test_1"]}',
        '{"v": 1, "type": "test_start", "nodeid": "a.py::test_1"}',
        '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "setup", "outcome": "passed", "duration": 0.01}',
        '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "call", "outcome": "passed", "duration": 0.01}',
        '{"v": 1, "type": "report", "nodeid": "a.py::test_1", "when": "teardown", "outcome": "passed", "duration": 0.01}',
        '{"v": 1, "type": "test_finish", "nodeid": "a.py::test_1"}',
        '{"v": 1, "type": "session_finish", "exitstatus": 0}',
    ]
    state.result_path.write_text("\n".join(events) + "\n", encoding="utf-8")
    state.process.exitcode = 1

    coordinator._read_worker_events(state, items, session, terminal, final=True)
    assert state.completed == ["a.py::test_1"]
    assert coordinator._completed == 1

    coordinator._reconcile_worker(state, items, session, terminal, None)
    assert session.testsfailed > 0


def test_terminal_reporter_restored_when_monitoring_raises(tmp_path: Path) -> None:
    coordinator, state, session, items = _make_harness(tmp_path, ["a.py::test_1"])
    terminal_reporter = Mock()
    terminal_reporter.showfspath = True
    session.config.pluginmanager.get_plugin.return_value = terminal_reporter

    workers = [(0, state.process, state.result_path, state.output_path)]
    with (
        patch.object(coordinator, "_read_worker_events", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError, match="boom"),
    ):
        coordinator._monitor(workers, items, session, assigned_by_worker={0: ["a.py::test_1"]})

    assert terminal_reporter.showfspath is True


def test_keyboard_interrupt_terminates_workers_and_writes_stop_file(tmp_path: Path) -> None:
    coordinator, state, session, items = _make_harness(tmp_path, ["a.py::test_1"])
    state.process.is_alive.return_value = True
    session.config.pluginmanager.get_plugin.return_value = None

    workers = [(0, state.process, state.result_path, state.output_path)]
    with (
        patch.object(coordinator, "_read_worker_events", side_effect=KeyboardInterrupt()),
        pytest.raises(KeyboardInterrupt),
    ):
        coordinator._monitor(workers, items, session, assigned_by_worker={0: ["a.py::test_1"]})

    assert (tmp_path / "stop").exists()
    state.process.terminate.assert_called()



@pytest.mark.parametrize(
    ("suffix", "diagnostic"),
    [
        (b"", None),
        (b"not-json\n", "malformed JSON"),
        (b"[]\n", "non-object JSON event from worker 0: list"),
        (b"\n", "empty JSONL line"),
        (b'{"v":1', "truncated JSONL"),
        (b"\xff", "truncated JSONL"),
        (b'{"v":2,"type":"warning"}\n', "unsupported protocol version"),
        (b'{"v":1,"type":"unknown"}\n', "event 'unknown' received after session_finish"),
    ],
)
def test_real_worker_stream_final_read_rejects_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    suffix: bytes, diagnostic: str | None,
) -> None:
    test_file = tmp_path / "test_real_worker.py"
    test_file.write_text("def test_ok():\n    assert True\n")
    monkeypatch.delenv("_PYTEST_PARALLEL_WORKER", raising=False)
    monkeypatch.delenv("PYTEST_PARALLEL_WORKER_ID", raising=False)
    original = Coordinator._read_worker_events
    injected = False

    def read(self: Any, state: Any, items: Any, session: Any, terminal: Any, *, final: bool) -> None:
        nonlocal injected
        if final:
            assert not state.process.is_alive()
            with state.result_path.open("ab") as stream:
                stream.write(suffix)
            injected = True
        original(self, state, items, session, terminal, final=final)

    monkeypatch.setattr(Coordinator, "_read_worker_events", read)
    rc = pytest.main([str(test_file), "-j", "1", "-q", "--import-mode=importlib"])
    output = capsys.readouterr().out
    assert injected, output
    if diagnostic is None:
        assert rc == pytest.ExitCode.OK, output
        assert "1 passed" in output
    else:
        assert rc == pytest.ExitCode.TESTS_FAILED, output
        assert diagnostic in output


def test_real_worker_invalid_utf8_inside_json_event_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    test_file = tmp_path / "test_real_worker.py"
    test_file.write_text("def test_ok():\n    assert True\n")
    monkeypatch.delenv("_PYTEST_PARALLEL_WORKER", raising=False)
    monkeypatch.delenv("PYTEST_PARALLEL_WORKER_ID", raising=False)
    original = Coordinator._read_worker_events

    def read(self: Any, state: Any, items: Any, session: Any, terminal: Any, *, final: bool) -> None:
        if final:
            assert not state.process.is_alive()
            data = state.result_path.read_bytes()
            assert data.startswith(b"{")
            state.result_path.write_bytes(b'{"extra":"\xff",' + data[1:])
            original(self, state, items, session, terminal, final=True)

    monkeypatch.setattr(Coordinator, "_read_worker_events", read)
    rc = pytest.main([str(test_file), "-j", "1", "-q", "--import-mode=importlib"])
    output = capsys.readouterr().out
    assert rc == pytest.ExitCode.TESTS_FAILED, output
    assert "invalid UTF-8" in output


@pytest.mark.parametrize(
    ("injected", "diagnostic"),
    [
        (b"not-json\n", "malformed JSON"),
        (b"\xff\n", "invalid UTF-8"),
        (b"\n", "empty JSONL line"),
        (b"[]\n", "non-object JSON"),
        (b'{"v":1,"type":"warning"}\n', "invalid warning event"),
        (b'{"v":1,"type":"unknown"}\n', "unknown event type"),
        (b'{"v":1,"type":"internal_error","excrepr":"injected fault"}\n', "injected fault"),
        (b'{"v":1,"type":"internal_error"}\n', "worker 0 internal error: worker internal error"),
    ],
)
def test_real_worker_stream_interleaved_errors_preserve_later_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    injected: bytes, diagnostic: str,
) -> None:
    test_file = tmp_path / "test_interleaved_worker.py"
    test_file.write_text("def test_ok():\n    assert True\n")
    monkeypatch.delenv("_PYTEST_PARALLEL_WORKER", raising=False)
    monkeypatch.delenv("PYTEST_PARALLEL_WORKER_ID", raising=False)
    original = Coordinator._read_worker_events

    def read(self: Any, state: Any, items: Any, session: Any, terminal: Any, *, final: bool) -> None:
        if final:
            data = state.result_path.read_bytes()
            first, rest = data.split(b"\n", 1)
            state.result_path.write_bytes(first + b"\n" + injected + rest)
            original(self, state, items, session, terminal, final=True)

    reports: list[tuple[str, str]] = []

    class Observer:
        def pytest_runtest_logreport(self, report: Any) -> None:
            reports.append((report.when, report.outcome))

    monkeypatch.setattr(Coordinator, "_read_worker_events", read)
    rc = pytest.main([str(test_file), "-j", "1", "-q", "--import-mode=importlib"], plugins=[Observer()])
    output = capsys.readouterr().out
    assert rc == pytest.ExitCode.TESTS_FAILED, output
    assert diagnostic in output
    assert ("call", "passed") in reports


def test_real_worker_stream_replays_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    test_file = tmp_path / "test_worker_warning.py"
    test_file.write_text("import warnings\ndef test_ok():\n    warnings.warn('worker warning witness', UserWarning)\n")
    monkeypatch.delenv("_PYTEST_PARALLEL_WORKER", raising=False)
    monkeypatch.delenv("PYTEST_PARALLEL_WORKER_ID", raising=False)
    rc = pytest.main([str(test_file), "-j", "1", "-q", "--import-mode=importlib"])
    output = capsys.readouterr().out
    assert rc == pytest.ExitCode.OK, output
    assert "worker warning witness" in output
    assert "1 passed" in output


def test_real_worker_stream_replays_collection_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    test_file = tmp_path / "test_worker_collect.py"
    test_file.write_text(
        "import os\n"
        "if os.getenv('_PYTEST_PARALLEL_WORKER'):\n    raise RuntimeError('worker collection witness')\n"
        "def test_ok():\n    assert True\n"
    )
    monkeypatch.delenv("_PYTEST_PARALLEL_WORKER", raising=False)
    monkeypatch.delenv("PYTEST_PARALLEL_WORKER_ID", raising=False)
    reports: list[str] = []

    class Observer:
        def pytest_collectreport(self, report: Any) -> None:
            if report.failed:
                reports.append(str(report.longrepr))

    rc = pytest.main([str(test_file), "-j", "1", "-q", "--import-mode=importlib"], plugins=[Observer()])
    output = capsys.readouterr().out
    assert rc == pytest.ExitCode.TESTS_FAILED, output
    assert any("worker collection witness" in report for report in reports), output


def test_complete_events_before_partial_line_are_not_replayed(tmp_path: Path) -> None:
    coordinator, state, session, items = _make_harness(tmp_path, ["a.py::test_1"])
    first = b'{"v":1,"type":"collection","nodeids":["a.py::test_1"]}\n'
    state.result_path.write_bytes(first + b'{"v":1,"type":"test_start",')
    coordinator._read_worker_events(state, items, session, Mock(), final=False)
    assert state.collection_verified
    assert state.offset == len(first)
    with state.result_path.open("ab") as stream:
        stream.write(b'"nodeid":"a.py::test_1"}\n')
    coordinator._read_worker_events(state, items, session, Mock(), final=False)
    assert state.current_test is not None
    assert state.current_test.nodeid == "a.py::test_1"
    assert not state.protocol_errors
    assert state.offset == state.result_path.stat().st_size


def test_real_worker_stream_forwards_uncaptured_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    test_file = tmp_path / "test_worker_stdout.py"
    test_file.write_text("def test_ok():\n    print('worker stdout witness')\n")
    monkeypatch.delenv("_PYTEST_PARALLEL_WORKER", raising=False)
    monkeypatch.delenv("PYTEST_PARALLEL_WORKER_ID", raising=False)
    rc = pytest.main([str(test_file), "-j", "1", "-q", "-s", "--import-mode=importlib"])
    output = capsys.readouterr().out
    assert rc == pytest.ExitCode.OK, output
    assert "worker stdout witness" in output
    assert "1 passed" in output


def test_missing_worker_stream_is_reported(tmp_path: Path) -> None:
    coordinator, state, session, items = _make_harness(tmp_path, ["a.py::test_1"])
    state.result_path.unlink()
    coordinator._read_worker_events(state, items, session, Mock(), final=True)
    assert state.protocol_errors == ["worker 0 result file is missing"]
    coordinator._reconcile_worker(state, items, session, Mock(), None)
    assert session.testsfailed > 0


def test_worker_report_observer_preserves_public_serialization_and_phases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "conftest.py").write_text(
        "import os, pytest\n"
        "@pytest.hookimpl(tryfirst=True)\n"
        "def pytest_report_to_serializable(config, report):\n"
        "    data = report._to_json()\n"
        "    data['$report_type'] = report.__class__.__name__\n"
        "    data['serialization_witness'] = os.getpid()\n"
        "    return data\n"
    )
    (tmp_path / "test_reports.py").write_text(
        "import pytest, warnings\n"
        "@pytest.fixture\n"
        "def phases(request):\n"
        "    print('setup witness')\n"
        "    request.node.user_properties.append(('case', 'value'))\n"
        "    yield\n"
        "    print('teardown witness')\n"
        "def test_failure(phases):\n"
        "    print('call witness')\n"
        "    warnings.warn('report warning witness', UserWarning)\n"
        "    assert 1 == 2, 'report failure witness'\n"
        "@pytest.mark.xfail(reason='expected witness')\n"
        "def test_expected():\n"
        "    assert False\n"
    )
    monkeypatch.delenv("_PYTEST_PARALLEL_WORKER", raising=False)
    monkeypatch.delenv("PYTEST_PARALLEL_WORKER_ID", raising=False)
    reports: list[Any] = []
    warning_messages: list[str] = []

    class Observer:
        def pytest_runtest_logreport(self, report: Any) -> None:
            reports.append(report)

        def pytest_warning_recorded(self, warning_message: Any, when: str) -> None:
            if when == "runtest":
                warning_messages.append(str(warning_message.message))

    rc = pytest.main([str(tmp_path), "-j", "1", "-q", "--import-mode=importlib"], plugins=[Observer()])
    output = capsys.readouterr().out
    assert rc == pytest.ExitCode.TESTS_FAILED, output
    failure = [r for r in reports if r.nodeid.endswith("::test_failure")]
    assert [(r.when, r.outcome) for r in failure] == [("setup", "passed"), ("call", "failed"), ("teardown", "passed")]
    assert all(r.serialization_witness != os.getpid() for r in failure)
    assert all(("case", "value") in r.user_properties for r in failure)
    assert "report failure witness" in str(failure[1].longrepr)
    assert "setup witness" in failure[0].capstdout
    assert "call witness" in failure[1].capstdout
    assert "teardown witness" in failure[2].capstdout
    expected = [r for r in reports if r.nodeid.endswith("::test_expected") and r.when == "call"]
    assert len(expected) == 1
    assert expected[0].outcome == "skipped"
    assert expected[0].wasxfail == "expected witness"
    assert "report warning witness" in warning_messages


def test_worker_report_observer_jsonl_from_pytest_hooks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    from pytest_parallel.worker import ResultReporter

    stream = tmp_path / "events.jsonl"
    (tmp_path / "conftest.py").write_text(
        "import pytest\n"
        "@pytest.hookimpl(tryfirst=True)\n"
        "def pytest_report_to_serializable(config, report):\n"
        "    assert config.rootpath is not None\n"
        "    if report.nodeid.endswith('::test_bad'):\n"
        "        data = report._to_json()\n"
        "        data['$report_type'] = report.__class__.__name__\n"
        "        data['custom_witness'] = 'from public hook'\n"
        "        return data\n"
        "    if report.nodeid.endswith('::test_xfail'):\n"
        "        return 'unsupported result'\n"
    )
    suite = tmp_path / "test_direct.py"
    suite.write_text(
        "import pytest\n"
        "def test_bad():\n    print('captured witness')\n    assert False, 'failure witness'\n"
        "@pytest.mark.xfail(reason='xfail witness')\n"
        "def test_xfail():\n    assert False\n"
    )
    rc = pytest.main([str(suite), "-p", "no:parallel", "-q", "--import-mode=importlib"], plugins=[ResultReporter(str(stream))])
    capsys.readouterr()
    assert rc == pytest.ExitCode.TESTS_FAILED
    events = [json.loads(line) for line in stream.read_text().splitlines()]
    reports = [e for e in events if e["type"] == "report" and e["nodeid"].endswith("::test_bad")]
    assert [(e["when"], e["outcome"]) for e in reports] == [("setup", "passed"), ("call", "failed"), ("teardown", "passed")]
    call = reports[1]
    assert call["duration"] >= 0
    assert "failure witness" in call["longrepr"]
    assert call["report"]["$report_type"] == "TestReport"
    assert call["report"]["custom_witness"] == "from public hook"
    assert reports[0]["longrepr"] is None
    assert any("captured witness" in section[1] for section in call["report"]["sections"])
    xfail = [e for e in events if e["type"] == "report" and e["nodeid"].endswith("::test_xfail") and e["when"] == "call"]
    assert len(xfail) == 1
    assert xfail[0]["outcome"] == "skipped"
    assert xfail[0]["wasxfail"] == "xfail witness"
    assert xfail[0]["report"]["$report_type"] == "TestReport"
    assert not [e for e in events if e["type"] == "collect_report"]

    bad = tmp_path / "test_collect_error.py"
    bad.write_text("raise RuntimeError('collection witness')\n")
    stream.unlink()
    rc = pytest.main([str(bad), "-p", "no:parallel", "-q", "--import-mode=importlib"], plugins=[ResultReporter(str(stream))])
    capsys.readouterr()
    assert rc == pytest.ExitCode.INTERRUPTED
    events = [json.loads(line) for line in stream.read_text().splitlines()]
    errors = [e for e in events if e["type"] == "collect_report"]
    assert len(errors) == 1
    assert errors[0]["nodeid"].endswith("test_collect_error.py")
    assert errors[0]["outcome"] == "failed"
    assert "collection witness" in errors[0]["longrepr"]
    assert errors[0]["report"]["$report_type"] == "CollectReport"
