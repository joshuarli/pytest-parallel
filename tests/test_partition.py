from __future__ import annotations

from typing import Any, cast
from unittest.mock import Mock, patch

from pytest_parallel.coordinator import Coordinator, _multiprocessing_context


def _make_item(nodeid: str) -> Mock:
    item = Mock()
    item.nodeid = nodeid
    item.location = (nodeid.split("::")[0], None, nodeid)
    return item


def test_round_robin_preserves_file_order():
    items = [
        _make_item("a.py::test_1"),
        _make_item("a.py::test_2"),
        _make_item("b.py::test_1"),
        _make_item("c.py::test_1"),
        _make_item("c.py::test_2"),
        _make_item("d.py::test_1"),
        _make_item("e.py::test_1"),
    ]

    buckets = Coordinator._partition(items, 3)

    assert [item.nodeid for item in buckets[0]] == ["a.py::test_1", "a.py::test_2", "d.py::test_1"]
    assert [item.nodeid for item in buckets[1]] == ["b.py::test_1", "e.py::test_1"]
    assert [item.nodeid for item in buckets[2]] == ["c.py::test_1", "c.py::test_2"]


def test_preserves_test_order_within_file():
    items = [
        _make_item("f.py::TestA::test_3"),
        _make_item("f.py::TestA::test_1"),
        _make_item("f.py::TestB::test_2"),
    ]

    buckets = Coordinator._partition(items, 2)

    assert [item.nodeid for item in buckets[0]] == [
        "f.py::TestA::test_3",
        "f.py::TestA::test_1",
        "f.py::TestB::test_2",
    ]
    assert buckets[1] == []


def test_single_worker_gets_everything():
    items = [_make_item(f"f{i}.py::test") for i in range(5)]

    buckets = Coordinator._partition(items, 1)

    assert len(buckets) == 1
    assert len(buckets[0]) == 5


def test_more_workers_than_files():
    items = [_make_item("a.py::test_1"), _make_item("b.py::test_1")]

    buckets = Coordinator._partition(items, 4)

    assert [item.nodeid for item in buckets[0]] == ["a.py::test_1"]
    assert [item.nodeid for item in buckets[1]] == ["b.py::test_1"]
    assert buckets[2] == []
    assert buckets[3] == []


def test_spawn_uses_multiprocessing_context(tmp_path):
    config = Mock()
    config.hook.pytest_parallel_worker_env = Mock()
    config.known_args_namespace.file_or_dir = []
    config.rootpath = tmp_path
    coordinator = Coordinator(cast(Any, config), 1)
    coordinator._work_dir = tmp_path
    test_list = tmp_path / "tests.txt"
    test_list.write_text("tests/test_example.py::test_ok\n")

    context = Mock()
    process = Mock()
    context.Process.return_value = process
    with patch("pytest_parallel.coordinator._multiprocessing_context", return_value=context):
        workers = coordinator._spawn([(0, test_list)])

    env = context.Process.call_args.kwargs["args"][0]
    assert env["_PYTEST_PARALLEL_ROOTDIR"] == str(tmp_path)
    assert env["_PYTEST_PARALLEL_OUTPUT"] == str(tmp_path / "worker_0_output.txt")
    process.start.assert_called_once_with()
    assert workers == [(0, process, tmp_path / "worker_0_results.jsonl", tmp_path / "worker_0_output.txt")]


def test_multiprocessing_context_uses_spawn_on_macos():
    with (
        patch("pytest_parallel.coordinator.sys.platform", "darwin"),
        patch("pytest_parallel.coordinator.multiprocessing.get_context") as get_context,
    ):
        _multiprocessing_context()

    get_context.assert_called_once_with("spawn")


def test_multiprocessing_context_uses_fork_on_linux():
    with (
        patch("pytest_parallel.coordinator.sys.platform", "linux"),
        patch("pytest_parallel.coordinator.multiprocessing.get_context") as get_context,
    ):
        _multiprocessing_context()

    get_context.assert_called_once_with("fork")
