FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.6.6 /uv /bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "dealgoblin"]
