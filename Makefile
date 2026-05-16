# Requires: uv, Git Bash / WSL (Windows) or any POSIX shell
.DEFAULT_GOAL := help
.PHONY: help install dev dashboard mcp init-db sync demo auth \
        lint format type-check test test-cov check \
        up docker-build docker-up docker-down docker-logs docker-shell \
        n8n-up n8n-down n8n-logs \
        clean

# ─── Help ────────────────────────────────────────────────────────────────────
help:
	@echo "Polar Dashboard — available targets:"
	@echo ""
	@echo "  Development"
	@echo "    install       Install all dependencies (including dev)"
	@echo "    dashboard     Start the Streamlit dashboard  (localhost:8501)"
	@echo "    mcp           Start the MCP server"
	@echo "    init-db       Initialise / migrate the DuckDB database"
	@echo "    sync          Run a headless Polar data sync"
	@echo "    auth          Run the OAuth2 callback server for token acquisition"
	@echo "    demo          Seed synthetic data (no Polar account needed)"
	@echo ""
	@echo "  Quality"
	@echo "    test          Run the test suite (quiet)"
	@echo "    test-cov      Run tests with coverage report (fail under 90 %)"
	@echo "    lint          Lint and check imports with ruff"
	@echo "    format        Auto-format with ruff"
	@echo "    type-check    Static type-check with mypy"
	@echo "    check         lint + type-check + test-cov"
	@echo ""
	@echo "  Docker"
	@echo "    up            Start all services, auto-patch .env with tunnel URL, restart n8n"
	@echo "    docker-build  Build the production Docker image"
	@echo "    docker-up     Start all services (dashboard + n8n) via docker compose"
	@echo "    docker-down   Stop all containers"
	@echo "    docker-logs   Tail dashboard container logs"
	@echo "    docker-shell  Open a shell inside the running dashboard container"
	@echo ""
	@echo "  n8n (Telegram bridge)"
	@echo "    n8n-up        Start only the n8n container"
	@echo "    n8n-down      Stop only the n8n container"
	@echo "    n8n-logs      Tail n8n container logs"
	@echo ""
	@echo "  Housekeeping"
	@echo "    clean         Remove caches, coverage artefacts, and .pyc files"

# ─── Development ─────────────────────────────────────────────────────────────
install:
	uv sync

dev:
	uv sync

dashboard:
	uv run streamlit run src/ui/streamlit/app.py

mcp:
	uv run python -m polar_mcp.server

init-db:
	uv run python scripts/init_db.py

sync:
	uv run python scripts/run_sync.py

auth:
	uv run python scripts/polar_auth.py

demo:
	uv run python scripts/seed_demo_data.py

# ─── Quality ─────────────────────────────────────────────────────────────────
lint:
	uv run ruff check src tests configs

format:
	uv run ruff format src tests configs
	uv run ruff check --fix src tests configs

type-check:
	uv run mypy src

test:
	uv run pytest tests/ -q

test-cov:
	uv run pytest tests/ --cov=src --cov-report=term-missing -q

check: lint type-check test-cov

# ─── Docker ──────────────────────────────────────────────────────────────────
up:
	bash scripts/tunnel_up.sh

docker-build:
	docker build --target runtime -t polar-dashboard:latest .

docker-up:
	docker compose up -d
	@echo "Dashboard → http://localhost:8501"

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f dashboard

docker-shell:
	docker compose exec dashboard /bin/bash

# ─── n8n ─────────────────────────────────────────────────────────────────────
n8n-up:
	docker compose up -d n8n
	@echo "n8n → http://localhost:5678"

n8n-down:
	docker compose stop n8n

n8n-logs:
	docker compose logs -f n8n

# ─── Housekeeping ────────────────────────────────────────────────────────────
clean:
	uv run python -c "\
import shutil, pathlib; \
[shutil.rmtree(p, ignore_errors=True) \
 for pattern in ['__pycache__', '.pytest_cache', '.mypy_cache', 'htmlcov', '*.egg-info'] \
 for p in pathlib.Path('.').rglob(pattern)]"
	-rm -f .coverage
