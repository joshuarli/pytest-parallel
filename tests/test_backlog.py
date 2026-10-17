from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from pytest_parallel.coordinator import Coordinator
from pytest_parallel.network import network_blocked


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("_PYTEST_PARALLEL_WORKER", None)
    env.pop("PYTEST_PARALLEL_WORKER_ID", None)
    return env


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=_clean_env(),
    )


def test_network_hot_path_caches_peer_and_still_blocks_external() -> None:
    import socket

    with network_blocked():
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with socket.socket() as client:
                client.connect(listener.getsockname())
                peer, _ = listener.accept()
                with peer:
                    for _ in range(20):
                        client.sendall(b"ok")
                        assert peer.recv(2) == b"ok"
        with socket.socket() as client, pytest.raises(PermissionError, match="outside loopback"):
            client.connect(("192.0.2.1", 80))
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.connect(("127.0.0.1", 9))
            client.send(b"x")
            with pytest.raises(PermissionError, match="outside loopback"):
                client.sendto(b"x", ("192.0.2.1", 9))


def test_connected_unix_socket_sendmsg_is_allowed() -> None:
    import socket

    address = f"/tmp/pp-{os.getpid()}.sock"
    try:
        os.unlink(address)
    except OSError:
        pass
    try:
        with network_blocked(), socket.socket(socket.AF_UNIX) as listener:
            listener.bind(address)
            listener.listen(1)
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(address)
                peer, _ = listener.accept()
                with peer:
                    client.sendmsg([b"ok"])
                    assert peer.recv(2) == b"ok"
    finally:
        try:
            os.unlink(address)
        except OSError:
            pass


def test_forwarded_args_preserves_plugin_option_value_matching_positional(tmp_path: Path) -> None:
    (tmp_path / "test_a.py").write_text("def test_a():\n assert True\n")
    (tmp_path / "conftest.py").write_text(
        "def pytest_addoption(parser):\n"
        "    parser.addoption('--cov-out', default=None)\n"
        "def pytest_configure(config):\n"
        "    assert config.option.cov_out == 'tests'\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_b.py").write_text("def test_b():\n assert True\n")
    res = _run(["tests", "--cov-out", "tests", "-j", "1", "-q"], tmp_path)
    assert res.returncode == 0, res.stdout
    assert "1 passed" in res.stdout


def test_coordinator_work_dir_is_created_under_explicit_basetemp(tmp_path: Path) -> None:
    base = tmp_path / "base"
    config = SimpleNamespace(option=SimpleNamespace(basetemp=str(base)), rootpath=tmp_path)
    work = Coordinator(cast(Any, config), 1)._ensure_work_dir()
    assert work.parent == base
    assert work.name.startswith("pytest_parallel_")


def test_work_dir_inside_explicit_basetemp(tmp_path: Path) -> None:
    base = tmp_path / "base"
    (tmp_path / "test_a.py").write_text("def test_a(tmp_path):\n (tmp_path / 'x').write_text('1')\n assert True\n")
    res = _run([str(tmp_path), "-j", "1", "-q", f"--basetemp={base}"], tmp_path)
    assert res.returncode == 0, res.stdout
    assert (base / "worker-0").exists()


def test_worker_native_fd_output_goes_to_worker_output(tmp_path: Path) -> None:
    (tmp_path / "test_native.py").write_text(
        "import os\n"
        "def test_native():\n"
        "    os.write(1, b'NATIVE_FD_MARKER\\n')\n"
        "    assert True\n"
    )
    res = _run([str(tmp_path), "-j", "1", "-q", "-s"], tmp_path)
    assert res.returncode == 0, res.stdout
    assert "NATIVE_FD_MARKER" in res.stdout


def test_custom_warning_constructor_fallback(tmp_path: Path) -> None:
    (tmp_path / "test_warn.py").write_text(
        "import warnings\n"
        "class MultiArgWarning(UserWarning):\n"
        "    def __init__(self, code, msg):\n"
        "        super().__init__(msg)\n"
        "        self.code = code\n"
        "def test_warns():\n"
        "    warnings.warn(MultiArgWarning(7, 'multi-arg warning'))\n"
        "    assert True\n"
    )
    res = _run([str(tmp_path), "-j", "1", "-q"], tmp_path)
    assert res.returncode == 0, res.stdout
    assert "1 passed" in res.stdout


def test_sigterm_reaps_worker_and_removes_work_dir(tmp_path: Path) -> None:
    suite = tmp_path / "suite"
    suite.mkdir()
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    ready = tmp_path / "ready.txt"
    pid_file = tmp_path / "worker_pid.txt"
    (suite / "test_hang.py").write_text(
        "import os, time\n"
        "from pathlib import Path\n"
        f"READY = Path({str(ready)!r})\n"
        f"PID = Path({str(pid_file)!r})\n"
        "def test_sleep():\n"
        "    if os.environ.get('_PYTEST_PARALLEL_WORKER') == '1':\n"
        "        PID.write_text(str(os.getpid()))\n"
        "        READY.write_text('1')\n"
        "        time.sleep(10.0)\n"
    )
    env = _clean_env()
    env["TMPDIR"] = str(scratch)
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", str(suite), "-j", "1", "-q"],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    deadline = time.monotonic() + 8.0
    while not ready.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert ready.exists(), proc.communicate(timeout=1)[0] if proc.poll() is not None else "worker did not start"
    proc.send_signal(signal.SIGTERM)
    stdout, _ = proc.communicate(timeout=8.0)
    assert proc.returncode != 0, stdout
    worker_pid = int(pid_file.read_text().strip())
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            os.kill(worker_pid, 0)
        except OSError:
            break
        time.sleep(0.02)
    else:
        raise AssertionError(f"worker {worker_pid} still alive")
    assert list(scratch.glob("pytest_parallel_*")) == []
