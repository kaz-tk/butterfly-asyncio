FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

COPY src/ src/
RUN uv sync --no-dev

EXPOSE 57575

ENTRYPOINT ["tini", "--"]
CMD ["uv", "run", "butterfly", "--host", "0.0.0.0", "--port", "57575"]
