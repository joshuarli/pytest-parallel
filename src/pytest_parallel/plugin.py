from __future__ import annotations

import math
import os
import re
from typing import Literal

import pytest

__version__ = "0.2.0"

_DEFAULT_MAX_WORKERS = 64
_RAMP_PATTERN = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[+-]?(?:inf|infinity|nan))\s*([smhSMH]?)$")

BalanceStrategy = Literal["round-robin", "count"]
StartMethod = Literal["auto", "fork", "spawn", "forkserver"]


class ParallelHookSpec:
    @pytest.hookspec(firstresult=True)
    def pytest_parallel_max_workers(self) -> int | None:
        """Return the maximum worker count allowed for this test environment."""

    @pytest.hookspec
    def pytest_parallel_pre_spawn(self, config: pytest.Config, num_workers: int) -> None:
        """Run once after collection and before worker processes are spawned."""

    @pytest.hookspec
    def pytest_parallel_worker_env(self, env: dict[str, str], worker_id: int) -> None:
        """Mutate a worker subprocess environment."""


def pytest_addhooks(pluginmanager: pytest.PytestPluginManager) -> None:
    pluginmanager.add_hookspecs(ParallelHookSpec)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "enable_network: allow network access during this test")
    config.addinivalue_line(
        "markers",
        "parallel_group(name, ...): assign related tests and their files to the same parallel worker",
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("parallel", "static parallel test execution")
    group._addoption(
        "-j",
        "--jobs",
        default="auto",
        dest="parallel_jobs",
        help="Run tests across N worker processes. Defaults to 'auto'.",
    )
    group._addoption(
        "--serial",
        action="store_true",
        default=False,
        dest="parallel_serial",
        help="Disable pytest-parallel and use pytest's standard serial runner.",
    )
    group._addoption(
        "--ramp",
        default=None,
        dest="parallel_ramp",
        help="Stagger worker first-test execution over DURATION (e.g. 5, 5s, 1m, 0.5h).",
    )
    group._addoption(
        "--parallel-balance",
        default="round-robin",
        dest="parallel_balance",
        help="File sharding strategy: 'round-robin' (default) or 'count'.",
    )
    group._addoption(
        "--parallel-start-method",
        default="auto",
        dest="parallel_start_method",
        help="Multiprocessing start method: 'auto' (default), 'fork', 'spawn', or 'forkserver'.",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_runtestloop(session: pytest.Session) -> bool | None:
    if session.config.getoption("parallel_serial", default=False) or os.environ.get("_PYTEST_PARALLEL_WORKER"):
        return None

    requested = _parse_jobs(session.config.getoption("parallel_jobs", default="0"))
    ramp = _parse_ramp(session.config.getoption("parallel_ramp", default=None))
    balance = _parse_balance(session.config.getoption("parallel_balance", default="round-robin"))
    start_method = _parse_start_method(session.config.getoption("parallel_start_method", default="auto"))

    if requested <= 0:
        return None

    if getattr(session.config.option, "usepdb", False) or getattr(session.config.option, "trace", False):
        raise pytest.UsageError(
            "pytest-parallel does not support interactive debugging (--pdb or --trace) in parallel workers; "
            "pass --serial to debug interactively."
        )

    if session.testsfailed and not getattr(session.config.option, "continue_on_collection_errors", False):
        raise session.Interrupted(
            f"{session.testsfailed} error{'s' if session.testsfailed != 1 else ''} during collection"
        )

    if getattr(session.config.option, "collectonly", False):
        return True

    if session.shouldfail:
        raise session.Failed(session.shouldfail)
    if session.shouldstop:
        raise session.Interrupted(session.shouldstop)

    from .coordinator import Coordinator

    return Coordinator(
        session.config,
        requested,
        ramp=ramp,
        balance=balance,
        start_method=start_method,
    ).run(session)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None):
    if item.get_closest_marker("enable_network") is not None:
        yield
        return

    from .network import network_blocked

    with network_blocked():
        yield


def _parse_jobs(value: object) -> int:
    if isinstance(value, bool):
        raise pytest.UsageError(f"Invalid --jobs value: {value!r}")
    if isinstance(value, int):
        if value < 0:
            raise pytest.UsageError(f"--jobs must be >= 0, got {value}")
        return value
    text = str(value).strip().lower()
    if text == "auto":
        return _auto_cpu_count()
    try:
        parsed = int(text)
    except ValueError as exc:
        raise pytest.UsageError(
            f"Invalid --jobs value {value!r}; expected 'auto' or a non-negative integer."
        ) from exc
    if parsed < 0:
        raise pytest.UsageError(f"--jobs must be >= 0, got {parsed}")
    return parsed


def _auto_cpu_count() -> int:
    process_count = getattr(os, "process_cpu_count", None)
    count = process_count() if callable(process_count) else None
    if count is None:
        count = os.cpu_count()
    return count if isinstance(count, int) and count > 0 else 1


def _parse_ramp(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        raise pytest.UsageError(f"Invalid --ramp value: {value!r}")
    if isinstance(value, int | float):
        seconds = float(value)
        if not math.isfinite(seconds) or seconds < 0.0:
            raise pytest.UsageError(f"--ramp must be a finite non-negative duration, got {value!r}")
        return seconds

    text = str(value).strip()
    if not text:
        raise pytest.UsageError("--ramp duration cannot be empty")
    match = _RAMP_PATTERN.match(text)
    if match is None:
        raise pytest.UsageError(
            f"Invalid --ramp value {value!r}; expected a non-negative number with optional s, m, or h suffix."
        )
    number_text, unit = match.groups()
    try:
        amount = float(number_text)
    except ValueError as exc:
        raise pytest.UsageError(f"Invalid --ramp value {value!r}") from exc
    if not math.isfinite(amount) or amount < 0.0:
        raise pytest.UsageError(f"--ramp must be a finite non-negative duration, got {value!r}")
    multipliers = {"": 1.0, "s": 1.0, "m": 60.0, "h": 3600.0}
    seconds = amount * multipliers[unit.lower()]
    if not math.isfinite(seconds):
        raise pytest.UsageError(f"--ramp duration overflow: {value!r}")
    return seconds


def _parse_balance(value: object) -> BalanceStrategy:
    text = str(value).strip().lower()
    if text == "round-robin":
        return "round-robin"
    if text == "count":
        return "count"
    raise pytest.UsageError(
        f"Invalid --parallel-balance value {value!r}; expected 'round-robin' or 'count'."
    )


def _parse_start_method(value: object) -> StartMethod:
    text = str(value).strip().lower()
    if text == "auto":
        return "auto"
    if text == "fork":
        return "fork"
    if text == "spawn":
        return "spawn"
    if text == "forkserver":
        return "forkserver"
    raise pytest.UsageError(
        f"Invalid --parallel-start-method value {value!r}; expected 'auto', 'fork', 'spawn', or 'forkserver'."
    )
