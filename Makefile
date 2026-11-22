.PHONY: build check lint test coverage mutants-scheduling preflight bump publish publish-mypypi bench bench-check bench-list

BUMP ?= minor

check:
	uv run ruff check
	uv run ty check

lint:
	uv run ruff check
	uv run ty check

test:
	uv run pytest tests/ -q

build:
	uv build --wheel

preflight:
	@command -v vault >/dev/null || { echo "preflight: vault is not installed" >&2; exit 1; }
	@vault ls | grep -qx UV_PUBLISH_PASSWORD || { \
		echo "preflight: store the PyPI token first: vault set UV_PUBLISH_PASSWORD" >&2; \
		exit 1; \
	}
	@next=$$(uv version --bump $(BUMP) --dry-run --short); \
		vault UV_PUBLISH_PASSWORD -- uv run python scripts/preflight_pypi.py "$$next"

bump: preflight
	uv version --bump $(BUMP)

publish: bump build
	vault UV_PUBLISH_USERNAME=__token__ UV_PUBLISH_PASSWORD -- uv publish
	$(MAKE) publish-mypypi

# Publish to our private wheel index as well. PACKAGES lists top-level
# requirements; mypypi resolves the transitive closure from PyPI, builds
# the wheels, and publishes them.
PACKAGES ?= joshuarli-pytest-parallel==0.4.0
STUFF ?= stuff
publish-mypypi:
	$(STUFF) publish pypi $(PACKAGES)

# Each invocation owns a fresh data directory; combine only after pytest exits.
coverage:
	@mkdir -p .work/coverage; \
	dir=$$(mktemp -d "$$PWD/.work/coverage/run.XXXXXXXX") || exit 1; \
	printf '[run]\nbranch = True\nparallel = True\nconcurrency = multiprocessing\npatch = subprocess\nsource = %s/src/pytest_parallel\ndata_file = %s/data\n' "$$PWD" "$$dir" > "$$dir/coverage.ini"; \
	export COVERAGE_RCFILE="$$dir/coverage.ini"; \
	export COVERAGE_GUARD_DIR="$$dir" PYTHONPATH="$$PWD/tests$${PYTHONPATH:+:$$PYTHONPATH}"; \
	uv run coverage run -m pytest -p test_coverage tests/ -q -j 2 && \
	uv run python -c 'import glob, os, pathlib, coverage; d = pathlib.Path(os.environ["COVERAGE_GUARD_DIR"]); pids = [(d / ("worker-" + str(i))).read_text() for i in range(2)]; assert len(set(pids)) == 2; files = [glob.glob(str(d / ("data.*.pid" + pid + ".*"))) for pid in pids]; assert all(len(f) == 1 for f in files), files; data = [coverage.CoverageData(basename=f[0]) for f in files]; [x.read() for x in data]; assert all(any(p.endswith("/pytest_parallel/worker.py") and x.lines(p) for p in x.measured_files()) for x in data), "missing worker measurement"' && \
	uv run coverage combine && uv run coverage report && \
	uv run coverage json -o "$$dir/coverage.json"

mutants-scheduling:
	uv run python scripts/mutants_scheduling.py

BENCH_ARGS ?=
bench:
	uv run python benchmarks/bench.py run $(BENCH_ARGS)

bench-check:
	uv run python benchmarks/bench.py check $(BENCH_ARGS)

bench-list:
	uv run python benchmarks/bench.py list $(BENCH_ARGS)

.PHONY: clean
clean:
	@for artifact in ./dist ./.pytest_cache ./.ruff_cache; do \
	  if test -L "$$artifact" || { test -e "$$artifact" && ! test -d "$$artifact"; }; then \
	    printf 'make clean: %s must be a local build directory\n' "$$artifact" >&2; exit 1; \
	  fi; \
	done
	rm -rf -- ./dist ./.pytest_cache ./.ruff_cache
