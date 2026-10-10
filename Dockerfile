FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.7.4 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY cloud_app.py gremlin_client.py ./
RUN useradd --uid 10001 --create-home gremlin
USER gremlin
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn cloud_app:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]
