.PHONY: dev test lint build up down

# ---------------------------------------------------------------------------
# Local development
# ---------------------------------------------------------------------------

dev:  ## Run the API locally with auto-reload
	uv run uvicorn maia_vectordb.main:app --host 0.0.0.0 --port 8000 --reload

test:  ## Run the test suite with coverage
	uv run pytest --cov=maia_vectordb --cov-report=term-missing -q

lint:  ## Run ruff linter, ruff formatter check, and mypy
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy src

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

build:  ## Build the Docker image
	docker build -t maia-vectordb .

up:  ## Start the service via docker-compose
	docker compose up -d

down:  ## Stop the service via docker-compose
	docker compose down
