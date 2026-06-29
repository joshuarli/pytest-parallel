.PHONY: build check lint test release

check:
	uv run ruff format --check
	uv run ruff check
	uv run ty check

lint:
	uv run ruff format
	uv run ruff check --fix
	uv run ty check --fix

test:
	uv run pytest tests/ -q --serial
	uv run pytest tests/ -q

build:
	uv build --wheel

publish: build
	vault UV_PUBLISH_USERNAME=__token__ UV_PUBLISH_PASSWORD -- uv publish
