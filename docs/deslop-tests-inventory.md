# Pytest-parallel Tests inventory

The calibration is scoped to the first-party plugin at `e54d5b2f`.
`make test`, `make lint` and `make coverage` are the ordinary entry points.
The installed-wheel witness verifies that the fixture and child import the
candidate package. On macOS arm64, `make coverage` passed 158 tests and
verified separate profiles from both workers. It covered 1,545 of 1,759
statements and 586 of 718 branches. Hosted test and lint passed for #28 on
the supported Linux and macOS runners.

| Contract and critical decisions | Protected scope | Existing witness | Remaining |
| --- | --- | --- | --- |
| CLI mode and plan output, hook defaults and failures, pins and affinities | `plugin.py`, coordinator hook selection and `scheduling.py` | `test_options.py`, `test_campaign.py`, `test_partition.py` and the installed-wheel [hook cases](deslop-hook-errors.md) | Recheck plan invalidation, worker-count fallback and hook admission on the combined selection. |
| File groups, weighted assignment and plan serialization | `scheduling.py` | The [serial scheduling scenario](deslop-scheduling-tests.md) accounts for all 276 identities at its recorded source. | Verify the same source and activation in the retained recipe. Preserve the longer-bound timeout confirmation. |
| Worker startup, exit and supervision, terminal reporter restoration, JSONL reconciliation | `coordinator.py` | `test_p0_correctness.py` and the [event stream scenario](deslop-event-stream.md) cover real worker failures, interleaved events, rejected input and truncation. | Account for supervision, missing stream/worker shutdown and errors outside the bounded reader and dispatcher. Keep the six final reader dispositions distinct from later targeted fixes. |
| Report emission, null diagnostics, pytest public report reconstruction and native worker coverage | `worker.py`, the report intake in `coordinator.py` and the coverage target | `test_p0_correctness.py`, `test_coverage.py`, the [report observer scenario](deslop-worker-reports.md) and [coverage](deslop-coverage.md) | Retain the 60 caught observer identities and prove process profile activation in the selected recipe. |
| Local socket policy, resolver behavior and bind compatibility in a real worker | `network.py` and the policy setup in `worker.py` | `test_integration.py`, `test_backlog.py`, the [installed wheel and fake transport](deslop-network-guard.md) and [empty bind](https://github.com/joshuarli/pytest-parallel/pull/26) | Reconcile the historical partial selection to current source and verify activation before counting its outcomes. Keep proofs on owned loopback sockets and fake transports. |

Stuff's repomod suite is the exercised installed-wheel consumer for #26.
Toolbox reproduced its existing FFmpeg failure in the paired comparison.
Additional operating systems and consumers require their own evidence.

## Retained lane acceptance

Use the serial pytest recipe with `-p no:parallel` when mutmut measures
test associations. Print the entire classified change, the union of
changed production regions and protected regions, and every resulting
identity. Include tests, fixtures, configuration, the lock, deletions and
renames in classification. Verify that executed tests load the instrumented
source. Treat an empty relevant selection or a missing result as a failure.

Run the controls against the actual workflow. An ordinary green change that
deletes a protective test must fail its mutation gate. A new uncovered
decision must fail. Combining unrelated production changes with test
deletion must report both regions and still catch the reopened miss.
Documentation-only changes must report that no relevant paths changed.
Confirm timeouts with a longer bound. Capture total runner cost including
retries and establish paired warm suite cost before closing DSLP-4.

## Option parsing scenario

At `45b45492`, mutmut 3.8.1 selected 127 identities across
`_parse_plan`, `_parse_jobs`, `_auto_cpu_count`, `_parse_ramp`,
`_parse_balance` and `_parse_start_method`. The first run caught 82
with 27 survivors and 18 identities with no tests. The final option
tests caught 126 of the same 127 with one survivor, no uncovered
identities and no timeouts. Both runs took about seven seconds on
macOS arm64 with CPython 3.15.2. The instrumented source blob was
`5fd554ec87169f9c31cc714c14e785f27c4760b6`.

The sole survivor is `_parse_ramp__mutmut_25`. It changes the diagnostic
for a `ValueError` in `float(number_text)`. Only a matched decimal,
infinity or NaN token can reach that conversion. All 770 Unicode decimal
characters in the pinned Python passed probes for whole, fractional and
exponent positions. Signed and unsigned special tokens also parsed.
Overflow returns a nonfinite float and reaches the separate finiteness
checks. The conversion error is unreachable for the matched grammar.

For reproduction, archive `src`, `tests`, `pyproject.toml` and
`uv.lock` from the checked revision. Set `TMPDIR` under the scratch
tree and install the locked pytest and mirrored mutmut 3.8.1. In the
scratch `pyproject.toml`, configure:

```toml
[tool.mutmut]
source_paths = ["src"]
only_mutate = ["src/pytest_parallel/plugin.py"]
pytest_add_cli_args = [
  "-p", "no:parallel", "-k",
  "not honors_python_cpu_count_override and not worker_count_capped and not invalid_max_workers_hook",
]
pytest_add_cli_args_test_selection = ["tests/test_options.py"]
```

```sh
set --
for method in parse_plan parse_jobs auto_cpu_count parse_ramp parse_balance parse_start_method; do
  set -- "$@" "pytest_parallel.plugin.x__${method}__mutmut_*"
done
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m mutmut run --max-children 1 "$@"
```

The mutation run uses direct option tests. Ordinary option testing
executes the subprocess and pytest startup cases as well. All 36 ordinary
option tests, Ruff and ty passed locally.

## Coordinator file planning

Against `8da30d09`, direct file-hook tests raised detection from 33
to 67 of the same 83 `Coordinator._build_units` mutations. The two
runs used coordinator blob `db7b1141d559d3690ef83dff686873076bff4f9a`.
The tests exercise grouping, collected item order, the hook's private
copy of the item list, summed overrides and defaults, and rejection
of nonpositive or nonfinite values.

The redundant guard after weight validation needs both an empty
file and a NaN weight. The coordinator creates each file entry while
adding an item, and hooks receive copies of that item list. The
existing validator rejects NaN before returning. Removing the guard
leaves 79 generated identities in coordinator blob
`7f5a114fe22945f97beac131eb25e47b7c0dba5c`. The final run caught
67 and left 12 survivors. Those survivors and the other coordinator
functions remain open.

Use the same serial mutmut setup as the options scenario, setting
`only_mutate = ["src/pytest_parallel/coordinator.py"]` and selecting
`tests/test_campaign.py -k 'missing_hooks or file_hooks_group or file_hook_rejects'`.
Run `mutmut run --max-children 1 'pytest_parallel.coordinator.xǁCoordinatorǁ_build_units__mutmut_*'`
with pytest plugin autoload disabled. The ordinary suite passed all
173 tests on macOS arm64.

A follow-up at `8197c593` caught all 79 of those same identities with
the same instrumented source blob. The test verifies that the path's
scoped hook receives an absolute path while its public arguments and
result use the root-relative path. A marker on one file and a hook on
another join the files into one unit. The hook assertions also cover
item copies, invalid group names and diagnostics that identify the
source path. The command above selects these cases.

## Worker pins and maximums

Against `4f498ebd`, direct hook witnesses raised detection from nine to
61 of the same 64 identities across `Coordinator._resolve_pins` and
`_resolve_max_workers`. The baseline had 47 survivors and eight
identities with no tests. The new cases exercise repeated and missing
votes, worker zero, scoped hooks, conflicts, type and range errors,
and the documented default and positive worker limits.

The three remaining identities target redundant branches. The
coordinator receives a real `pytest.Config`, whose constructor always
sets `hook`. A missing shard-worker hook is already handled by
`getattr` with a default. The internal result method returns a list
on both routes. Removing those branches leaves 51 identities, all
caught, in coordinator blob `43d9c9ca7645241ee4beb4d0fdf4d863a1d24313`.
The ordinary suite passed all 188 tests and lint.

Use the coordinator file-planning setup with `tests/test_campaign.py`
and `-k 'missing_hooks or shard_pin_votes or worker_limit_hook'`.
Select `pytest_parallel.coordinator.xǁCoordinatorǁ_resolve_pins__mutmut_*`
and `pytest_parallel.coordinator.xǁCoordinatorǁ_resolve_max_workers__mutmut_*`
in the same serial run.

## Whole-change gate trial

The trial runs `scripts/mutants_diff.py BASE` on a clean committed
head with mutmut 3.8.1 in the test environment. Set `MUTMUT` to that
environment's executable. Use `--plan` to inspect a dirty change or
`--shard plugin` to execute one lane. The coordinator's file-planning
selection uses `--shard coordinator-plan`. A production change to the
coordinator selects the whole module and includes both witness sets.
The gate archives the tested
revision and runs the existing serial recipes. Unknown paths, missing
witnesses, empty relevant selections, incomplete results, and budget
exhaustion fail.

The options shard against `8da30d09` reported 126 caught and the
one previously dispositioned equivalent. In isolated controls,
removing the invalid-plan-mode test left 32 ordinary option tests
passing and reopened `x__parse_plan__mutmut_18`. Adding an
uncovered branch left 33 ordinary tests passing and exposed
surviving `_parse_plan` mutations. A mixed-change plan selected
both the unrelated scheduling module and the protected option scope
after a test deletion. A docs-only plan reported no relevant changes.
These checks used the local driver. The mixed negative still needs
execution through the complete workflow.

The standalone scheduling shard accounted for all 276 identities,
with 264 caught, 11 equivalent and one confirmed timeout. At
`f320bda` against `4f498ebd`, the file-planning shard caught all
79 selected identities through this same driver.

The worker shard caught all 60 report identities through `make
mutants-diff` at `19775d6`. It runs the two in-process report
observers. An earlier selection also ran child CLI checks in the
mutation environment, where plugin autoload is disabled. Those
checks require the normal plugin and remain in the ordinary suite.
The draft tries the four locally qualified shards on Linux and
macOS. The remaining coordinator and socket selections stay open.

On the first aggregate attempt, `f7c2795` against `8da30d09`
exhausted 1,200 seconds in the coordinator. It processed 130 of
559 selected coordinator mutations, with 48 caught and 82 survivors.
The aggregate never reached the other components. The trial now
supports distinct module shards and emits partial counts on budget
exhaustion. The coordinator needs smaller behavioral witnesses,
followed by repeat measurements for the full supported selection.
Keep the workflow outside required CI and fleet retention until the
complete positives and controls pass within the declared budgets.
