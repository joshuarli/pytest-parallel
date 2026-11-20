Prefix: PAR
Next: 17
### PAR-15 · P3 · Benchmark representative suites and resource costs

- **Area:** benchmark coverage
- **Where:** benchmarks/run_benchmarks.py
- **Problem:** The synthetic CPU-trivial suites measure wall time only and do not represent real test workloads, aggregate process memory or CPU, attribution, tail latency, or a paired regression budget.
- **Recommendation:** Add a reproducible representative suite with completed-work and correctness oracles; measure process-tree resources and document profiling and paired host-gated comparisons.
- **Fix with:** bench-pyramid
- **Effort:** M

### PAR-16 · P3 · Strengthen benchmark preflight and result provenance

- **Area:** benchmark operability
- **Where:** benchmarks/bench.py
- **Problem:** The entrypoint checks imports and host tool availability but does not verify disk capacity, leftover processes, tool versions or package artifact identity; host diagnostics are not retained in the summary.
- **Recommendation:** Add selected-workload prerequisite and process checks, preserve readiness diagnostics and exact tool and artifact identity, and test failures before workload execution.
- **Fix with:** bench-pyramid
- **Effort:** M
