# Development Guide

## Quick Start

**Local Development:**

```bash
# Install dependencies
uv sync --extra dev

# Configure environment
cp .env.example .env
# Edit .env with your actual DATABASE_URL and OPENAI_API_KEY

# Run all quality checks
uv run ruff check src tests && \
uv run mypy src && \
uv run pytest tests -v
```

**Docker Development:**

```bash
# Configure environment
cp .env.example .env
# Edit .env with your actual values

# Build and run
docker compose up --build

# Or run in background
docker compose up -d
```

## Development Workflow

### 1. Making Changes

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes to code
# ...

# Run linter (with auto-fix)
uv run ruff check --fix src tests

# Format code
uv run ruff format src tests

# Type check
uv run mypy src

# Run tests
uv run pytest tests -v
```

### 2. Writing Tests

**Test File Naming**: `test_*.py` in `tests/` directory

**Example Test**:
```python
"""Test module for feature X."""

from fastapi.testclient import TestClient
from maia_vectordb.main import app

client = TestClient(app)


def test_feature_x() -> None:
    """Feature X behaves correctly."""
    response = client.get("/api/endpoint")
    assert response.status_code == 200
    assert response.json() == {"expected": "data"}
```

**Async Tests**:
```python
import pytest
from httpx import AsyncClient
from maia_vectordb.main import app


@pytest.mark.asyncio
async def test_async_endpoint() -> None:
    """Async endpoint works correctly."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/async-endpoint")
        assert response.status_code == 200
```

**Integration Tests** (external APIs):
```python
import pytest


@pytest.mark.integration
async def test_openai_embedding() -> None:
    """OpenAI embedding service generates vectors."""
    # Test that calls external API
    ...
```

Run integration tests explicitly:
```bash
uv run pytest tests -v -m integration
```

### 3. Type Checking

**Strict Mode**: All code must pass `mypy --strict`

**Common Patterns**:
```python
# Function signatures
def process_data(items: list[str]) -> dict[str, int]:
    """Process data and return counts."""
    return {item: len(item) for item in items}

# Async functions
async def fetch_data() -> list[dict[str, Any]]:
    """Fetch data from API."""
    ...

# Optional values
from typing import Optional

def get_user(user_id: int) -> Optional[User]:
    """Get user by ID, None if not found."""
    ...
```

**Ignoring External Packages**:
Already configured in `pyproject.toml`:
```toml
[[tool.mypy.overrides]]
module = ["pgvector.*", "tiktoken.*", "asyncpg.*"]
ignore_missing_imports = true
```

### 4. Code Style

**Ruff Configuration**:
- Line length: 88 characters (Black-compatible)
- Import sorting: isort-compatible
- Rules: E (errors), F (pyflakes), I (isort)

**Import Order**:
```python
# 1. Standard library
import os
from typing import Optional

# 2. Third-party
from fastapi import FastAPI
from pydantic import BaseModel

# 3. Local application
from maia_vectordb.core.config import settings
from maia_vectordb.models.vector import Vector
```

**Docstrings**:
```python
def function_name(param: str) -> int:
    """Short description of what function does.

    Longer description if needed. Explain complex logic,
    edge cases, or important behavior.

    Args:
        param: Description of parameter.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param is invalid.
    """
    ...
```

### 5. Pre-Commit Checklist

Before committing, ensure:

✅ **Linting passes**: `uv run ruff check src tests`
✅ **Formatting correct**: `uv run ruff format --check src tests`
✅ **Types correct**: `uv run mypy src`
✅ **Tests pass**: `uv run pytest tests -v`

**One-liner**:
```bash
uv run ruff check src tests && \
uv run ruff format --check src tests && \
uv run mypy src && \
uv run pytest tests -v
```

### 6. Adding Dependencies

**Production Dependency**:
```bash
# Add to pyproject.toml dependencies
uv add package-name

# Lock and sync
uv lock
uv sync
```

**Development Dependency**:
```bash
# Add to pyproject.toml dev dependencies
uv add --dev package-name

# Sync with dev extras
uv sync --extra dev
```

**Verify Lock File**:
```bash
# Check for conflicts
uv lock --check

# Upgrade all dependencies
uv lock --upgrade
```

## Project Structure Guidelines

### Module Organization

```
src/maia_vectordb/
├── api/              # FastAPI routes
│   ├── __init__.py
│   ├── vectors.py    # /vectors CRUD endpoints
│   └── search.py     # /search similarity endpoint
├── models/           # SQLAlchemy ORM models
│   ├── __init__.py
│   └── vector.py     # Vector table model
├── schemas/          # Pydantic request/response schemas
│   ├── __init__.py
│   └── vector.py     # VectorCreate, VectorResponse, etc.
├── services/         # Business logic
│   ├── __init__.py
│   ├── embedding.py  # OpenAI embedding generation
│   └── search.py     # Similarity search logic
├── core/             # Configuration
│   ├── __init__.py
│   ├── config.py     # Settings (env vars)
│   └── logging.py    # Logging setup
└── db/               # Database
    ├── __init__.py
    ├── session.py    # Async session factory
    └── engine.py     # Async engine setup
```

### File Naming Conventions

- **Modules**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case()`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore()`

### Import Conventions

**Absolute imports only**:
```python
# Good
from maia_vectordb.models.vector import Vector
from maia_vectordb.core.config import settings

# Bad
from ..models.vector import Vector
from .config import settings
```

## Testing Guidelines

### Coverage Requirements

- **Minimum**: 80% overall coverage
- **Critical paths**: 100% coverage (API routes, business logic)
- **Infrastructure**: 60%+ coverage (database, config)

**Generate Coverage Report**:
```bash
uv run pytest tests --cov=src/maia_vectordb --cov-report=html
# Open htmlcov/index.html
```

### Test Organization

```
tests/
├── __init__.py
├── conftest.py          # Shared fixtures
├── test_api/            # API endpoint tests
│   ├── __init__.py
│   ├── test_vectors.py
│   └── test_search.py
├── test_services/       # Service layer tests
│   ├── __init__.py
│   ├── test_embedding.py
│   └── test_search.py
└── test_models/         # Database model tests
    ├── __init__.py
    └── test_vector.py
```

### Fixtures

**Database Fixtures** (`conftest.py`):
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from maia_vectordb.db.session import get_session


@pytest.fixture
async def db_session() -> AsyncSession:
    """Provide test database session."""
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost/test_db")
    async with AsyncSession(engine) as session:
        yield session
        await session.rollback()
```

**Client Fixture**:
```python
@pytest.fixture
def client() -> TestClient:
    """Provide test client."""
    from maia_vectordb.main import app
    return TestClient(app)
```

## Docker Development

### Building and Running

```bash
# Build container
docker compose build

# Run application
docker compose up

# Run in detached mode
docker compose up -d

# View logs
docker compose logs -f app

# Stop services
docker compose down

# Rebuild after dependency changes
docker compose build --no-cache
```

### Environment Configuration

**Required Setup:**
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your actual values:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/maia_vectors
   OPENAI_API_KEY=sk-your-actual-api-key-here
   EMBEDDING_MODEL=text-embedding-3-small
   CHUNK_SIZE=800
   CHUNK_OVERLAP=200
   ```

**Note:** Use `host.docker.internal` in DATABASE_URL to connect to PostgreSQL running on host machine.

### Running Commands in Container

```bash
# Run tests
docker compose run app uv run pytest tests -v

# Type check
docker compose run app uv run mypy src

# Lint
docker compose run app uv run ruff check src tests

# Interactive shell
docker compose run app /bin/bash
```

### Docker Layer Caching

The Dockerfile is optimized for fast rebuilds:
- **Dependencies change**: Only layers 2-3 rebuild (~30 seconds)
- **Source code change**: Only layer 3 rebuilds (~5 seconds)
- **No changes**: Instant startup from cache

**Force clean rebuild:**
```bash
docker compose build --no-cache
```

## Debugging

### Running Development Server

**Local (with auto-reload):**

```bash
# With auto-reload
uv run uvicorn maia_vectordb.main:app --reload --log-level debug

# Custom host/port
uv run uvicorn maia_vectordb.main:app --host 0.0.0.0 --port 8080
```

**Docker (rebuild required for code changes):**

```bash
# Run with logs
docker compose up

# Or detached
docker compose up -d && docker compose logs -f
```

### Interactive Debugging

**Using pytest**:
```bash
# Drop into debugger on failure
uv run pytest tests -v --pdb

# Drop into debugger on first failure
uv run pytest tests -v -x --pdb
```

**Using breakpoint()**:
```python
def complex_function(data: dict) -> str:
    """Complex logic that needs debugging."""
    processed = preprocess(data)
    breakpoint()  # Debugger stops here
    result = transform(processed)
    return result
```

### Logging

**Configure Logging**:
```python
import logging

logger = logging.getLogger(__name__)

def process_request(data: dict) -> None:
    """Process incoming request."""
    logger.debug(f"Processing data: {data}")
    logger.info("Request processed successfully")
    logger.error("Failed to process request")
```

**Run with Debug Logging**:
```bash
LOG_LEVEL=debug uv run uvicorn maia_vectordb.main:app --reload
```

## Common Tasks

### Update All Dependencies

```bash
# Update lock file
uv lock --upgrade

# Sync environment
uv sync --extra dev

# Verify tests still pass
uv run pytest tests -v
```

### Clean Build Artifacts

```bash
# Remove Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Remove test artifacts
rm -rf .pytest_cache htmlcov .coverage

# Remove build artifacts
rm -rf dist build *.egg-info
```

### Check Package Build

```bash
# Build wheel
uv build

# Verify contents
unzip -l dist/maia_vectordb-*.whl
```

## CI/CD Integration

**GitHub Actions Example** (`.github/workflows/test.yml`):
```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Lint
        run: uv run ruff check src tests

      - name: Type check
        run: uv run mypy src

      - name: Test
        run: uv run pytest tests -v --cov
```

## Troubleshooting

### Import Errors in Tests

**Problem**: `ModuleNotFoundError: No module named 'maia_vectordb'`

**Solution**: Use `uv run` to execute tests:
```bash
# Good
uv run pytest tests -v

# Bad (won't work unless package installed)
pytest tests -v
```

### Type Checking Errors

**Problem**: `error: Skipping analyzing "pgvector": module is installed, but missing library stubs`

**Solution**: Already configured in `pyproject.toml`:
```toml
[[tool.mypy.overrides]]
module = ["pgvector.*"]
ignore_missing_imports = true
```

### Lock File Conflicts

**Problem**: `uv.lock` merge conflicts after pull

**Solution**: Regenerate lock file:
```bash
# Discard conflicted lock
git checkout --theirs uv.lock

# Regenerate from pyproject.toml
uv lock

# Sync environment
uv sync --extra dev
```

## Resources

- [uv Documentation](https://github.com/astral-sh/uv)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Pydantic V2](https://docs.pydantic.dev/latest/)
- [pytest Documentation](https://docs.pytest.org/)
- [Ruff Rules](https://docs.astral.sh/ruff/rules/)
- [mypy Cheat Sheet](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)
