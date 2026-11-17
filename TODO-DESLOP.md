Prefix: DSLP
Next: 7

Deslop campaign backlog ([plan](https://github.com/laputa-systems/stuff/blob/main/docs/campaigns/deslop.md), tier Calibration). One agent works this file with the `deslop` skill: take the lowest-numbered open ticket whose area does not start with `Needs owner ·`. After DSLP-5, work the open P1 and P2 findings, then fill in `## Report` below.

Ground evidence at 4968f8e: the plan fixture has a local pytest.ini; PR 15 CI passed at 0c57bde9, and the supported workflow shape and baseline costs are recorded in [Ground evidence](docs/deslop-ground.md).

## Report

Diagnose at `0ecb2b3`: reviewed first-party Python, tests, manifests, CI/release configuration, docs, both backlogs and recent churn. Lenses covered public hooks and CLI, scheduling, errors, worker lifecycle and JSONL reconciliation, argument/environment forwarding, network guard, tests, dependencies and documentation. One P2 finding (DSLP-6); no P1, P3 or P4 findings. Built-wheel synthetic hook probes reproduced the finding; baseline Ruff and ty passed. Linux, Windows, consumer integration, live release/registry paths, broader plugin combinations, performance, coverage and mutation were not exercised; known coverage and in-memory plugin limitations remain DSLP-4. No runtime, consumer or performance claim follows from this docs-only pass. Next: DSLP-3 Types, without applying DSLP-6 in this step.

Types at `60129d817c3f82f075a8a8dc12578866ed135a10` (macOS, Python 3.15, ty 0.0.101, Ruff 0.17.4): no setting adopted; zero findings alone do not justify one. The existing profile passed before and after. First-party hatch **matching lines** (`cast\(|# type: ignore|# ty: ignore|\bAny\b|# noqa`, all tracked Python in `src`, `tests`, `benchmarks`, `scripts`): 76 before and after, including 75 in the ty scope. This counts lines, not individual occurrences. No source or configuration changed, so no new witness is required; none of the candidates met the adoption test.

| Candidate | Diagnostics | Decision and evidence |
| --- | ---: | --- |
| ty `blanket-ignore-comment`, `disjoint-cast`, `dynamic-function-decorator-return` | 0 each | Reject: no demonstrated defect or removed trust. |
| ty `missing-type-argument` | 4 | Reject: two bare lists are public hooks (`plugin.py:33,37`), whose signatures are out of scope; two bare dicts (`test_campaign.py:36,154`) consume unvalidated dynamic JSON. A fabricated shape would not remove trust. |
| ty `possibly-unresolved-reference` | 0 | Reject: no demonstrated defect or removed trust. |
| ty `unsound-assignment`, `unsound-return-statement` | 1 each | Reject: same false inference at `scheduling.py:80,81`: `parent` starts as integers from `range` and only integer indices are assigned at lines 79, 87; explicit `parent: list[int]` still produced both diagnostics. One false positive in 4,962 scoped lines exceeds the limit. |
| ty `unsound-yield`, `unsupported-dynamic-base`, `unused-ignore-comment` | 0 each | Reject: no demonstrated defect or removed trust. |
| Ruff `ANN` / `ANN401` | 55 / 28 (overlap) | Reject: 28 explicit dynamic annotations include pytest hooks, socket forwarding and test doubles (`coordinator.py:305`, `network.py:92`, `test_p0_correctness.py:304`); other findings include test fixture and return annotations (`test_partition.py:100`) and a pytest hook generator (`plugin.py:197`). They are not all defects; broad enforcement would require extensive intentional API cleanup. Dynamic first-party plan/event dictionaries remain a typing gap. |
| Ruff `PGH003` | 0 | Reject: no demonstrated defect or removed trust; existing ignores specify codes. |
| Ruff `TC` | 24 | Reject: type-only import suggestions and quoting casts, e.g. `api.py:4`, `coordinator.py:613`; no demonstrated defect or removed trust and import changes may affect runtime introspection. |
| Ruff `B`, `RET` | 0 each | Already selected (with existing exceptions); no extra setting justified. |

Measurement commands: set `TMPDIR="$PWD/.work/tmp"`, `UV_PROJECT_ENVIRONMENT=/Users/josh/repos/pytest-parallel/.work/wt/ds-ground-finish/.work/ground-final`, `UV_NO_SYNC=1`, `UV_PYTHON_DOWNLOADS=never`, `PYTHONPATH="$PWD/src"`; `cpu-guard --cores 2 -- uv run ty check --output-format concise` and `cpu-guard --cores 2 -- uv run ruff check` exited 0. For each ty rule in the table, `uv run ty explain rule "$rule"` exited 0, then `cpu-guard --cores 2 -- uv run ty check --output-format concise --error "$rule"` exited 1 for the three nonzero rules and 0 for the rest. For each Ruff family in the table, `cpu-guard --cores 2 -- uv run ruff check --isolated --select "$rule" --output-format concise src tests benchmarks scripts` exited 1 for ANN, ANN401 and TC, 0 otherwise. `rg -c 'cast\(|# type: ignore|# ty: ignore|\bAny\b|# noqa' src tests benchmarks scripts | awk -F: '{n += $2} END {print n}'` gave 76. The explicit-list experiment was reverted. Final `cpu-guard --cores 2 -- make test` exited 0 (119 passed), and `cpu-guard --cores 2 -- make lint` exited 0 (Ruff and ty passed), with the same environment. `todo --file TODO-DESLOP.md close DSLP-3` and `todo --file TODO-DESLOP.md check` exited 0. No runtime, import, public API or configuration change: consumers and performance are unaffected and were not tested; coverage and mutation remain DSLP-4. DSLP-6 remains deferred. Tooling gap: ty's recursive-list inference emits the two false positives above.

## Tickets




### DSLP-4 · P2 · Tests: coverage, boundary gaps, mutation

- **Area:** deslop · tests
- **Where:** test suites and CI
- **Problem:** Coverage and mutation results are unmeasured; no deslop mutation lane exists. Qualification at eda0c359 (macOS, Python 3.15.2): mutmut 3.8.1 full-package recipe exited 1 in 11.77s before classifications; debug rerun exited 1 in 1.73s because pytest-parallel defaults to workers and rejects mutmut’s in-memory StatsCollector execution hooks. Verdict: does not work through pytest-parallel; mutant counts, worker activation, serial alternative cost, and diff-scoped CI timing remain unverified. Mutmut mirrors MUTANT_UNDER_TEST into the environment and uses generated function trampolines, but worker inheritance was not demonstrated. mutmut through pytest-parallel: does not work (in-memory plugin rejected); serial with -p no:pytest_parallel: does not complete here (actual entry-point name no:parallel), counts unavailable, 7.01s (retry 6.90s). Stats collection failed on the known TMPDIR-sensitive test_hooks_weights_groups_and_pin_via_plan after 16 passed; no mutant was classified and the requested killed-mutant fault check could not run.
- **Recommendation:** Run the deslop Tests step. Accept: no undispositioned survivor in critical code, the test cost budget holds, and the lane is green where the tools are mirrored.
- **Fix with:** deslop
- **Effort:** M

### DSLP-5 · P2 · Dead code: tools and debloat

- **Area:** deslop · dead code
- **Where:** whole repository
- **Problem:** No dead-code scan has run.
- **Recommendation:** Run the deslop Dead code step. Accept: tools clean or allowlisted with reasons; walk-backs filed as Needs owner tickets.
- **Fix with:** deslop
- **Effort:** M


### DSLP-6 · P2 · Scheduling hook AttributeErrors silently discard customization

- **Area:** scheduling hooks
- **Where:** src/pytest_parallel/coordinator.py:249, src/pytest_parallel/coordinator.py:258, src/pytest_parallel/coordinator.py:278
- **Problem:** The handler catches AttributeError raised by hook implementations as if the hook were absent. A broken affinity hook can silently split files across workers, a failed pin can move a shard, and a failed weight silently uses test count. Built wheel repro: create a pytest.ini containing [pytest], test_a.py and test_b.py each containing one passing test, and conftest.py defining `def pytest_parallel_file_groups(path, items): raise AttributeError("hook failed")`; run `PYTHONPATH="$PWD/.work/tmp/diagnose-wheel-unpacked" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -p pytest_parallel.plugin -j 2 --parallel-plan=json .work/tmp/diagnose-hook`. Actual exit 0, two units on separate workers, no diagnostic; expected a nonzero exit reporting the hook failure and no plan. With analogous weight and shard-worker hooks the same command exited 0 with default weights and no pins; replacing AttributeError with ValueError exited 3 with the diagnostic and empty stdout. Wheel was built with `uv build --wheel --out-dir .work/tmp/diagnose-wheel` and unpacked into the PYTHONPATH directory.
- **Recommendation:** Let exceptions raised during hook execution propagate; detect absent hook attributes outside the call. Exercise each hook through the installed product and assert no plan or workers after the error.
- **Fix with:** error-model
- **Effort:** S

