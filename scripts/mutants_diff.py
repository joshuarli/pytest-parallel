from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from mutants_scheduling import EQUIVALENT, SOURCE_SHA256, run

ROOT = Path(__file__).resolve().parent.parent
SOURCE = PurePosixPath("src/pytest_parallel")
CONFIGURATION = frozenset({".envrc", ".gitignore", "Dockerfile", "Makefile", "pyproject.toml", "uv.lock"})
DOCUMENTATION = frozenset({"AGENTS.md", "CHANGELOG.md", "LICENSE", "README.md", "TODO.md", "TODO-DESLOP.md"})
PROTECTED_FUNCTIONS = {
    "src/pytest_parallel/coordinator.py": (
        "xǁCoordinatorǁ_build_units",
        "xǁCoordinatorǁ_resolve_pins",
        "xǁCoordinatorǁ_resolve_max_workers",
        "xǁCoordinatorǁ_spawn",
        "xǁCoordinatorǁ_monitor",
        "xǁCoordinatorǁ_terminate_live_workers",
        "xǁCoordinatorǁ_read_worker_events",
        "xǁCoordinatorǁ_process_worker_event",
    ),
    "src/pytest_parallel/network.py": (
        "x__targets_loopback",
        "x__is_loopback_host",
    ),
    "src/pytest_parallel/plugin.py": (
        "x__parse_plan",
        "x__parse_jobs",
        "x__auto_cpu_count",
        "x__parse_ramp",
        "x__parse_balance",
        "x__parse_start_method",
    ),
    "src/pytest_parallel/worker.py": (
        "xǁResultReporterǁ_serialize_report",
        "xǁResultReporterǁpytest_collectreport",
        "xǁResultReporterǁpytest_runtest_logreport",
    ),
    "src/pytest_parallel/scheduling.py": (),
}
TESTS = {
    "src/pytest_parallel/coordinator.py": [
        "tests/test_p0_correctness.py", "-k",
        "protocol_validation or partial_jsonl or invalid_utf8 or real_worker_stream or incomplete_finish "
        "or missing_call_report or reconcile_rejects or complete_events_before_partial or missing_worker_stream",
    ],
    "src/pytest_parallel/network.py": [
        "tests/test_integration.py", "-k", "network_address_and_resolver_boundary",
    ],
    "src/pytest_parallel/plugin.py": [
        "tests/test_options.py", "-k",
        "not honors_python_cpu_count_override and not worker_count_capped and not invalid_max_workers_hook",
    ],
    "src/pytest_parallel/scheduling.py": ["tests/test_partition.py"],
    "src/pytest_parallel/worker.py": [
        "tests/test_p0_correctness.py", "-k",
        "worker_report_observer or worker_stream_replays_collection_failure or phase_outcomes_and_junitxml",
    ],
}
OPTIONS_SOURCE_SHA256 = "35a04145a9aee49dd0680ff7c5b1adf4ce3a325b9ad8ca637a3c7300cbb5f420"


@dataclass(frozen=True)
class MutationSelection:
    classes: dict[str, str]
    production: tuple[str, ...]
    protected: bool

    def selectors(self) -> dict[str, tuple[str, ...]]:
        scopes = dict(PROTECTED_FUNCTIONS) if self.protected else {}
        scopes.update((path, ()) for path in self.production)
        result = {}
        for path, functions in sorted(scopes.items()):
            module = ".".join(PurePosixPath(path).with_suffix("").parts[1:])
            result[path] = (
                tuple(f"{module}.{function}__mutmut_*" for function in functions)
                if functions
                else (f"{module}.*",)
            )
        return result


def changed_paths(base: str, root: Path = ROOT, revision: str | None = None) -> dict[str, str]:
    common = subprocess.check_output(
        ["git", "merge-base", "--", base, revision or "HEAD"], cwd=root, text=True,
    ).strip()
    endpoints = [common] if revision is None else [common, revision]
    raw = subprocess.check_output(
        ["git", "diff", "--name-status", "--no-renames", "-z", *endpoints, "--"], cwd=root,
    )
    fields = raw.decode("utf-8").split("\0")
    if fields[-1] != "" or len(fields) % 2 == 0:
        raise ValueError("malformed git change list")
    changes = {}
    for status, path in zip(fields[0:-1:2], fields[1:-1:2], strict=True):
        if status not in {"A", "M", "D"} or not path:
            raise ValueError(f"unsupported git change {status!r} for {path!r}")
        changes[path] = status
    if revision is None:
        untracked = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root,
        )
        for path in untracked.decode("utf-8").split("\0"):
            if path:
                changes[path] = "A"
    return changes


def select_mutations(changes: dict[str, str]) -> MutationSelection:
    classes: dict[str, str] = {}
    production: list[str] = []
    protected = False
    for path, status in sorted(changes.items()):
        source_file = PurePosixPath(path)
        if source_file.is_relative_to(SOURCE) and source_file.suffix == ".py":
            if status == "D":
                classes[path] = "deleted production"
                protected = True
            else:
                classes[path] = "production"
                production.append(path)
        elif path.startswith("tests/"):
            classes[path] = "test or fixture"
            protected = True
        elif path in CONFIGURATION or path.startswith((".github/", "scripts/", "benchmarks/")):
            classes[path] = "configuration"
            protected = True
        elif path in DOCUMENTATION or path.startswith("docs/"):
            classes[path] = "documentation"
        else:
            raise ValueError(f"unclassified change: {path}")
    return MutationSelection(classes, tuple(production), protected)


def snapshot(revision: str, destination: Path) -> None:
    archive = subprocess.check_output(
        ["git", "archive", revision, "src", "tests", "pyproject.toml", "uv.lock"], cwd=ROOT,
    )
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as files:
        members = files.getmembers()
        if any(not (member.isfile() or member.isdir()) for member in members):
            raise ValueError("mutation input archive contains a link or special file")
        files.extractall(destination, members=members, filter="data")


def results(
    mutmut: str,
    directory: Path,
    env: dict[str, str],
    source: str,
    selectors: tuple[str, ...],
) -> dict[str, str]:
    meta = json.loads((directory / "mutants" / f"{source}.meta").read_text(encoding="utf-8"))
    available = meta.get("exit_code_by_key") if isinstance(meta, dict) else None
    if not isinstance(available, dict):
        raise ValueError(f"missing mutation inventory for {source}")
    selection: set[str] = set()
    for pattern in selectors:
        matches = {name for name in available if fnmatchcase(name, pattern)}
        if not matches:
            raise ValueError(f"empty mutation selection for {pattern}")
        selection.update(matches)
    observed = {}
    for line in run([mutmut, "results", "--all", "true"], directory, env, capture=True).splitlines():
        name, separator, status = line.strip().partition(": ")
        if separator and name in selection:
            if name in observed:
                raise ValueError(f"duplicate result for {name}")
            observed[name] = status
    if set(observed) != selection:
        raise ValueError(f"missing results for {source}: {sorted(selection - observed.keys())}")
    return observed


def equivalent(source: str, snapshot_hash: str, name: str) -> bool:
    if source == "src/pytest_parallel/scheduling.py" and snapshot_hash == SOURCE_SHA256:
        return name.removeprefix("pytest_parallel.scheduling.") in EQUIVALENT
    return (
        source == "src/pytest_parallel/plugin.py"
        and snapshot_hash == OPTIONS_SOURCE_SHA256
        and name == "pytest_parallel.plugin.x__parse_ramp__mutmut_25"
    )


def run_scope(
    mutmut: str, directory: Path, source: str, selectors: tuple[str, ...], scratch: Path,
) -> bool:
    env = dict(os.environ, PYTHONPATH=str(directory / "src"), TMPDIR=str(scratch))
    env.pop("MUTANT_UNDER_TEST", None)
    config = directory / "pyproject.toml"
    contents = config.read_text(encoding="utf-8") + (
        '\n[tool.mutmut]\nsource_paths = ["src"]\n'
        f"only_mutate = {json.dumps([source])}\n"
        'pytest_add_cli_args = ["-p", "no:parallel"]\n'
        f"pytest_add_cli_args_test_selection = {json.dumps(TESTS[source])}\n"
    )
    config.write_text(contents, encoding="utf-8")
    command = [mutmut, "run", "--max-children", "1"]
    run([*command, *selectors], directory, env)
    observed = results(mutmut, directory, env, source, selectors)
    timeouts = tuple(name for name, status in observed.items() if status == "timeout")
    if timeouts:
        config.write_text(contents + "timeout_multiplier = 30.0\ntimeout_constant = 2.0\n", encoding="utf-8")
        run([*command, *timeouts], directory, env)
        for name, status in results(mutmut, directory, env, source, timeouts).items():
            observed[name] = "confirmed timeout" if status == "timeout" else status
    digest = hashlib.sha256((directory / source).read_bytes()).hexdigest()
    for name, status in sorted(observed.items()):
        if status == "survived" and equivalent(source, digest, name):
            observed[name] = "equivalent"
        print(f"{name}: {observed[name]}", flush=True)
    return all(status in {"killed", "confirmed timeout", "equivalent"} for status in observed.values())


def run_selection(selectors: dict[str, tuple[str, ...]], revision: str) -> bool:
    if unsupported := set(selectors) - TESTS.keys():
        raise ValueError(f"missing mutation witness selection: {sorted(unsupported)}")
    scratch = ROOT / ".work" / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    mutmut = os.environ.get("MUTMUT", "mutmut")
    passed = True
    with tempfile.TemporaryDirectory(prefix="mutants-diff-", dir=scratch) as temp:
        directory = Path(temp)
        snapshot(revision, directory)
        if "3.8.1" not in run([mutmut, "--version"], directory, dict(os.environ), capture=True).split():
            raise ValueError("mutmut 3.8.1 is required")
        for source, patterns in selectors.items():
            candidate = directory / "candidate"
            candidate.mkdir()
            for name in ("src", "tests"):
                shutil.copytree(directory / name, candidate / name)
            for name in ("pyproject.toml", "uv.lock"):
                shutil.copyfile(directory / name, candidate / name)
            passed = run_scope(mutmut, candidate, source, patterns, scratch) and passed
            shutil.rmtree(candidate)
    return passed


def main() -> None:
    plan = len(sys.argv) == 3 and sys.argv[1] == "--plan"
    if not plan and len(sys.argv) != 2:
        raise ValueError("usage: mutants_diff.py [--plan] BASE")
    revision = None
    if not plan:
        if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT):
            raise ValueError("commit the selected changes before running the mutation gate")
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    selection = select_mutations(changed_paths(sys.argv[-1], revision=revision))
    selectors = selection.selectors()
    print(json.dumps({
        "changes": selection.classes,
        "production": selection.production,
        "protected": selection.protected,
        "selectors": selectors,
    }, indent=2), flush=True)
    if not selectors:
        print("no relevant changes")
    elif revision is not None and not run_selection(selectors, revision):
        raise ValueError("mutation gate found a miss or unclassified result")


if __name__ == "__main__":
    def interrupt(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
        signal.signal(sig, interrupt)
    try:
        main()
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
