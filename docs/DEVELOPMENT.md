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

## Text Chunking & Embedding Services

### Chunking Service (`services/chunking.py`)

**Purpose**: Split long documents into token-limited chunks with overlap to prevent context loss.

**Key Features**:
- Recursive separator strategy: `\n\n` → `\n` → ` ` → character-level
- Accurate token counting using `tiktoken` (same as OpenAI)
- Configurable chunk size (default 800 tokens) and overlap (default 200 tokens)
- Supports `.txt` and `.md` files

**Usage Example**:
```python
from maia_vectordb.services.chunking import split_text, read_file

# Split text into chunks
text = "Your long document here..."
chunks = split_text(
    text,
    chunk_size=800,      # Max tokens per chunk (default from settings)
    chunk_overlap=200,   # Overlapping tokens (default from settings)
)

# Read and validate file
content = read_file("document.txt")  # Supports .txt and .md only
chunks = split_text(content)
```

**Configuration** (via `core/config.py`):
```python
# .env file
CHUNK_SIZE=800           # Max tokens per chunk
CHUNK_OVERLAP=200        # Overlapping tokens between chunks
```

**How it Works**:
1. Tries to split on paragraph boundaries (`\n\n`) first
2. Falls back to line boundaries (`\n`) if paragraphs too large
3. Falls back to word boundaries (` `) if lines too large
4. Falls back to character-level splitting as last resort
5. Maintains overlap by taking trailing tokens from previous chunk

### Embedding Service (`services/embedding.py`)

**Purpose**: Generate vector embeddings for text chunks using OpenAI's embedding API.

**Key Features**:
- Batching at max 2048 inputs per request (OpenAI limit)
- Exponential backoff retry (1s → 2s → 4s → 8s → 16s)
- Retries on rate limits (429) and transient errors (5xx, connection errors)
- Non-retryable errors (401, 403) raise immediately
- Integration function `chunk_and_embed()` combines chunking + embedding

**Usage Example**:
```python
from maia_vectordb.services.embedding import embed_texts, chunk_and_embed

# Embed a list of texts
texts = ["Hello world", "Another text"]
embeddings = embed_texts(texts, model="text-embedding-3-small")
# Returns: list[list[float]] - one 1536-dim vector per text

# One-liner: chunk and embed in one step
text = "Your long document here..."
result = chunk_and_embed(
    text,
    chunk_size=800,
    chunk_overlap=200,
    model="text-embedding-3-small",
)
# Returns: list[tuple[str, list[float]]] - (chunk_text, embedding_vector) pairs
```

**Configuration** (via `core/config.py`):
```python
# .env file
OPENAI_API_KEY=sk-your-api-key-here
EMBEDDING_MODEL=text-embedding-3-small  # or text-embedding-ada-002
```

**Retry Logic**:
- Retries on: 429 (rate limit), 500, 502, 503, 504 (server errors), connection errors
- Max 5 retries with exponential backoff
- Backoff: 1s → 2s → 4s → 8s → 16s
- Non-retryable errors raise immediately (401, 403, etc.)

**Batching**:
- Automatically splits large inputs into batches of 2048 texts
- Preserves input order in output
- Example: 2058 texts → 2 API calls (2048 + 10)

**Integration Test** (requires API key):
```python
import pytest

@pytest.mark.integration
def test_chunk_and_embed_real_api() -> None:
    """Integration test with real OpenAI API (requires OPENAI_API_KEY)."""
    from maia_vectordb.services.embedding import chunk_and_embed

    text = "This is a test document. " * 100  # ~200 tokens
    result = chunk_and_embed(text, chunk_size=100, chunk_overlap=20)

    assert len(result) >= 2  # Should split into multiple chunks
    for chunk_text, embedding in result:
        assert len(embedding) == 1536  # text-embedding-3-small dimension
        assert chunk_text  # Non-empty text

# Run integration tests
# uv run pytest tests -v -m integration
```

## Database Schema

### Tables

**VectorStore** - Named collection of file chunks with vector embeddings
- `id` (UUID, PK)
- `name` (String)
- `metadata_` (JSON)
- `file_counts` (JSON)
- `status` (Enum: expired, in_progress, completed)
- `created_at`, `updated_at`, `expires_at` (DateTime)

**File** - File uploaded to a vector store
- `id` (UUID, PK)
- `vector_store_id` (UUID, FK → vector_stores.id, CASCADE)
- `filename` (String)
- `status` (Enum: in_progress, completed, cancelled, failed)
- `bytes` (Integer)
- `purpose` (String)
- `created_at` (DateTime)

**FileChunk** - Text chunk from file with vector embedding
- `id` (UUID, PK)
- `file_id` (UUID, FK → files.id, CASCADE)
- `vector_store_id` (UUID, FK → vector_stores.id, CASCADE)
- `chunk_index` (Integer)
- `content` (Text)
- `token_count` (Integer)
- `embedding` (Vector(1536)) - pgvector column with HNSW index
- `metadata_` (JSON)
- `created_at` (DateTime)

**Indexes:**
- `ix_file_chunks_embedding_hnsw` - HNSW index on embedding column for fast cosine similarity search

### Connection Pooling

Configured in `src/maia_vectordb/db/engine.py`:
- **Pool size**: 5 base connections
- **Max overflow**: 10 additional connections (15 total max)
- **Pre-ping**: Health checks before using connections
- **Recycle**: Recycle connections after 300 seconds

### Startup DDL

Tables and pgvector extension are created automatically on application startup via `init_engine()`:
1. `CREATE EXTENSION IF NOT EXISTS vector`
2. `Base.metadata.create_all()` - creates all tables

## API Endpoints

### Vector Store CRUD (`/v1/vector_stores`)

**Create Vector Store** - `POST /v1/vector_stores`

Create a new vector store with optional name and metadata.

```bash
curl -X POST http://localhost:8000/v1/vector_stores \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Documents",
    "metadata": {"project": "demo"}
  }'
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "object": "vector_store",
  "name": "My Documents",
  "status": "completed",
  "file_counts": {
    "in_progress": 0,
    "completed": 0,
    "cancelled": 0,
    "failed": 0,
    "total": 0
  },
  "metadata": {"project": "demo"},
  "created_at": 1707868800,
  "updated_at": 1707868800,
  "expires_at": null
}
```

**List Vector Stores** - `GET /v1/vector_stores`

List all vector stores with pagination support.

Query Parameters:
- `limit` (1-100, default: 20) - Number of results per page
- `offset` (≥0, default: 0) - Number of results to skip
- `order` ("asc" | "desc", default: "desc") - Sort order by created_at

```bash
curl "http://localhost:8000/v1/vector_stores?limit=10&offset=0&order=desc"
```

Response:
```json
{
  "object": "list",
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "object": "vector_store",
      "name": "My Documents",
      "status": "completed",
      "file_counts": {...},
      "metadata": {"project": "demo"},
      "created_at": 1707868800,
      "updated_at": 1707868800,
      "expires_at": null
    }
  ],
  "first_id": "550e8400-e29b-41d4-a716-446655440000",
  "last_id": "550e8400-e29b-41d4-a716-446655440000",
  "has_more": false
}
```

**Get Vector Store** - `GET /v1/vector_stores/{id}`

Retrieve a single vector store by ID.

```bash
curl http://localhost:8000/v1/vector_stores/550e8400-e29b-41d4-a716-446655440000
```

Response: Same as create response (200 OK) or 404 Not Found.

**Delete Vector Store** - `DELETE /v1/vector_stores/{id}`

Delete a vector store and all associated files and chunks (cascade delete).

```bash
curl -X DELETE http://localhost:8000/v1/vector_stores/550e8400-e29b-41d4-a716-446655440000
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "object": "vector_store.deleted",
  "deleted": true
}
```

### File Upload & Processing (`/v1/vector_stores/{id}/files`)

**Upload File** - `POST /v1/vector_stores/{vector_store_id}/files`

Upload a file (or raw text) to a vector store. The file is chunked, embedded, and stored as searchable vectors. Large files (>50 KB) are processed in the background.

**File Upload (multipart/form-data):**
```bash
curl -X POST http://localhost:8000/v1/vector_stores/550e8400-e29b-41d4-a716-446655440000/files \
  -F "file=@document.txt"
```

**Raw Text Upload:**
```bash
curl -X POST http://localhost:8000/v1/vector_stores/550e8400-e29b-41d4-a716-446655440000/files \
  -F "text=Your raw text content here"
```

Response (small file - processed inline):
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "object": "vector_store.file",
  "vector_store_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.txt",
  "status": "completed",
  "bytes": 1024,
  "chunk_count": 3,
  "purpose": "assistants",
  "created_at": 1707868900
}
```

Response (large file - background processing):
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440002",
  "object": "vector_store.file",
  "vector_store_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "large_document.txt",
  "status": "in_progress",
  "bytes": 75000,
  "chunk_count": 0,
  "purpose": "assistants",
  "created_at": 1707868900
}
```

**Processing Behavior:**
- Files ≤50 KB: Processed inline, returns `status: "completed"` with chunk count
- Files >50 KB: Processed in background, returns `status: "in_progress"` (use GET endpoint to poll)
- Errors: Returns `status: "failed"` if chunking/embedding fails

**Get File Status** - `GET /v1/vector_stores/{vector_store_id}/files/{file_id}`

Retrieve a file's processing status and chunk count (useful for polling background uploads).

```bash
curl http://localhost:8000/v1/vector_stores/550e8400-e29b-41d4-a716-446655440000/files/660e8400-e29b-41d4-a716-446655440002
```

Response:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440002",
  "object": "vector_store.file",
  "vector_store_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "large_document.txt",
  "status": "completed",
  "bytes": 75000,
  "chunk_count": 95,
  "purpose": "assistants",
  "created_at": 1707868900
}
```

**Implementation Details:**
- **Chunking**: Uses `split_text()` from chunking service with recursive separator strategy
- **Embedding**: Uses `embed_texts()` from embedding service (OpenAI API)
- **Bulk Insert**: Uses `session.add_all()` for efficient batch insertion of 100+ chunks
- **Background Processing**: Uses FastAPI `BackgroundTasks` for large files
- **Session Management**: Background tasks create their own sessions via `get_session_factory()`

### Similarity Search (`/v1/vector_stores/{id}/search`)

**Search Vector Store** - `POST /v1/vector_stores/{vector_store_id}/search`

Perform semantic similarity search over a vector store using cosine similarity.

Request body:
```json
{
  "query": "What is machine learning?",
  "max_results": 10,
  "filter": {"category": "science"},
  "score_threshold": 0.8
}
```

Parameters:
- `query` (string, required) - Text query to search for
- `max_results` (integer, optional, default: 10, range: 1-100) - Maximum number of results
- `filter` (object, optional) - Metadata filters (key-value pairs, AND logic)
- `score_threshold` (float, optional, range: 0.0-1.0) - Minimum similarity score

```bash
curl -X POST http://localhost:8000/v1/vector_stores/550e8400-e29b-41d4-a716-446655440000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning applications",
    "max_results": 5,
    "filter": {"category": "science", "lang": "en"},
    "score_threshold": 0.7
  }'
```

Response:
```json
{
  "object": "list",
  "data": [
    {
      "file_id": "660e8400-e29b-41d4-a716-446655440001",
      "filename": "ml_guide.txt",
      "chunk_index": 0,
      "content": "Machine learning is a subset of artificial intelligence...",
      "score": 0.92,
      "metadata": {"category": "science", "lang": "en"}
    },
    {
      "file_id": "660e8400-e29b-41d4-a716-446655440002",
      "filename": "ai_intro.txt",
      "chunk_index": 2,
      "content": "Applications of ML include computer vision, NLP...",
      "score": 0.85,
      "metadata": {"category": "science", "lang": "en"}
    }
  ],
  "search_query": "machine learning applications"
}
```

**How It Works:**
1. Query text is embedded on-the-fly using OpenAI's embedding API
2. Cosine similarity search performed using pgvector's `<=>` operator
3. Metadata filters applied as SQL WHERE clauses (JSON containment)
4. Score threshold filters out low-relevance results
5. Results ranked by similarity score (highest first)

**Implementation Details:**
- **Query Embedding**: Generated on-the-fly via `embed_texts([query])[0]`
- **Similarity Metric**: Cosine distance (pgvector `<=>` operator), converted to score: `1 - distance`
- **Metadata Filtering**: Uses `metadata->>'key' = 'value'` SQL clauses (multiple filters combined with AND)
- **Score Threshold**: Applied as distance threshold: `distance <= 1 - threshold`
- **Performance**: HNSW index on embedding column enables fast approximate nearest neighbor search

---

## Error Handling & Middleware

### Exception Hierarchy (`core/exceptions.py`)

**Purpose**: Provide a consistent exception hierarchy with proper HTTP status code mapping.

**Exception Classes**:
- `APIError` (base, 500) - Base exception for all API errors
- `NotFoundError` (404) - Resource not found
- `ValidationError` (400) - Invalid request input
- `EmbeddingServiceError` (502) - Embedding service unavailable
- `DatabaseError` (503) - Database operation failed

**Usage Example**:
```python
from maia_vectordb.core.exceptions import NotFoundError, ValidationError

# Raise custom exceptions in your code
def get_vector_store(store_id: UUID) -> VectorStore:
    """Get vector store by ID."""
    store = session.get(VectorStore, store_id)
    if not store:
        raise NotFoundError(f"Vector store {store_id} not found")
    return store

# Validation errors
if not filename.endswith(('.txt', '.md')):
    raise ValidationError("Only .txt and .md files supported")
```

### Global Exception Handlers (`core/handlers.py`)

All exceptions are converted to a consistent JSON error envelope:

```json
{
  "error": {
    "message": "Resource not found",
    "type": "not_found",
    "code": 404
  }
}
```

**Handlers**:
- `api_error_handler` - Handles all `APIError` subclasses
- `http_exception_handler` - Wraps FastAPI/Starlette `HTTPException`
- `validation_exception_handler` - Wraps Pydantic `RequestValidationError`
- `unhandled_exception_handler` - Catch-all for unexpected exceptions (never leaks stack traces)

### Middleware (`core/middleware.py`)

**RequestIDMiddleware**:
- Generates/echoes `X-Request-ID` header for correlation
- Stores request ID in `request.state.request_id`
- Useful for distributed tracing and log correlation

**RequestLoggingMiddleware**:
- Logs every request: method, path, status code, duration, request ID
- Acts as outermost safety net catching unhandled exceptions
- Returns safe 500 JSON response on unhandled errors (no stack trace leaks)

**Log Format**:
```
2025-02-13T10:30:45 INFO [maia_vectordb.core.middleware] GET /v1/vector_stores 200 45.2ms [request_id=abc-123]
```

### Structured Logging (`core/logging_config.py`)

**Configuration**:
```python
from maia_vectordb.core.logging_config import setup_logging

# Configure at app startup (already done in main.py)
setup_logging(level=logging.INFO)

# Use in your modules
import logging
logger = logging.getLogger(__name__)

logger.info("Processing file upload")
logger.warning("Rate limit approaching")
logger.error("Failed to connect to embedding service")
```

**Log Format**:
```
%(asctime)s %(levelname)s [%(name)s] %(message)s
```

**Production Mode**:
- Stack traces are never leaked to clients
- Internal errors logged server-side with full traceback
- Clients receive safe "Internal server error" message

## Project Structure Guidelines

### Module Organization

```
src/maia_vectordb/
├── api/              # FastAPI routes
│   ├── __init__.py
│   ├── vector_stores.py  # Vector store CRUD endpoints
│   └── files.py          # File upload & processing endpoints
├── models/           # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── vector_store.py  # VectorStore model
│   ├── file.py          # File model
│   └── file_chunk.py    # FileChunk model with pgvector
├── schemas/          # Pydantic request/response schemas
│   ├── __init__.py
│   ├── vector_store.py  # Vector store schemas
│   └── file.py          # File schemas
├── services/         # Business logic
│   ├── __init__.py
│   ├── chunking.py   # Recursive text splitter
│   └── embedding.py  # OpenAI embedding generation
├── core/             # Configuration & error handling
│   ├── __init__.py
│   ├── config.py        # Settings (env vars)
│   ├── exceptions.py    # Custom exception hierarchy
│   ├── handlers.py      # Global exception handlers
│   ├── middleware.py    # Request logging & ID middleware
│   └── logging_config.py # Structured logging setup
└── db/               # Database
    ├── __init__.py
    ├── base.py       # SQLAlchemy Base
    └── engine.py     # Async engine + session factory
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
