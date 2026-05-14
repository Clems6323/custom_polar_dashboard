# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — dependency installation
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first so this layer is cached until they change
COPY pyproject.toml uv.lock ./

# Create a virtual environment and install production dependencies only.
# --frozen ensures the exact versions in uv.lock are used.
# --no-dev skips test/lint tooling.
# --no-editable prevents installing the project itself as a package
# (source is provided via PYTHONPATH at runtime instead).
RUN uv sync --frozen --no-dev --no-editable


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — runtime image (lean, no build tools)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# curl is needed only for the HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the pre-built virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY src/       ./src/
COPY configs/   ./configs/
COPY docs/      ./docs/

# Ensure default data directories exist.
# At runtime these are overridden by the volume mount defined in docker-compose.
RUN mkdir -p data/tokens data/parquet

# Activate the virtual environment and expose source to Python
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:/app"

# Streamlit port
EXPOSE 8501

# Verify the app responds within 30 s of startup
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "src/ui/streamlit/app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
