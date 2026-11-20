from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("uniform", "uneven", "many_tiny", "single_file")


def main() -> None:
    parser = argparse.ArgumentParser(description="Select benchmark workloads; full is manual only")
    parser.add_argument("action", choices=("run", "check", "list"))
    parser.add_argument("--tier", choices=("edit", "change", "scenario", "full"), default="edit")
    parser.add_argument("--name", action="append", default=[])
    parser.add_argument("--area", choices=("harness", "scheduling"), action="append", default=[])
    parser.add_argument("--skip", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    opts = parser.parse_args()
    entries = {"harness": ("edit", "harness"), **dict.fromkeys(KINDS, ("change", "scheduling"))}
    levels = {"edit": 0, "change": 1, "scenario": 2, "full": 3}
    unknown = (set(opts.name) | set(opts.skip)) - entries.keys()
    if unknown:
        parser.error(f"unknown workload: {', '.join(sorted(unknown))}")
    selected = [name for name, (tier, area) in entries.items() if levels[tier] <= levels[opts.tier]
                and (not opts.name or name in opts.name) and (not opts.area or area in opts.area)
                and name not in opts.skip]
    if not selected:
        parser.error("selection matches no workloads")
    for name, (tier, area) in entries.items():
        print(f"{name}: {tier}, {area}, {'selected' if name in selected else 'excluded by selection'}")
    if opts.action == "list":
        return
    if not shutil.which("perf-gate-ready"):
        parser.error("perf-gate-ready missing; install it for host readiness information")
    probe = subprocess.run([sys.executable, "-c", "import pytest, pytest_parallel"], cwd=ROOT, check=False)
    if probe.returncode:
        parser.error("pytest or pytest-parallel missing; run uv sync --locked")
    if opts.action == "check":
        readiness = subprocess.run(["perf-gate-ready"], capture_output=True, text=True, check=False)
        print(f"host readiness exit {readiness.returncode}: {readiness.stdout}{readiness.stderr}".strip())
        return
    commands = {"harness": [sys.executable, "-m", "unittest", "discover", "-s", "benchmarks", "-p", "test_*.py"],
                **{k: [sys.executable, "benchmarks/run_benchmarks.py", "--trials", "3" if opts.tier in ("scenario", "full") else "1", "--workers", "2", "--kind", k] for k in KINDS}}
    for name in selected:
        print(f"{name}: {commands[name]}")
    if opts.dry_run:
        return
    out = ROOT / ".work" / "bench" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    out.mkdir(parents=True)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=False)
    summary = {"revision": revision.stdout.strip(), "dirty": bool(status.stdout),
               "excluded": {name: "selection" for name in entries if name not in selected}, "workloads": {}}
    failed = False
    for name in selected:
        ready = subprocess.run(["perf-gate-ready"], capture_output=True, text=True, check=False)
        start = time.monotonic()
        result = subprocess.run(commands[name], cwd=ROOT, capture_output=True, text=True, check=False)
        after = subprocess.run(["perf-gate-ready", "-1"], capture_output=True, text=True, check=False)
        (out / f"{name}.log").write_text(result.stdout + result.stderr)
        summary["workloads"][name] = {"exit": result.returncode, "seconds": time.monotonic() - start,
                         "timing": "host ready" if ready.returncode == after.returncode == 0 and not (ready.stdout + ready.stderr + after.stdout + after.stderr).strip() else "host readiness uncertain; no timing verdict",
                         "verdict": "completion only; no budget"}
        failed |= result.returncode != 0
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"results: {out}\n{json.dumps(summary, indent=2)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
