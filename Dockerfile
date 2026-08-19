FROM python:3.13.5-slim-bookworm AS builder
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /build
COPY app/ ./
RUN pip install --no-cache-dir uv==0.8.11 \
    && uv sync --frozen --no-editable

FROM python:3.13.5-slim-bookworm AS runtime
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system notes && useradd --system --gid notes --home-dir /app notes
WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY app/ ./
RUN chown -R notes:notes /app
USER notes
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=12 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live')"]
CMD ["uvicorn", "notes_rag.main:app", "--host", "0.0.0.0", "--port", "8000"]
