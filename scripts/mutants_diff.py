from __future__ import annotations

import argparse
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
from collections import Counter
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from mutants_scheduling import EQUIVALENT, SOURCE_SHA256, run

ROOT = Path(__file__).resolve().parent.parent
SOURCE = PurePosixPath("src/pytest_parallel")
CONFIGURATION = frozenset({".envrc", ".gitignore", "Dockerfile", "Makefile", "pyproject.toml", "uv.lock"})
DOCUMENTATION = frozenset({"AGENTS.md", "CHANGELOG.md", "LICENSE", "README.md", "TODO.md", "TODO-DESLOP.md"})
COORDINATOR_PLAN = "pytest_parallel.coordinator.xǁCoordinatorǁ_build_units__mutmut_*"
COORDINATOR_PINS = (
    "pytest_parallel.coordinator.xǁCoordinatorǁ_resolve_pins__mutmut_*",
    "pytest_parallel.coordinator.xǁCoordinatorǁ_resolve_max_workers__mutmut_*",
)
COORDINATOR_PLAN_TESTS = [
    "tests/test_campaign.py", "-k", "missing_hooks or file_hooks_group or file_hook_rejects",
]
COORDINATOR_PINS_TESTS = [
    "tests/test_campaign.py", "-k", "missing_hooks or shard_pin_votes or worker_limit_hook",
]
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
        "worker_report_observer_jsonl_from_pytest_hooks or worker_report_observer_keeps_missing_collection_detail_null",
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


def inventory(directory: Path, source: str, selectors: tuple[str, ...]) -> dict[str, int | None]:
    meta = json.loads((directory / "mutants" / f"{source}.meta").read_text(encoding="utf-8"))
    available = meta.get("exit_code_by_key") if isinstance(meta, dict) else None
    if not isinstance(available, dict):
        raise ValueError(f"missing mutation inventory for {source}")
    selection: dict[str, int | None] = {}
    for pattern in selectors:
        matches = {name: status for name, status in available.items() if fnmatchcase(name, pattern)}
        if not matches:
            raise ValueError(f"empty mutation selection for {pattern}")
        selection.update(matches)
    if any(value is not None and type(value) is not int for value in selection.values()):
        raise ValueError(f"malformed mutation outcomes for {source}")
    return selection


def results(
    mutmut: str,
    directory: Path,
    env: dict[str, str],
    source: str,
    selectors: tuple[str, ...],
) -> dict[str, str]:
    selection = inventory(directory, source, selectors)
    observed = {}
    for line in run([mutmut, "results", "--all", "true"], directory, env, capture=True).splitlines():
        name, separator, status = line.strip().partition(": ")
        if separator and name in selection:
            if name in observed:
                raise ValueError(f"duplicate result for {name}")
            observed[name] = status
    if observed.keys() != selection.keys():
        raise ValueError(f"missing results for {source}: {sorted(selection.keys() - observed.keys())}")
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
    mutmut: str, directory: Path, source: str, selectors: tuple[str, ...], tests: list[str], scratch: Path,
) -> bool:
    env = dict(os.environ, PYTHONPATH=str(directory / "src"), TMPDIR=str(scratch))
    env.pop("MUTANT_UNDER_TEST", None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    config = directory / "pyproject.toml"
    contents = config.read_text(encoding="utf-8") + (
        '\n[tool.mutmut]\nsource_paths = ["src"]\n'
        f"only_mutate = {json.dumps([source])}\n"
        'pytest_add_cli_args = ["-p", "no:parallel"]\n'
        f"pytest_add_cli_args_test_selection = {json.dumps(tests)}\n"
    )
    config.write_text(contents, encoding="utf-8")
    command = [mutmut, "run", "--max-children", "1"]
    try:
        run([*command, *selectors], directory, env)
    except subprocess.TimeoutExpired:
        try:
            partial = Counter(inventory(directory, source, selectors).values())
        except (OSError, ValueError) as error:
            print(f"mutation inventory unavailable at timeout for {source}: {error}", flush=True)
        else:
            labels = {None: "unrun", 0: "survived", 1: "killed"}
            outcome_counts = {labels.get(status, f"code {status}"): count for status, count in partial.items()}
            print(f"partial mutation outcomes for {source}: {outcome_counts}", flush=True)
        raise
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


def mutation_jobs(
    selectors: dict[str, tuple[str, ...]],
) -> dict[str, tuple[str, tuple[str, ...], list[str]]]:
    jobs = {}
    for source, patterns in selectors.items():
        shard = PurePosixPath(source).stem
        tests = TESTS[source]
        if COORDINATOR_PLAN in patterns:
            jobs["coordinator-plan"] = (source, (COORDINATOR_PLAN,), COORDINATOR_PLAN_TESTS)
            jobs["coordinator-pins"] = (source, COORDINATOR_PINS, COORDINATOR_PINS_TESTS)
            patterns = tuple(pattern for pattern in patterns if pattern not in (COORDINATOR_PLAN, *COORDINATOR_PINS))
        elif shard == "coordinator":
            test_file, _, test_names = COORDINATOR_PLAN_TESTS
            tests = [tests[0], test_file, "-k", f"{tests[-1]} or {test_names} or {COORDINATOR_PINS_TESTS[-1]}"]
        if patterns:
            jobs[shard] = (source, patterns, tests)
    return jobs


def run_selection(jobs: dict[str, tuple[str, tuple[str, ...], list[str]]], revision: str) -> bool:
    scratch = ROOT / ".work" / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    mutmut = os.environ.get("MUTMUT", "mutmut")
    passed = True
    with tempfile.TemporaryDirectory(prefix="mutants-diff-", dir=scratch) as temp:
        directory = Path(temp)
        snapshot(revision, directory)
        if "3.8.1" not in run([mutmut, "--version"], directory, dict(os.environ), capture=True).split():
            raise ValueError("mutmut 3.8.1 is required")
        for shard, (source, patterns, tests) in jobs.items():
            print(f"running {shard}", flush=True)
            candidate = directory / "candidate"
            candidate.mkdir()
            for name in ("src", "tests"):
                shutil.copytree(directory / name, candidate / name)
            for name in ("pyproject.toml", "uv.lock"):
                shutil.copyfile(directory / name, candidate / name)
            passed = run_scope(mutmut, candidate, source, patterns, tests, scratch) and passed
            shutil.rmtree(candidate)
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Select and run the serial mutation gate")
    parser.add_argument("base")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true")
    mode.add_argument(
        "--shard", choices=sorted(["coordinator-pins", "coordinator-plan", *(PurePosixPath(path).stem for path in TESTS)]),
    )
    args = parser.parse_args()
    revision = None
    if not args.plan:
        if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT):
            raise ValueError("commit the selected changes before running the mutation gate")
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    selection = select_mutations(changed_paths(args.base, revision=revision))
    selectors = selection.selectors()
    print(json.dumps({
        "changes": selection.classes,
        "production": selection.production,
        "protected": selection.protected,
        "selectors": selectors,
    }, indent=2), flush=True)
    if not selectors:
        print("no relevant changes")
    elif revision is not None:
        if unsupported := set(selectors) - TESTS.keys():
            raise ValueError(f"missing mutation witness selection: {sorted(unsupported)}")
        jobs = mutation_jobs(selectors)
        if args.shard:
            jobs = {name: job for name, job in jobs.items() if name == args.shard}
        if not jobs:
            print(f"no mutations selected for shard {args.shard}")
        elif not run_selection(jobs, revision):
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
