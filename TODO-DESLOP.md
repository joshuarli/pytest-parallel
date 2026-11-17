Prefix: DSLP
Next: 6

Deslop campaign backlog ([plan](https://github.com/laputa-systems/stuff/blob/main/docs/campaigns/deslop.md), tier Calibration). One agent works this file with the `deslop` skill: take the lowest-numbered open ticket whose area does not start with `Needs owner ·`. After DSLP-5, work the open P1 and P2 findings, then fill in `## Report` below.

Ground evidence at 4968f8e: the plan fixture has a local pytest.ini; PR 15 CI passed at 0c57bde9, and the supported workflow shape and baseline costs are recorded in [Ground evidence](docs/deslop-ground.md).

## Report

Not started.

## Tickets


### DSLP-2 · P2 · Diagnose: ultrareview into this backlog

- **Area:** deslop · diagnose
- **Where:** whole repository
- **Problem:** No review has ranked this repository's risks for the deslop pass.
- **Recommendation:** Run the deslop Diagnose step. Accept: the diff touches only docs, comments, and this file, and every finding names its Fix with.
- **Fix with:** deslop
- **Effort:** S

### DSLP-3 · P2 · Types: strict profile and typing findings

- **Area:** deslop · types
- **Where:** type checker and lint configuration; Python sources
- **Problem:** The strict-profile candidates in the deslop skill's tools reference have not been measured here.
- **Recommendation:** Run the deslop Types step. Accept: clean at the adopted profile, escape hatches not increased, witnesses recorded.
- **Fix with:** deslop
- **Effort:** M

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

