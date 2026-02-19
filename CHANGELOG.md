# Changelog

All notable changes to MAIA VectorDB will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **X-API-Key authentication**: All `/v1/*` routes now require a valid `X-API-Key` request header.
  Configure accepted keys via the `API_KEYS` environment variable (comma-separated list).
  The `/health` endpoint remains unauthenticated for liveness/readiness probes.
  The server refuses to start if `API_KEYS` is empty.

### Changed
- **Async embedding service** (`services/embedding.py`): Migrated from `openai.OpenAI`
  (synchronous) to `openai.AsyncOpenAI`. The `embed_texts` and `_call_with_retry` functions
  are now `async`; the retry back-off uses `asyncio.sleep()` instead of `time.sleep()`.
  This eliminates event-loop blocking during embedding API calls and back-offs, allowing
  concurrent requests to be served normally even while retrying transient OpenAI errors.
  Call sites in `api/files.py` and `api/search.py` updated to `await embed_texts(...)`.

### Planned
- Metadata filtering improvements
- Batch file upload support
- Query result caching
- Rate limiting

## [0.1.0] - 2024-02-13

### Added
- Initial release of MAIA VectorDB
- OpenAI-compatible vector store API
- Vector store CRUD operations (create, list, retrieve, delete)
- File upload and processing with automatic chunking and embedding
- Background processing for large files (>50 KB)
- Semantic search with cosine similarity using pgvector HNSW indexes
- Metadata filtering support in search queries
- Health check endpoint with database connectivity status
- Interactive OpenAPI documentation at `/docs`
- Error handling middleware with consistent error responses
- Request logging with correlation IDs
- Docker support with optimized multi-stage build
- PostgreSQL database with pgvector extension support
- Async SQLAlchemy 2.0 with asyncpg driver
- Alembic database migrations
- Text chunking service with recursive separator strategy
- OpenAI embedding service with retry logic and batching
- Comprehensive test suite with 80%+ coverage
- Development and deployment documentation

### Technical Stack
- **Framework**: FastAPI 0.115+
- **Database**: PostgreSQL 14+ with pgvector extension
- **ORM**: SQLAlchemy 2.0 (async)
- **Embeddings**: OpenAI API (text-embedding-3-small)
- **Chunking**: Recursive text splitter with tiktoken
- **Python**: 3.12+
- **Package Manager**: uv

### Database Schema
- `vector_stores` - Named collections of file chunks with embeddings
- `files` - Uploaded files with processing status tracking
- `file_chunks` - Text chunks with 1536-dimension vector embeddings
- HNSW index on embeddings for fast similarity search

### API Endpoints
- `GET /health` - Health check with database status
- `POST /v1/vector_stores` - Create vector store
- `GET /v1/vector_stores` - List vector stores (with pagination)
- `GET /v1/vector_stores/{id}` - Retrieve vector store
- `DELETE /v1/vector_stores/{id}` - Delete vector store
- `POST /v1/vector_stores/{id}/files` - Upload file for processing
- `GET /v1/vector_stores/{vector_store_id}/files/{file_id}` - Get file status
- `POST /v1/vector_stores/{id}/search` - Semantic similarity search

### Configuration
- Environment-based configuration via Pydantic Settings
- Support for `.env` files
- Configurable chunking parameters (chunk size, overlap)
- Configurable embedding model
- Database connection pooling settings

### Development
- Ruff for linting and formatting
- mypy for strict type checking
- pytest with async support
- Coverage reporting
- Docker Compose for local development
- Comprehensive test fixtures and helpers

### Documentation
- Quick start guide
- Development guide with testing and debugging tips
- Deployment guide for Docker and cloud platforms
- Contributing guidelines
- Detailed API documentation
- Database schema documentation

[0.1.0]: https://github.com/yourusername/maia-vectordb/releases/tag/v0.1.0
