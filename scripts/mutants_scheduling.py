from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIX = 'pytest_parallel.scheduling.'
EQUIVALENT = {
    # Union root choices preserve components; merge emits original file order.
    'x_merge_units__mutmut_12', 'x_merge_units__mutmut_13', 'x_merge_units__mutmut_14',
    # Controller file ordinals and merged component indices have the same order.
    'x_assign_units__mutmut_11', 'x_assign_units__mutmut_13',
    # Round-robin never reads these loads; plan weights come from the buckets.
    'x_assign_units__mutmut_50', 'x_assign_units__mutmut_51',
    # Controller assignment and plan share the same unit objects, so lookup defaults are unreachable.
    'x_plan_dict__mutmut_51', 'x_plan_dict__mutmut_53', 'x_plan_dict__mutmut_55',
    'x_plan_dict__mutmut_56',
}
DEADLINE = time.monotonic() + 1200
SOURCE_SHA256 = '6d9cdc14ea746f02fbfe899eb040ebdd6e5caf7cf6527b450dbb3fd93acc5489'


def run(args: list[str], cwd: Path, env: dict[str, str], *, capture: bool = False) -> str:
    with subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE if capture else None,
                          text=True, start_new_session=True) as process:
        try:
            output, _ = process.communicate(timeout=max(0.01, DEADLINE - time.monotonic()))
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, args)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
    return output or ''


def main() -> None:
    if hashlib.sha256((ROOT / 'src/pytest_parallel/scheduling.py').read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Scheduling source changed; reclassify mutant identities before using this recipe')
    mutmut = os.environ.get('MUTMUT', 'mutmut')
    if '3.8.1' not in run([mutmut, '--version'], ROOT, os.environ, capture=True).split():
        raise ValueError('mutmut 3.8.1 is required')
    scratch = ROOT / '.work' / 'tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    copy = Path(tempfile.mkdtemp(prefix='mutants-scheduling-', dir=scratch))
    for name in ('src', 'tests'):
        shutil.copytree(ROOT / name, copy / name, ignore=shutil.ignore_patterns('__pycache__'))
    config = (ROOT / 'pyproject.toml').read_text() + (
        '\n[tool.mutmut]\nsource_paths = ["src"]\n'
        'pytest_add_cli_args = ["-p", "no:parallel"]\n'
        'pytest_add_cli_args_test_selection = ["tests/test_partition.py"]\n'
    )
    (copy / 'pyproject.toml').write_text(config)
    env = dict(os.environ, PYTHONPATH=str(copy / 'src'), TMPDIR=str(scratch))
    print(f'Mutation workspace: {copy}', flush=True)
    run([mutmut, 'run', '--max-children', '1', PREFIX + '*'], copy, env)
    results = run([mutmut, 'results', '--all', 'true'], copy, env, capture=True)
    selected = {}
    for line in results.splitlines():
        name, separator, status = line.strip().partition(': ')
        if separator and name.startswith(PREFIX):
            selected[name] = status
    if len(selected) != 276:
        raise ValueError(f'Expected 276 scheduling mutants, found {len(selected)}')
    timeouts = [name for name, status in selected.items() if status == 'timeout']
    if timeouts:
        (copy / 'pyproject.toml').write_text(config + 'timeout_multiplier = 30.0\ntimeout_constant = 2.0\n')
        run([mutmut, 'run', '--max-children', '1', *timeouts], copy, env)
        confirmed = run([mutmut, 'results', '--all', 'true'], copy, env, capture=True)
        for name in timeouts:
            if f'{name}: timeout' not in confirmed.splitlines() and f'    {name}: timeout' not in confirmed.splitlines():
                raise ValueError(f'Timeout not confirmed: {name}')
    print('\n'.join(f'{name}: {status}' for name, status in selected.items()))
    bad = {name: status for name, status in selected.items()
           if status not in ('killed', 'timeout')
           and not (status == 'survived' and name.removeprefix(PREFIX) in EQUIVALENT)}
    if bad:
        raise ValueError(f'Unclassified or unexpected scheduling mutants: {bad}')
    print(f'{len(selected)} scheduling mutants classified; {len(timeouts)} confirmed timeouts')


if __name__ == '__main__':
    def interrupt(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
        signal.signal(sig, interrupt)
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error
