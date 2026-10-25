.PHONY: build check lint test preflight bump publish

BUMP ?= minor

check:
	uv run ruff check
	uv run ty check

lint:
	uv run ruff check --fix
	uv run ty check --fix

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
