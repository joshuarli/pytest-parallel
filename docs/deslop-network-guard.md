# Network guard boundary witnesses

Base `e49e7fb1080a8766c28c2257b8261966aef8dcd0`, macOS, CPython 3.15.2. The runtime source was unchanged. `test_network_address_and_resolver_boundary` exercises allowed and denied host forms with fake resolver and transport and verifies restoration. `test_network_guard_installed_wheel_spawn` builds and installs the wheel, asserts the spawned worker imports it, exchanges data over owned loopback and Unix sockets, and checks denial of TEST-NET and a fake hostname before their fake transport and resolver. The child processes have 90-second deadlines and process-group cleanup; sockets have three-second timeouts. No third-party endpoint is contacted.

The contract mismatch remains open for a separate runtime fix: `uv run python -c 'import socket; from pytest_parallel.network import network_blocked; s=socket.socket(); exec("with network_blocked(): s.bind((\"\", 0))")'` exits 1 with `PermissionError`; AGENTS.md allows the empty local bind address. No consumer or performance claim is made here. Broader Tests and CI remain open.

Historical unqualified partial observations: mutmut 3.8.1 selected the same 121 identities in `_targets_loopback` and `_is_loopback_host` before and after the first direct witness. Results were 37 killed, 82 survived, two timeouts before; 50 killed and 71 survived after. The 71 survivors have not been dispositioned, the baseline timeouts have not been confirmed, and generated-source activation was not verified. These numbers do not qualify mutation or CI. The initial run used incorrect single-underscore patterns and failed with an empty selection; it is excluded.

Verification used `TMPDIR="$PWD/.work/tmp"`, `UV_PROJECT_ENVIRONMENT="$PWD/.work/tmp/venv"`, `UV_FROZEN=1`, `UV_OFFLINE=1`, `UV_PYTHON_DOWNLOADS=never`, `PYTHON_CPU_COUNT=2`, `CARGO_BUILD_JOBS=1`, `RUST_TEST_THREADS=1`, and `RUSTC_WRAPPER=kache`; each command held an owned heavy slot and ran under `cpu-guard --cores 2 --`. `uv run pytest -p no:parallel tests/test_integration.py::test_network_address_and_resolver_boundary tests/test_integration.py::test_network_guard_installed_wheel_spawn -q` exited 0 with two passed after the faults. `make test` exited 0 with 154 passed; `make lint` exited 0 with Ruff and ty passing. The latter checks ran before the faults; the source hash was restored afterward.

The hand-fault harness below ran under the mutation lock and a heavy slot as `cpu-guard --cores 2 -- uv run python .work/tmp/network_faults.py` and exited 0. The resolver fault made the direct witness exit 1 with `DID NOT RAISE`; the disabled-context fault made the installed-wheel witness exit 1 with `external transport reached`. The fake transport prevented external contact. The source SHA-256 before and after was `7a1c2d876fab7cd162ea13d659f418a8aee95260ac6b1b206f954e9a86a186a9`. For reproduction, save this script in `.work/tmp/network_faults.py`, acquire the mutation lock and a heavy slot, and run it with the environment above. The original run also backed up `network.py` and restored it in the owning shell's exit trap before releasing either lock.

```python
from pathlib import Path
import hashlib
import os
import subprocess
import sys

source = Path('src/pytest_parallel/network.py')
original = source.read_bytes()
original_hash = hashlib.sha256(original).hexdigest()
targets = [
    ('resolver', '        if address is None or address == "" or address == b"":', '        if address == "example.invalid":\n            return original(*args, **kwargs)\n        if address is None or address == "" or address == b"":', 'tests/test_integration.py::test_network_address_and_resolver_boundary', 'DID NOT RAISE'),
    ('disabled-worker-guard', '    originals: list[tuple[Any, str, Callable[..., Any]]] = []', '    yield\n    return\n    originals: list[tuple[Any, str, Callable[..., Any]]] = []', 'tests/test_integration.py::test_network_guard_installed_wheel_spawn', 'external transport reached'),
]
try:
    for label, before, after, test, expected in targets:
        text = original.decode()
        assert text.count(before) == 1, label
        source.write_text(text.replace(before, after, 1))
        try:
            result = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'no:parallel', test, '-q'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120, env=os.environ.copy(), start_new_session=True)
            print(f'{label}: exit {result.returncode}; expected diagnostic {expected!r}: {expected in result.stdout}', flush=True)
            print(result.stdout, flush=True)
            if result.returncode != 1 or expected not in result.stdout:
                raise SystemExit(f'{label}: fault did not produce the intended failure')
        finally:
            source.write_bytes(original)
finally:
    source.write_bytes(original)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    print(f'restored sha256 {original_hash}', flush=True)
```
