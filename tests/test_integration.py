from __future__ import annotations

import os
import subprocess
import sys

import pytest


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


@pytest.mark.parametrize("runner_args", [("--serial",), ("-j", "1")], ids=["serial", "parallel"])
def test_network_policy_and_loopback_exception(tmp_path, runner_args):
    test_file = tmp_path / "test_network_policy.py"
    test_file.write_text(
        """
import socket

import pytest

ORIGINAL_CONNECT = socket.socket.connect


def test_external_connection_is_blocked():
    with socket.socket() as client:
        with pytest.raises(PermissionError, match='outside loopback'):
            client.connect(('192.0.2.1', 80))


def test_external_hostname_lookup_is_blocked():
    with pytest.raises(PermissionError, match='outside loopback'):
        socket.getaddrinfo('example.com', 80)


def test_loopback_connection_is_allowed():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        with socket.socket() as client:
            client.connect(listener.getsockname())
            peer, _ = listener.accept()
            with peer:
                client.sendall(b'ok')
                assert peer.recv(2) == b'ok'


@pytest.mark.enable_network
def test_marker_allows_network():
    assert socket.socket.connect is ORIGINAL_CONNECT
"""
    )
    env = os.environ.copy()
    env.pop("_PYTEST_PARALLEL_WORKER", None)
    env.pop("PYTEST_PARALLEL_WORKER_ID", None)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "-q", *runner_args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )

    assert result.returncode == 0, result.stdout
    assert "4 passed" in result.stdout
