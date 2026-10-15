FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY quarantine/ quarantine/
COPY web/ web/
COPY fixture.yaml ./

RUN uv pip install --system --no-cache -e .

EXPOSE 8765

CMD ["python", "web/server.py", "--port", "8765"]
