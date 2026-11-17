from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest


def pytest_sessionfinish() -> None:
    guard_dir = os.environ.get("COVERAGE_GUARD_DIR")
    worker_id = os.environ.get("PYTEST_PARALLEL_WORKER_ID")
    if guard_dir and worker_id is not None:
        import coverage

        if coverage.Coverage.current() is not None:
            (Path(guard_dir) / f"worker-{worker_id}").write_text(str(os.getpid()))


def _run(args: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    process = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        output, _ = process.communicate(timeout=90)
    except BaseException:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.communicate()
        raise
    assert process.returncode == 0, output
    return output


def test_installed_wheel_native_worker_coverage(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith('COVERAGE_') and k not in {'_PYTEST_PARALLEL_WORKER', 'PYTEST_PARALLEL_WORKER_ID', 'PYTEST_ADDOPTS', 'PYTHONPATH'}}
    wheels = tmp_path / 'wheels'
    wheels.mkdir()
    _run(['uv', 'build', '--wheel', '--out-dir', str(wheels)], cwd=repo, env=env)
    wheel, = wheels.glob('*.whl')
    installed = tmp_path / 'installed'
    _run(['uv', 'pip', 'install', '--no-deps', '--target', str(installed), str(wheel)], cwd=tmp_path, env=env)
    env['PYTHONPATH'] = str(installed)
    package = tmp_path / 'subject'
    package.mkdir()
    (package / '__init__.py').write_text('')
    (package / 'logic.py').write_text('def choose(flag):\n    if flag:\n        return "yes"\n    else:\n        return "no"\n')
    (package / 'unused.py').write_text('def never_called():\n    return 42\n')
    (tmp_path / 'conftest.py').write_text('import os\nfrom pathlib import Path\nimport pytest_parallel\nassert Path(pytest_parallel.__file__).resolve().is_relative_to(Path(os.environ["WHEEL_TARGET"]))\ndef pytest_sessionstart(session):\n    if not os.getenv("_PYTEST_PARALLEL_WORKER"):\n        Path("parent.pid").write_text(str(os.getpid()))\n')
    env['WHEEL_TARGET'] = str(installed)
    for name, flag, expected in [('a', 'True', 'yes'), ('b', 'False', 'no')]:
        (tmp_path / f'test_{name}.py').write_text(
            'import os\nfrom pathlib import Path\n'
            f'def test_{name}():\n'
            '    if os.getenv("DROP_WORKER_COVERAGE") and os.getenv("_PYTEST_PARALLEL_WORKER"):\n'
            '        import coverage\n        coverage.Coverage.current().stop()\n'
            '    from subject.logic import choose\n'
            f'    Path("{name}.pid").write_text(str(os.getpid()))\n'
            f'    assert choose({flag}) == "{expected}"\n'
        )

    def measure(mode: str, drop: bool = False) -> dict:
        data = tmp_path / f'data-{mode}-{drop}'
        config = tmp_path / f'coverage-{mode}-{drop}.ini'
        config.write_text(f'[run]\nbranch = True\nparallel = True\nconcurrency = multiprocessing\npatch = subprocess\nsource = {package}\ndata_file = {data}\n')
        child_env = env | {'COVERAGE_RCFILE': str(config)}
        if drop:
            child_env['DROP_WORKER_COVERAGE'] = '1'
        args = ['-p', 'no:parallel'] if mode == 'serial' else ['-j', '2']
        out = _run([sys.executable, '-m', 'coverage', 'run', '-m', 'pytest', '-q', *args], cwd=tmp_path, env=child_env)
        assert '2 passed' in out, out
        pids = [(tmp_path / f'{name}.pid').read_text() for name in ('a', 'b')]
        parent = (tmp_path / 'parent.pid').read_text()
        if mode == 'parallel':
            assert len(set(pids)) == 2
            assert parent not in pids
        else:
            assert pids == [parent, parent]
        _run([sys.executable, '-m', 'coverage', 'combine'], cwd=tmp_path, env=child_env)
        json_path = tmp_path / f'{mode}-{drop}.json'
        _run([sys.executable, '-m', 'coverage', 'json', '-o', str(json_path)], cwd=tmp_path, env=child_env)
        return json.loads(json_path.read_text())['files']

    def oracle(files: dict) -> None:
        logic = files['subject/logic.py']
        unused = files['subject/unused.py']
        assert logic['executed_lines'] == [1, 2, 3, 5], 'worker lines missing'
        assert logic['executed_branches'] == [[2, 3], [2, 5]]
        assert unused['executed_lines'] == []
        assert unused['missing_lines'] == [1, 2]

    serial = measure('serial')
    parallel = measure('parallel')
    oracle(serial)
    oracle(parallel)
    with pytest.raises(AssertionError, match='worker lines missing'):
        oracle(measure('parallel', drop=True))
