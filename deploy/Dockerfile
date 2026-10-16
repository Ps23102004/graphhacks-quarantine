FROM python:3.13-slim-bookworm@sha256:5024f48ba9441d4b13a95d3945abc6365538e3a31109833367a1923523c6efed

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.23

COPY pyproject.toml uv.lock README.md ./
COPY quarantine/ quarantine/
COPY web/ web/
COPY fixture.yaml ./

RUN uv sync --frozen --no-dev --all-extras

EXPOSE 8765

CMD ["/app/.venv/bin/python", "web/server.py", "--host", "0.0.0.0", "--port", "8765"]
