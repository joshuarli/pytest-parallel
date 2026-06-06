"""Small static-sharding parallel runner for pytest."""

from __future__ import annotations

import os

import pytest

_DEFAULT_MAX_WORKERS = 64


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


@pytest.hookimpl(tryfirst=True)
def pytest_runtestloop(session: pytest.Session) -> bool | None:
    if session.config.getoption("parallel_serial", default=False):
        return None

    requested = _parse_jobs(session.config.getoption("parallel_jobs", default="0"))
    if requested <= 0 or os.environ.get("_PYTEST_PARALLEL_WORKER"):
        return None

    from .coordinator import Coordinator

    return Coordinator(session.config, requested).run(session)


def _parse_jobs(value: object) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip().lower()
    if text == "auto":
        return os.cpu_count() or 1
    return int(text)
