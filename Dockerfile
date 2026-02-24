# ---- builder stage ----
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no project itself yet)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source and README (needed by hatchling build)
COPY README.md ./
COPY src/ src/

# Install the project itself, then strip test data to reduce image size
RUN uv sync --frozen --no-dev \
    && find .venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; \
       find .venv -type d -name "tests"       -exec rm -rf {} + 2>/dev/null; \
       find .venv -type d -name "test"        -exec rm -rf {} + 2>/dev/null; \
       find .venv -name "*.pyc" -delete 2>/dev/null; \
       find .venv -name "*.pyi" -delete 2>/dev/null; \
       find .venv -name "*.so" -exec strip --strip-unneeded {} \; 2>/dev/null; \
       rm -rf .venv/lib/python3.12/site-packages/numpy/doc \
              .venv/lib/python3.12/site-packages/numpy/f2py \
              .venv/lib/python3.12/site-packages/numpy/_core/include 2>/dev/null; \
       true

# Pre-download tiktoken encoding data at build time so it's baked into the
# image and never needs a network fetch at runtime.
ENV TIKTOKEN_CACHE_DIR=/app/.tiktoken_cache
RUN mkdir -p /app/.tiktoken_cache \
    && .venv/bin/python -c "import tiktoken; tiktoken.encoding_for_model('gpt-4o')"

# ---- runtime stage ----
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Copy the virtual environment, source, and tiktoken cache from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/.tiktoken_cache /app/.tiktoken_cache

# Ensure venv binaries are on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV TIKTOKEN_CACHE_DIR=/app/.tiktoken_cache

# Switch to non-root user
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["uvicorn", "maia_vectordb.main:app", "--host", "0.0.0.0", "--port", "8000"]
