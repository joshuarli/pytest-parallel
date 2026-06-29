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
	uv run python -m build --wheel

release: build
	uv run twine upload dist/*
