from __future__ import annotations

from pytest_parallel import _parse_numprocesses


def test_auto_uses_cpu_count(monkeypatch):
    monkeypatch.setattr("pytest_parallel.os.cpu_count", lambda: 12)

    assert _parse_numprocesses("auto") == 12


def test_auto_falls_back_to_one_worker(monkeypatch):
    monkeypatch.setattr("pytest_parallel.os.cpu_count", lambda: None)

    assert _parse_numprocesses("auto") == 1


def test_numeric_worker_count():
    assert _parse_numprocesses("4") == 4
