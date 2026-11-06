.PHONY: build check lint test preflight bump publish publish-mypypi

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
# the wheels, and publishes them. Only the host platform is built unless
# PLATFORM names others (cross-platform builds need matching hosts).
WORK_DIR ?= .work/registry-pub
PLATFORM ?=
BUCKET ?= stuff-mypypi
PACKAGES ?= joshuarli-pytest-parallel==0.4.0
STUFF_DIR ?= ../stuff
publish-mypypi:
	@test -x "$(STUFF_DIR)/deploy/publish-mypypi.sh" || { echo "STUFF_DIR does not point at a stuff checkout: $(STUFF_DIR)" >&2; exit 2; }
	STUFF_DIR="$(STUFF_DIR)" \
	PACKAGES="$(PACKAGES)" \
	WORK_DIR="$(WORK_DIR)" PLATFORM="$(PLATFORM)" BUCKET="$(BUCKET)" \
	"$(STUFF_DIR)/deploy/publish-mypypi.sh"
