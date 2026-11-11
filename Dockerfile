FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen
COPY tests ./tests
COPY benchmarks ./benchmarks
COPY Makefile ./

CMD ["sh", "-c", "uv run pytest tests/ -q --serial && uv run pytest tests/ -q --parallel-start-method=forkserver && uv run pytest tests/ -q --parallel-start-method=spawn"]
