# Setup Documentation

## Initial Project Scaffold (v0.1.0)

**Status**: ✅ Complete
**Sprint**: Backend Initialization
**Date**: 2026-02-13
**Commit**: `45a594f`

### Overview

Initial project scaffolding for MAIA VectorDB, establishing repository structure, dependency management, and development tooling.

### What Was Implemented

#### 1. Repository Initialization
- Git repository at `C:/Users/DiegoPC/Documents/GitHub/maia-vectordb`
- `.gitignore` covering:
  - Python artifacts (`__pycache__`, `*.pyc`, `.mypy_cache`)
  - Virtual environments (`venv/`, `.venv/`, `env/`)
  - Environment files (`.env`, `.env.*`)
  - Testing artifacts (`.pytest_cache/`, `.coverage`)
  - Distribution files (`dist/`, `build/`, `*.egg-info/`)
  - IDE files (`.vscode/`, `.idea/`, `.DS_Store`)
  - uv-specific (`.python-version`)

#### 2. Package Configuration (`pyproject.toml`)
- **Build System**: hatchling with `src/` layout
- **Python Version**: ≥3.12
- **Package Name**: `maia-vectordb`
- **Version**: 0.1.0

**Production Dependencies (10)**:
```toml
fastapi>=0.115.0           # Web framework
uvicorn[standard]>=0.34.0  # ASGI server
sqlalchemy[asyncio]>=2.0.0 # Async ORM
asyncpg>=0.30.0            # PostgreSQL driver
pgvector>=0.3.0            # Vector operations
alembic>=1.14.0            # Migrations
tiktoken>=0.8.0            # Token counting
openai>=1.60.0             # OpenAI client
pydantic>=2.0              # Validation
python-dotenv>=1.0.0       # Environment vars
```

**Development Dependencies (6)**:
```toml
pytest>=8.0              # Testing
pytest-cov>=6.0          # Coverage
pytest-asyncio>=0.25.0   # Async tests
ruff>=0.9.0              # Linting/formatting
mypy>=1.14.0             # Type checking
httpx>=0.28.0            # HTTP client
```

#### 3. Source Layout (`src/maia_vectordb/`)

**Package Structure**:
```
src/maia_vectordb/
├── __init__.py          # "MAIA VectorDB — OpenAI-compatible vector store API."
├── main.py              # FastAPI app with /health endpoint
├── api/                 # API routes (future: /vectors, /search)
├── models/              # SQLAlchemy models (future: Vector, VectorStore)
├── schemas/             # Pydantic schemas (future: VectorCreate, VectorResponse)
├── services/            # Business logic (future: EmbeddingService, SearchService)
├── core/                # Configuration (future: settings.py, config.py)
└── db/                  # Database (future: session.py, engine.py)
```

**Entry Point (`main.py`)**:
- FastAPI app configured with title/description/version
- Health check endpoint: `GET /health` → `{"status": "ok"}`
- Modern Python typing (`dict[str, str]`)

#### 4. Testing Infrastructure

**Test Suite**:
```
tests/
├── __init__.py
└── test_health.py       # Smoke test for /health endpoint
```

**Configuration**:
- Test discovery: `tests/` directory
- Async mode: auto (pytest-asyncio)
- Test marker: `integration` for external API calls

**Current Coverage**: 1 test (health endpoint)

#### 5. Development Tooling

**Ruff Configuration**:
- Target: Python 3.12
- Source directory: `src/`
- Linting rules: E (errors), F (pyflakes), I (isort)

**Mypy Configuration**:
- Strict mode enabled
- Pydantic plugin activated
- Ignoring missing imports: `pgvector`, `tiktoken`, `asyncpg`

**Pytest Configuration**:
- Async mode: auto
- Test paths: `tests/`
- Custom markers: `integration`

#### 6. Dependency Resolution

**Lock File**: `uv.lock` (55 packages resolved)
- Total packages: 54 installed (1 local package + 53 dependencies)
- Zero conflicts or warnings
- Reproducible builds guaranteed

### Acceptance Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Git repo initialized with .gitignore | ✅ | Repository active, .gitignore covers Python/venv/.env/__pycache__/.mypy_cache |
| pyproject.toml valid with all deps | ✅ | All 10 required deps present, uv lock succeeds |
| src layout with all subpackages | ✅ | 8 files created: root + 6 subpackages (api, models, schemas, services, core, db) |
| uv lock/install succeeds | ✅ | `uv lock` → 55 packages, `uv sync --extra dev` → 54 packages, 0 errors |

### Quality Assurance

**Linting**: ✅ `ruff check src tests` → All checks passed!
**Formatting**: ✅ `ruff format --check src tests` → 10 files already formatted
**Type Checking**: ✅ `mypy src` → Success: no issues found in 8 source files
**Tests**: ✅ `uv run pytest tests -v` → 1 passed in 0.20s

### Known Limitations

1. **No Database Connection**: Database models/session management not yet implemented
2. **No API Routes**: Only health endpoint exists, vector CRUD pending
3. **No Migrations**: Alembic installed but not initialized
4. **No Configuration**: Settings/config module not created
5. **No OpenAI Integration**: Embedding service not implemented

### Next Steps

Recommended implementation order:

1. **Core Configuration** (`core/settings.py`)
   - Database URL, OpenAI API key
   - Environment variable validation
   - Logging configuration

2. **Database Layer** (`db/session.py`, `db/engine.py`)
   - Async engine + session factory
   - pgvector extension initialization
   - Connection pooling

3. **Models** (`models/vector.py`)
   - Vector table with embedding column
   - Indexes for similarity search
   - SQLAlchemy model definitions

4. **Schemas** (`schemas/vector.py`)
   - Request/response models
   - OpenAI compatibility layer

5. **Services** (`services/embedding.py`, `services/search.py`)
   - OpenAI embedding generation
   - Cosine similarity search

6. **API Routes** (`api/vectors.py`)
   - CRUD endpoints
   - Similarity search endpoint

7. **Migrations** (Alembic)
   - Initialize Alembic
   - Create initial migration

### Development Workflow

```bash
# Install dependencies
uv sync --extra dev

# Run tests (use uv run for package imports)
uv run pytest tests -v

# Type check
uv run mypy src

# Lint
uv run ruff check src tests

# Format
uv run ruff format src tests

# Run all quality checks
uv run ruff check src tests && \
uv run mypy src && \
uv run pytest tests -v
```

### File Manifest

**Configuration Files** (3):
- `.gitignore` (43 lines)
- `pyproject.toml` (62 lines)
- `uv.lock` (1473 lines, 55 packages)

**Source Files** (8):
- `src/maia_vectordb/__init__.py` (1 line docstring)
- `src/maia_vectordb/main.py` (15 lines, FastAPI app + health endpoint)
- `src/maia_vectordb/api/__init__.py` (1 line)
- `src/maia_vectordb/models/__init__.py` (1 line)
- `src/maia_vectordb/schemas/__init__.py` (1 line)
- `src/maia_vectordb/services/__init__.py` (1 line)
- `src/maia_vectordb/core/__init__.py` (1 line)
- `src/maia_vectordb/db/__init__.py` (1 line)

**Test Files** (2):
- `tests/__init__.py` (0 lines)
- `tests/test_health.py` (14 lines)

**Total**: 13 files, 1614 insertions

### Git History

```
45a594f feat: initialize project scaffolding with uv, FastAPI, and src layout
0b5b7f6 Initial commit
```

### References

- [uv documentation](https://github.com/astral-sh/uv)
- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [pgvector documentation](https://github.com/pgvector/pgvector-python)

---

## Docker Compose and Environment Configuration (v0.1.0)

**Status**: ✅ Complete
**Sprint**: Backend Initialization
**Date**: 2026-02-13
**Commit**: `6f174dd`

### Overview

Infrastructure for containerized development: Docker Compose configuration, Dockerfile with Python 3.12-slim and uv package manager, environment variable management with Pydantic BaseSettings, and comprehensive environment documentation.

### What Was Implemented

#### 1. Docker Configuration

**Dockerfile** (23 lines):
- **Base Image**: `python:3.12-slim` (minimal footprint, matches project requirements)
- **Package Manager**: uv installed via pip
- **Build Optimization**: Multi-stage dependency installation for layer caching
  - Stage 1: Copy `pyproject.toml` + `uv.lock`, install dependencies
  - Stage 2: Copy source code, install project
- **Production Mode**: `--no-dev` flag excludes development dependencies
- **Frozen Dependencies**: `--frozen` flag ensures reproducible builds from `uv.lock`
- **Entrypoint**: `uvicorn` serving FastAPI app on `0.0.0.0:8000`

**Layer Caching Strategy**:
```dockerfile
# Layer 1: Base + uv (rarely changes)
FROM python:3.12-slim
RUN pip install --no-cache-dir uv

# Layer 2: Dependencies (changes when pyproject.toml/uv.lock change)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Layer 3: Source code (changes frequently)
COPY README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev
```

**docker-compose.yml** (9 lines):
- **Services**: Single `app` service (PostgreSQL runs on host)
- **Port Mapping**: `8000:8000` (HTTP API)
- **Environment**: Loads `.env` file automatically
- **Network**: `host.docker.internal:host-gateway` for container-to-host database access
- **Build Context**: Current directory (`.`)

#### 2. Environment Configuration

**.env.example** (12 lines):
```env
# Database connection (asyncpg driver for async SQLAlchemy)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/maia_vectors

# OpenAI API key for embedding generation
OPENAI_API_KEY=sk-your-openai-api-key-here

# Embedding model (default: text-embedding-3-small)
EMBEDDING_MODEL=text-embedding-3-small

# Chunking parameters
CHUNK_SIZE=800
CHUNK_OVERLAP=200
```

**Features**:
- Inline comments explaining each variable
- Docker-ready DATABASE_URL using `host.docker.internal`
- Placeholder API key with correct format prefix (`sk-`)
- All required configuration documented

#### 3. Settings Module (`src/maia_vectordb/core/config.py`)

**Pydantic BaseSettings** (23 lines):
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration via environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/maia_vectors"
    )
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 800
    chunk_overlap: int = 200


settings = Settings()
```

**Features**:
- **Auto-Loading**: Reads `.env` file on initialization
- **Type Safety**: All fields type-annotated
- **Validation**: Pydantic validates types at runtime
- **Defaults**: Sensible fallbacks for all settings
- **Singleton**: Single `settings` instance exported
- **Environment Override**: Environment variables override defaults

**Configuration Priority** (highest to lowest):
1. Explicit environment variables (e.g., `export CHUNK_SIZE=1000`)
2. `.env` file values
3. Default values in Settings class

#### 4. Dependency Updates

**Added to `pyproject.toml`**:
```toml
dependencies = [
    # ... existing dependencies ...
    "pydantic-settings>=2.0",  # NEW
]
```

**Locked in `uv.lock`**:
- `pydantic-settings==2.12.0`
- Transitive dependencies: `typing-inspection`
- Zero conflicts, 55 total packages

#### 5. Git Configuration Update

**.gitignore** modification:
```diff
 .env
 .env.*
+!.env.example
```

**Rationale**: Ignore all `.env*` files (secrets), but explicitly track `.env.example` (documentation)

### Acceptance Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `docker-compose.yml` builds and defines app service | ✅ | Service defined with build, ports, env_file, extra_hosts |
| `Dockerfile` builds successfully | ✅ | Multi-stage build, Python 3.12-slim, uv, production mode |
| `config.py` loads all settings from env | ✅ | Pydantic BaseSettings with 5 settings: database_url, openai_api_key, embedding_model, chunk_size, chunk_overlap |
| `.env.example` documents all required vars | ✅ | All 5 variables with inline comments |

### Quality Assurance

**Linting**: ✅ `ruff check .` → All checks passed!
**Type Checking**: ✅ `mypy src` → Success: no issues found in 9 source files
**Tests**: ✅ `uv run pytest tests -v` → 1 passed in 0.86s
**Docker Build**: ✅ `docker compose build` → Built successfully

### Docker Usage

**Development Workflow**:
```bash
# First-time setup
cp .env.example .env
# Edit .env with your actual values

# Build image
docker compose build

# Run application
docker compose up

# Run in background
docker compose up -d

# View logs
docker compose logs -f app

# Stop services
docker compose down
```

**Local Development (without Docker)**:
```bash
# Create .env file
cp .env.example .env

# Update DATABASE_URL for local Postgres
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/maia_vectors

# Run directly
uv run uvicorn maia_vectordb.main:app --reload
```

### Configuration Loading Examples

**Reading settings in application code**:
```python
from maia_vectordb.core.config import settings

# Access database URL
db_url = settings.database_url

# Access OpenAI credentials
api_key = settings.openai_api_key
model = settings.embedding_model

# Access chunking parameters
chunk_size = settings.chunk_size
overlap = settings.chunk_overlap
```

**Override via environment**:
```bash
# Override chunk size for testing
CHUNK_SIZE=1000 uv run pytest tests -v

# Override in Docker
docker compose run -e CHUNK_SIZE=1000 app
```

### Known Limitations

1. **No Health Check**: Docker Compose does not define healthcheck directive
2. **No Restart Policy**: Service does not auto-restart on failure (development mode)
3. **No Volume Mounts**: Source code not mounted for hot-reload (requires rebuild)
4. **No Config Validation**: OpenAI API key format not validated at startup
5. **No Secret Management**: Production should use secret management service

### Future Enhancements

**Optional improvements for future PRs**:

1. **Add health check to docker-compose.yml**:
   ```yaml
   healthcheck:
     test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
     interval: 30s
     timeout: 3s
     retries: 3
   ```

2. **Add development volume mount**:
   ```yaml
   volumes:
     - ./src:/app/src:ro  # Read-only mount for hot-reload
   ```

3. **Add custom validators**:
   ```python
   from pydantic import field_validator

   @field_validator('openai_api_key')
   def validate_api_key(cls, v):
       if not v.startswith('sk-'):
           raise ValueError('Invalid OpenAI API key format')
       return v
   ```

4. **Add config tests**:
   ```python
   # tests/test_config.py
   def test_default_settings():
       settings = Settings()
       assert settings.chunk_size == 800
   ```

### File Manifest

**New Files** (4):
- `.env.example` (12 lines)
- `Dockerfile` (23 lines)
- `docker-compose.yml` (9 lines)
- `src/maia_vectordb/core/config.py` (23 lines)

**Modified Files** (3):
- `pyproject.toml` (+1 line: pydantic-settings)
- `uv.lock` (+16 lines: pydantic-settings resolution)
- `.gitignore` (+1 line: !.env.example exception)

**Total Changes**: 7 files, +85 lines

### Git History

```
6f174dd feat: add Docker Compose, Dockerfile, and env configuration
4607d29 docs: add comprehensive project documentation
45a594f feat: initialize project scaffolding with uv, FastAPI, and src layout
0b5b7f6 Initial commit
```

### Integration with Task 1

**Extends existing structure**:
- Uses `src/maia_vectordb/core/` package created in Task 1
- Adds to `pyproject.toml` dependencies list
- Follows established code style (ruff, mypy)
- Maintains test suite compatibility

**Enables future tasks**:
- Database services can import `settings.database_url`
- Embedding services can import `settings.openai_api_key`, `settings.embedding_model`
- Chunking logic can import `settings.chunk_size`, `settings.chunk_overlap`

### References

- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [uv Documentation](https://github.com/astral-sh/uv)

---

## Async SQLAlchemy Engine and Session Management (v0.1.0)

**Status**: ✅ Complete
**Sprint**: Backend Initialization
**Date**: 2026-02-13
**Commit**: `190a84e` + type fixes
**Dependencies**: Task 1, Task 2

### Overview

Async SQLAlchemy engine and session management infrastructure with asyncpg driver, async sessionmaker, FastAPI dependency injection for database sessions, pgvector extension registration on startup, and FastAPI lifespan event wiring for proper engine initialization and disposal.

### What Was Implemented

#### 1. Declarative Base (`src/maia_vectordb/db/base.py`)

**SQLAlchemy 2.0 DeclarativeBase** (8 lines):
```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all database models."""
```

**Purpose**: All ORM models (VectorStore, File, FileChunk) inherit from this base class.

#### 2. Async Engine and Session Management (`src/maia_vectordb/db/engine.py`)

**Features** (54 lines):
- **Async Engine Factory**: `_create_engine()` creates `AsyncEngine` from `settings.database_url`
- **Driver**: Uses `asyncpg` (specified in DATABASE_URL: `postgresql+asyncpg://...`)
- **Session Factory**: `async_sessionmaker` with `expire_on_commit=False`
- **FastAPI Dependency**: `get_db_session()` yields `AsyncSession` for route injection
- **Lifecycle Functions**:
  - `init_engine()`: Creates engine, registers pgvector extension, initializes session factory
  - `dispose_engine()`: Gracefully closes all connections and releases resources
- **pgvector Extension**: Registered via `CREATE EXTENSION IF NOT EXISTS vector` on startup
- **Error Handling**: Raises `RuntimeError` if session accessed before engine initialization
- **Type Safety**: Full type annotations with `AsyncEngine`, `AsyncSession`, `AsyncIterator`

**Key Implementation Details**:
```python
# Module-level state (singleton pattern)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_engine() -> None:
    """Initialise the async engine, register pgvector, and create session factory."""
    global _engine, _session_factory

    _engine = _create_engine()

    # Register pgvector extension
    async with _engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session (FastAPI dependency)."""
    if _session_factory is None:
        raise RuntimeError("Database engine not initialised. Call init_engine() first.")

    async with _session_factory() as session:
        yield session
```

**Configuration**:
- Database URL: From `settings.database_url` (e.g., `postgresql+asyncpg://user:pass@localhost/db`)
- Echo SQL: `echo=False` (production mode, no SQL logging)
- Session behavior: `expire_on_commit=False` (objects remain accessible after commit)

#### 3. FastAPI Lifespan Integration (`src/maia_vectordb/main.py`)

**Lifespan Context Manager** (+16 lines):
```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from maia_vectordb.db.engine import dispose_engine, init_engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown."""
    await init_engine()
    yield
    await dispose_engine()


app = FastAPI(
    title="MAIA VectorDB",
    description="OpenAI-compatible vector store API",
    version="0.1.0",
    lifespan=lifespan,  # Wire in lifecycle management
)
```

**Execution Flow**:
1. FastAPI app starts
2. `lifespan()` entered → `init_engine()` called
3. Engine created, pgvector extension registered, session factory initialized
4. `yield` → app begins serving requests
5. On shutdown → `dispose_engine()` called, connections closed

**Modern Pattern**: Uses `@asynccontextmanager` instead of deprecated `@app.on_event("startup")` / `@app.on_event("shutdown")`.

#### 4. Type Safety Fixes (Models)

**Issue**: String forward references in model relationships failed mypy type checking.

**Fix Applied**: Added `TYPE_CHECKING` imports to prevent circular import issues while satisfying mypy:

**All three model files** (file.py, vector_store.py, file_chunk.py):
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maia_vectordb.models.file import File
    from maia_vectordb.models.file_chunk import FileChunk
    from maia_vectordb.models.vector_store import VectorStore
```

**Also Fixed**:
- Removed `# noqa: F821` comments (no longer needed)
- Removed `# type: ignore[type-arg]` on embedding field
- Fixed import order in `tests/test_models.py` (ruff auto-fix)

**Result**:
- ✅ `mypy src/maia_vectordb/` → Success: no issues found in 14 source files
- ✅ `ruff check .` → All checks passed!
- ✅ All 26 tests passing

#### 5. Database Module Exports (`src/maia_vectordb/db/__init__.py`)

**Public API** (16 lines):
```python
from maia_vectordb.db.base import Base
from maia_vectordb.db.engine import (
    dispose_engine,
    get_db_session,
    init_engine,
)

__all__ = [
    "Base",
    "dispose_engine",
    "get_db_session",
    "init_engine",
]
```

**Usage in Application Code**:
```python
from maia_vectordb.db import Base, get_db_session, init_engine, dispose_engine
```

### Acceptance Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Async engine connects to `postgresql+asyncpg` URL | ✅ | `engine.py:21` — `create_async_engine(settings.database_url)` |
| `get_db_session` yields `AsyncSession` | ✅ | `engine.py:47-53` — `async with _session_factory() as session: yield session` |
| pgvector extension registered | ✅ | `engine.py:30-32` — `CREATE EXTENSION IF NOT EXISTS vector` |
| Lifespan startup/shutdown works | ✅ | `main.py:11-16` — `@asynccontextmanager` lifespan |
| `main.py` has FastAPI app with lifespan | ✅ | `main.py:19-24` — `FastAPI(lifespan=lifespan)` |

### Quality Assurance

**Linting**: ✅ `ruff check .` → All checks passed! (1 auto-fix applied)
**Type Checking**: ✅ `mypy src/maia_vectordb/` → Success: no issues found in 14 source files
**Tests**: ✅ `pytest tests/ -q` → 26 passed in 0.53s
**Package Install**: ✅ `pip install -e .` → Successfully installed maia-vectordb-0.1.0

### Usage Examples

#### Using Database Session in Routes

```python
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from maia_vectordb.db import get_db_session
from maia_vectordb.models import VectorStore


@app.get("/vector_stores")
async def list_vector_stores(
    session: AsyncSession = Depends(get_db_session),
):
    """List all vector stores."""
    result = await session.execute(select(VectorStore))
    stores = result.scalars().all()
    return stores


@app.post("/vector_stores")
async def create_vector_store(
    name: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new vector store."""
    store = VectorStore(name=name)
    session.add(store)
    await session.commit()
    await session.refresh(store)
    return store
```

#### Session Management in Services

```python
from maia_vectordb.db import get_db_session


async def some_service_function():
    """Example service using database session."""
    async for session in get_db_session():
        # Use session here
        result = await session.execute(select(VectorStore))
        stores = result.scalars().all()
        return stores
```

### Architecture Decisions

**1. Module-Level State vs. FastAPI State**:
- **Chosen**: Module-level `_engine` and `_session_factory`
- **Why**: Simpler for async SQLAlchemy, standard pattern in FastAPI docs
- **Alternative**: Could use `app.state.db_engine` (more explicit, better for testing)

**2. `expire_on_commit=False`**:
- **Why**: Prevents lazy loading errors after commit
- **Trade-off**: Objects may be stale if another process modifies data
- **Acceptable**: Most routes commit and return immediately

**3. Lifespan Pattern vs. On Event**:
- **Chosen**: `@asynccontextmanager` lifespan
- **Why**: Modern FastAPI pattern, `on_event` deprecated in FastAPI 0.93+
- **Benefit**: Cleaner async resource management

**4. pgvector Extension in Code vs. Migration**:
- **Chosen**: Register in `init_engine()` startup
- **Why**: Ensures extension exists before any queries
- **Alternative**: Could use Alembic migration (Task 4+)
- **Acceptable**: Extensions are idempotent (`IF NOT EXISTS`)

### Known Limitations

1. **No Connection Pool Configuration**: Uses SQLAlchemy defaults
2. **No Health Check for Database**: `/health` endpoint doesn't test DB connectivity
3. **No Database Migrations**: Tables not yet created (Task 4+)
4. **No Query Logging Configuration**: `echo=False` hardcoded
5. **No Retry Logic**: Engine init fails immediately if DB unreachable

### Future Enhancements

**1. Add Database Health Check**:
```python
@app.get("/health/db")
async def health_db(session: AsyncSession = Depends(get_db_session)):
    """Database connectivity check."""
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
```

**2. Configure Connection Pool**:
```python
# config.py
class Settings(BaseSettings):
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout: int = 30
    database_echo: bool = False

# engine.py
def _create_engine() -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
    )
```

**3. Add Integration Tests**:
```python
# tests/test_db_integration.py
async def test_get_db_session(db_engine):
    """Database session can be acquired."""
    async for session in get_db_session():
        assert isinstance(session, AsyncSession)


async def test_pgvector_extension_registered(db_engine):
    """pgvector extension is registered."""
    async for session in get_db_session():
        result = await session.execute(
            text("SELECT * FROM pg_extension WHERE extname = 'vector'")
        )
        assert result.fetchone() is not None
```

### File Manifest

**New Files** (2):
- `src/maia_vectordb/db/base.py` (8 lines)
- `src/maia_vectordb/db/engine.py` (54 lines)

**Modified Files** (6):
- `src/maia_vectordb/db/__init__.py` (16 lines)
- `src/maia_vectordb/main.py` (+16 lines)
- `src/maia_vectordb/models/file.py` (+5 lines TYPE_CHECKING)
- `src/maia_vectordb/models/vector_store.py` (+5 lines TYPE_CHECKING)
- `src/maia_vectordb/models/file_chunk.py` (+5 lines TYPE_CHECKING)
- `tests/test_models.py` (import order fix)

**Total Changes**: 8 files, +108 new lines, ~30 lines modified

### Integration with Previous Tasks

**Integrates with Task 2:**
- Imports `settings` from `maia_vectordb.core.config`
- Uses `settings.database_url` for engine creation
- Follows established code style (ruff, mypy)

**Integrates with Task 1:**
- All models inherit from `Base` (created in this task)
- Models already tested in `tests/test_models.py`
- TYPE_CHECKING fixes prevent circular imports

**Enables Future Tasks:**
- Task 4: Alembic migrations can import `Base` and models
- Task 5+: API routes can inject `Depends(get_db_session)` for database access
- Services can use `AsyncSession` for CRUD operations

### References

- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [pgvector Extension](https://github.com/pgvector/pgvector)
- [asyncpg Driver](https://github.com/MagicStack/asyncpg)
- [TYPE_CHECKING Pattern](https://peps.python.org/pep-0484/#runtime-or-type-checking)

---

## SQLAlchemy Database Models (v0.1.0)

**Status**: ✅ Complete
**Sprint**: Backend Initialization
**Date**: 2026-02-13
**Commit**: `1c9a232`
**Dependencies**: Task 3 (Async SQLAlchemy Engine)

### Overview

SQLAlchemy database models for vector_stores, files, and file_chunks with pgvector integration. Includes UUID primary keys, foreign key relationships with cascade delete, Vector(1536) embeddings, and HNSW index for cosine similarity search.

### What Was Implemented

#### 1. VectorStore Model (`src/maia_vectordb/models/vector_store.py`)

**Complete ORM Model** (64 lines):
```python
class VectorStoreStatus(str, enum.Enum):
    """Status of a vector store."""
    expired = "expired"
    in_progress = "in_progress"
    completed = "completed"


class VectorStore(Base):
    """A named collection of file chunks with vector embeddings."""
    __tablename__ = "vector_stores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    metadata_: Mapped[dict[str, object] | None] = mapped_column("metadata", JSON, nullable=True)
    file_counts: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[VectorStoreStatus] = mapped_column(Enum(VectorStoreStatus))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    files: Mapped[list["File"]] = relationship("File", back_populates="vector_store", cascade="all, delete-orphan")
    chunks: Mapped[list["FileChunk"]] = relationship("FileChunk", back_populates="vector_store", cascade="all, delete-orphan")
```

**Features**:
- **UUID Primary Key**: `uuid.uuid4` default factory for globally unique IDs
- **Status Enum**: Lifecycle tracking (expired, in_progress, completed)
- **Metadata Storage**: Flexible JSON columns for metadata and file_counts
- **Timestamps**: Auto-managed `created_at` and `updated_at` with timezone support
- **Optional Expiration**: `expires_at` nullable for TTL support
- **Cascade Delete**: Deleting VectorStore removes all associated Files and FileChunks

#### 2. File Model (`src/maia_vectordb/models/file.py`)

**Complete ORM Model** (59 lines):
```python
class FileStatus(str, enum.Enum):
    """Status of a file within a vector store."""
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class File(Base):
    """A file uploaded to a vector store."""
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vector_store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vector_stores.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(1024))
    status: Mapped[FileStatus] = mapped_column(Enum(FileStatus), default=FileStatus.in_progress)
    bytes: Mapped[int] = mapped_column(Integer, default=0)
    purpose: Mapped[str] = mapped_column(String(64), default="assistants")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vector_store: Mapped["VectorStore"] = relationship("VectorStore", back_populates="files")
    chunks: Mapped[list["FileChunk"]] = relationship("FileChunk", back_populates="file", cascade="all, delete-orphan")
```

**Features**:
- **Foreign Key**: Links to VectorStore with CASCADE delete
- **Status Enum**: Processing lifecycle (in_progress, completed, cancelled, failed)
- **File Metadata**: Tracks filename (1024 chars max), bytes, purpose
- **OpenAI Compatibility**: `purpose` field defaults to "assistants"
- **Cascade Delete**: Deleting File removes all associated FileChunks

#### 3. FileChunk Model (`src/maia_vectordb/models/file_chunk.py`)

**Complete ORM Model with Vector Index** (66 lines):
```python
EMBEDDING_DIMENSION = 1536


class FileChunk(Base):
    """A chunk of text from a file, with its vector embedding."""
    __tablename__ = "file_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"))
    vector_store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vector_stores.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=True)
    metadata_: Mapped[dict[str, object] | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    file: Mapped["File"] = relationship("File", back_populates="chunks")
    vector_store: Mapped["VectorStore"] = relationship("VectorStore", back_populates="chunks")

    __table_args__ = (
        Index(
            "ix_file_chunks_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
```

**Features**:
- **Dual Foreign Keys**: Links to both File and VectorStore (denormalized for query performance)
- **Vector Embeddings**: `Vector(1536)` column for OpenAI embeddings (text-embedding-3-small/large)
- **HNSW Index**: Approximate nearest neighbor search with cosine distance
  - `m=16`: Maximum connections per layer (quality vs size tradeoff)
  - `ef_construction=64`: Build-time quality parameter
  - `vector_cosine_ops`: Optimized for normalized embeddings
- **Chunk Ordering**: `chunk_index` for maintaining document order
- **Token Tracking**: `token_count` for embedding cost monitoring
- **Nullable Embedding**: Allows chunks to exist before embedding generation

#### 4. Module Exports (`src/maia_vectordb/models/__init__.py`)

**Public API** (15 lines):
```python
from maia_vectordb.models.file import File, FileStatus
from maia_vectordb.models.file_chunk import EMBEDDING_DIMENSION, FileChunk
from maia_vectordb.models.vector_store import VectorStore, VectorStoreStatus

__all__ = [
    "EMBEDDING_DIMENSION",
    "File",
    "FileChunk",
    "FileStatus",
    "VectorStore",
    "VectorStoreStatus",
]
```

**Usage**:
```python
from maia_vectordb.models import VectorStore, File, FileChunk
from maia_vectordb.models import VectorStoreStatus, FileStatus, EMBEDDING_DIMENSION
```

#### 5. Comprehensive Tests (`tests/test_models.py`)

**Test Coverage** (207 lines, 25 tests):
- **VectorStoreModel**: 6 tests (table, base, columns, PK, enum, nullable)
- **FileModel**: 6 tests (table, base, columns, PK, FK, cascade, enum)
- **FileChunkModel**: 9 tests (table, base, columns, PK, FKs, cascade, vector, HNSW)
- **ModelsImportable**: 2 tests (imports, UUID factory)

**Test Examples**:
```python
def test_uuid_primary_key() -> None:
    table = VectorStore.__table__
    assert table.c.id.type.__class__.__name__ == "Uuid"

def test_cascade_delete_on_fk() -> None:
    table = File.__table__
    for fk in table.foreign_keys:
        if str(fk.target_fullname) == "vector_stores.id":
            assert fk.ondelete == "CASCADE"

def test_vector_column_dimension() -> None:
    col = FileChunk.__table__.c.embedding
    assert col.type.dim == EMBEDDING_DIMENSION
    assert EMBEDDING_DIMENSION == 1536

def test_hnsw_index_uses_cosine_ops() -> None:
    table = FileChunk.__table__
    for idx in table.indexes:
        if idx.name == "ix_file_chunks_embedding_hnsw":
            dialect_options = idx.dialect_options.get("postgresql", {})
            assert dialect_options.get("using") == "hnsw"
            ops = dialect_options.get("ops", {})
            assert ops.get("embedding") == "vector_cosine_ops"
```

### Acceptance Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| All 3 models defined with proper columns/types | ✅ | VectorStore (8 cols), File (7 cols), FileChunk (9 cols) — all fields typed with `Mapped[T]` |
| UUID primary keys | ✅ | All models: `id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)` |
| Foreign keys with cascade delete | ✅ | File → VectorStore (`CASCADE`), FileChunk → File/VectorStore (`CASCADE`), relationships use `cascade="all, delete-orphan"` |
| Vector(1536) column on file_chunks | ✅ | `embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=True)` |
| HNSW index on embedding for cosine distance | ✅ | `ix_file_chunks_embedding_hnsw` with `postgresql_using="hnsw"`, `postgresql_ops={"embedding": "vector_cosine_ops"}` |
| Models importable from models package | ✅ | `from maia_vectordb.models import VectorStore, File, FileChunk` works |

### Quality Assurance

**Linting**: ✅ `ruff check src/maia_vectordb/models/` → All checks passed!
**Type Checking**: ✅ `mypy src/maia_vectordb/models/` → Success: no issues found in 4 source files
**Tests**: ✅ `pytest tests/test_models.py -v` → 25 passed in 0.35s

### Schema Diagram

```
┌─────────────────────────────────┐
│       vector_stores             │
├─────────────────────────────────┤
│ id: UUID (PK)                   │
│ name: String(255)               │
│ metadata_: JSON                 │
│ file_counts: JSON               │
│ status: Enum                    │
│ created_at: DateTime(tz)        │
│ updated_at: DateTime(tz)        │
│ expires_at: DateTime(tz)?       │
└────────────┬────────────────────┘
             │
             │ 1:N (CASCADE)
             │
    ┌────────▼─────────────────────┐
    │         files                │
    ├──────────────────────────────┤
    │ id: UUID (PK)                │
    │ vector_store_id: UUID (FK)   │
    │ filename: String(1024)       │
    │ status: Enum                 │
    │ bytes: Integer               │
    │ purpose: String(64)          │
    │ created_at: DateTime(tz)     │
    └────────┬─────────────────────┘
             │
             │ 1:N (CASCADE)
             │
    ┌────────▼─────────────────────────────┐
    │         file_chunks                  │
    ├──────────────────────────────────────┤
    │ id: UUID (PK)                        │
    │ file_id: UUID (FK)                   │
    │ vector_store_id: UUID (FK, denorm)   │
    │ chunk_index: Integer                 │
    │ content: Text                        │
    │ token_count: Integer                 │
    │ embedding: Vector(1536)?             │
    │ metadata_: JSON                      │
    │ created_at: DateTime(tz)             │
    ├──────────────────────────────────────┤
    │ INDEX: HNSW on embedding (cosine)    │
    └──────────────────────────────────────┘
```

### Usage Examples

#### Creating a VectorStore
```python
from maia_vectordb.models import VectorStore, VectorStoreStatus
from maia_vectordb.db import get_db_session

async with get_db_session() as session:
    vector_store = VectorStore(
        name="customer-support-docs",
        metadata_={"department": "support", "version": "1.0"},
        status=VectorStoreStatus.in_progress,
    )
    session.add(vector_store)
    await session.commit()
    await session.refresh(vector_store)
```

#### Adding a File
```python
from maia_vectordb.models import File, FileStatus

file = File(
    vector_store_id=vector_store.id,
    filename="faq.pdf",
    status=FileStatus.in_progress,
    bytes=512000,  # 500 KB
    purpose="assistants",
)
session.add(file)
await session.commit()
```

#### Adding File Chunks with Embeddings
```python
from maia_vectordb.models import FileChunk
import numpy as np

# Mock embedding (in production, use OpenAI API)
embedding_vector = np.random.rand(1536).tolist()

chunk = FileChunk(
    file_id=file.id,
    vector_store_id=vector_store.id,
    chunk_index=0,
    content="What is your return policy?",
    token_count=8,
    embedding=embedding_vector,
    metadata_={"page": 1, "section": "returns"},
)
session.add(chunk)
await session.commit()
```

#### Vector Similarity Search
```python
from sqlalchemy import select
from maia_vectordb.models import FileChunk

# Query embedding (in production, from OpenAI API)
query_embedding = np.random.rand(1536).tolist()

# Cosine similarity search using HNSW index
stmt = (
    select(FileChunk)
    .where(FileChunk.vector_store_id == vector_store.id)
    .where(FileChunk.embedding.is_not(None))
    .order_by(FileChunk.embedding.cosine_distance(query_embedding))
    .limit(10)
)
results = await session.execute(stmt)
chunks = results.scalars().all()

for chunk in chunks:
    print(f"[{chunk.chunk_index}] {chunk.content[:100]}")
```

#### Cascade Delete Demonstration
```python
# Deleting a VectorStore cascades to all Files and FileChunks
vector_store = await session.get(VectorStore, store_id)
await session.delete(vector_store)
await session.commit()

# All associated Files and FileChunks are automatically deleted
# No orphaned records remain in the database
```

### Architecture Decisions

**1. UUID Primary Keys**
- **Decision**: Use UUID v4 for all primary keys
- **Rationale**: Globally unique, non-sequential (secure), compatible with OpenAI Assistants API
- **Trade-off**: Slightly larger than INT (16 bytes vs 4 bytes), no ordering benefits

**2. Denormalized vector_store_id in FileChunks**
- **Decision**: Store `vector_store_id` directly in `file_chunks` table
- **Rationale**: Avoids JOIN when querying chunks by vector store (critical for similarity search performance)
- **Trade-off**: Redundant data, but maintains referential integrity via FK

**3. HNSW Index Parameters**
- **Decision**: `m=16`, `ef_construction=64`
- **Rationale**: Balanced quality vs build time (PostgreSQL defaults)
- **Tuning**: Increase `m` for better recall (larger index), increase `ef_construction` for better quality (slower build)

**4. Cosine Distance Operator**
- **Decision**: Use `vector_cosine_ops` for HNSW index
- **Rationale**: OpenAI embeddings are normalized (L2 norm = 1), cosine similarity = dot product for normalized vectors
- **Alternative**: Could use `vector_l2_ops` (Euclidean distance) or `vector_ip_ops` (inner product)

**5. Cascade Delete Strategy**
- **Decision**: `ondelete="CASCADE"` on FKs + `cascade="all, delete-orphan"` on relationships
- **Rationale**: Atomic cleanup — deleting VectorStore removes all Files and FileChunks
- **Behavior**: Database-level CASCADE for data integrity, SQLAlchemy-level cascade for ORM operations

**6. Nullable Embedding Column**
- **Decision**: Make `embedding` nullable
- **Rationale**: Files are uploaded → chunked → embedded (async pipeline), chunks exist before embeddings are generated
- **Query**: Filter `WHERE embedding IS NOT NULL` for similarity search

### Performance Considerations

**1. HNSW Index Build Time**
- Index builds during migration (`CREATE INDEX`)
- Build time ∝ dataset size × `ef_construction`
- **Recommendation**: Build index after bulk insert, or use `CREATE INDEX CONCURRENTLY`

**2. Query Performance**
- HNSW approximate k-NN: O(log N) expected time
- Exact k-NN (no index): O(N) linear scan
- **Optimization**: Filter by `vector_store_id` before ORDER BY for best performance

**3. Storage Estimation**
- Vector(1536) = 6 KB per chunk (1536 floats × 4 bytes)
- HNSW index adds ~20-30% overhead
- **Estimate**: 1M chunks ≈ 8 GB (vectors + index)

**4. Cascade Delete Performance**
- PostgreSQL uses FK triggers (one DELETE → N child DELETEs)
- Can be slow for large hierarchies (10K+ chunks)
- **Recommendation**: Monitor `pg_stat_user_tables` for bloat, consider batch deletion for large stores

### Integration with Previous Tasks

**Integrates with Task 3:**
- Models inherit from `Base` (created in Task 3)
- Can be used with `get_db_session()` dependency
- Ready for Alembic migrations

**Enables Future Tasks:**
- **Task 5**: Alembic migrations will auto-generate schema from these models
- **Task 6**: API routes can perform CRUD operations using these models
- **Task 7**: Embedding service can insert FileChunks with vectors
- **Task 8**: Vector search service can query using HNSW index

### File Manifest

**New Files** (4):
- `src/maia_vectordb/models/vector_store.py` (64 lines)
- `src/maia_vectordb/models/file.py` (59 lines)
- `src/maia_vectordb/models/file_chunk.py` (66 lines)
- `tests/test_models.py` (207 lines)

**Modified Files** (1):
- `src/maia_vectordb/models/__init__.py` (15 lines)

**Total Changes**: 5 files, 411 lines added

### References

- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [pgvector-python](https://github.com/pgvector/pgvector-python)
- [HNSW Algorithm Paper](https://arxiv.org/abs/1603.09320)
- [OpenAI Assistants API](https://platform.openai.com/docs/assistants/overview)
- [PostgreSQL Indexes](https://www.postgresql.org/docs/current/indexes.html)
