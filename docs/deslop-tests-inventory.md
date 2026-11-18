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
