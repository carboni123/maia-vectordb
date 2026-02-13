# Review: Health Check & OpenAPI Documentation

**Status**: ✅ Complete
**Date**: 2026-02-13
**Task ID**: Health Check & OpenAPI Documentation

## Overview

Implemented health check endpoint and enhanced OpenAPI documentation with proper configuration, tag groupings, and request/response examples.

## Implementation Summary

### 1. Health Check Endpoint (`GET /health`)

**Location**: `src/maia_vectordb/main.py`

**Features**:
- Returns service status with version information
- Database connectivity check via `SELECT 1` query
- OpenAI API key presence check (flag only, not validation)
- Returns HTTP 200 for healthy state, 503 for degraded state
- Proper error handling with detailed error messages

**Response Schema**: `src/maia_vectordb/schemas/health.py`
- `ComponentHealth` - Individual component status
- `HealthResponse` - Overall health status with all components

**Example Response (Healthy)**:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": {
    "status": "ok",
    "detail": null
  },
  "openai_api_key_set": true
}
```

**Example Response (Degraded)**:
```json
{
  "status": "degraded",
  "version": "0.1.0",
  "database": {
    "status": "error",
    "detail": "Connection refused"
  },
  "openai_api_key_set": false
}
```

### 2. OpenAPI Configuration

**Location**: `src/maia_vectordb/main.py`

**Enhancements**:
- Added comprehensive API metadata (title, description, version)
- Configured tag metadata for all endpoint groups:
  - `health` - Service health checks and status monitoring
  - `vector_stores` - Create, list, retrieve, and delete vector stores
  - `files` - Upload documents and check processing status
  - `search` - Similarity search over vector store embeddings
- Proper OpenAPI responses configuration on health endpoint

**FastAPI App Configuration**:
```python
app = FastAPI(
    title="MAIA VectorDB",
    description=(
        "OpenAI-compatible vector store API service powered by PostgreSQL "
        "and pgvector. Provides endpoints for creating vector stores, "
        "uploading documents with automatic chunking and embedding, "
        "and performing similarity search."
    ),
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=TAG_METADATA,
)
```

### 3. Request/Response Examples

**Location**: All schema files in `src/maia_vectordb/schemas/`

**Updated Files**:
- `health.py` - Health check schemas with examples
- `vector_store.py` - Vector store CRUD schemas with examples
- `file.py` - File upload schemas with examples
- `search.py` - Search request/response schemas with examples

**Example Configuration**:
```python
class HealthResponse(BaseModel):
    """Response body for the health check endpoint."""

    status: str
    version: str
    database: ComponentHealth
    openai_api_key_set: bool

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "ok",
                    "version": "0.1.0",
                    "database": {"status": "ok", "detail": None},
                    "openai_api_key_set": True,
                }
            ]
        }
    }
```

### 4. Documentation Endpoints

- **Swagger UI**: Available at `/docs`
- **ReDoc**: Available at `/redoc`
- **OpenAPI JSON**: Available at `/openapi.json`

All endpoints are properly documented with:
- Request/response schemas
- Example payloads
- Status codes and descriptions
- Tag groupings for organization

## Tests

**Location**: `tests/test_health.py`

**Coverage**: 12 tests covering:

### Health Endpoint Tests (6 tests):
1. `test_health_ok_when_db_reachable` - Returns 200 with status=ok when database is reachable
2. `test_health_503_when_db_unreachable` - Returns 503 with status=degraded when database unreachable
3. `test_health_503_when_session_query_fails` - Returns 503 when SELECT 1 query fails
4. `test_health_openai_key_flag_true` - Reports openai_api_key_set=True when key is configured
5. `test_health_openai_key_flag_false` - Reports openai_api_key_set=False when key is empty
6. `test_health_response_structure` - Validates response contains all expected keys

### OpenAPI Documentation Tests (6 tests):
1. `test_swagger_ui_accessible` - Swagger UI renders at /docs
2. `test_redoc_accessible` - ReDoc renders at /redoc
3. `test_openapi_schema_metadata` - OpenAPI schema has correct title, description, version
4. `test_openapi_tags_present` - OpenAPI schema includes all tag descriptions
5. `test_openapi_all_endpoints_present` - All API endpoints appear in OpenAPI schema
6. `test_openapi_schema_has_examples` - All schemas include examples from json_schema_extra

**Test Results**:
```bash
tests/test_health.py::TestHealthEndpoint::test_health_ok_when_db_reachable PASSED
tests/test_health.py::TestHealthEndpoint::test_health_503_when_db_unreachable PASSED
tests/test_health.py::TestHealthEndpoint::test_health_503_when_session_query_fails PASSED
tests/test_health.py::TestHealthEndpoint::test_health_openai_key_flag_true PASSED
tests/test_health.py::TestHealthEndpoint::test_health_openai_key_flag_false PASSED
tests/test_health.py::TestHealthEndpoint::test_health_response_structure PASSED
tests/test_health.py::TestOpenAPIDocs::test_swagger_ui_accessible PASSED
tests/test_health.py::TestOpenAPIDocs::test_redoc_accessible PASSED
tests/test_health.py::TestOpenAPIDocs::test_openapi_schema_metadata PASSED
tests/test_health.py::TestOpenAPIDocs::test_openapi_tags_present PASSED
tests/test_health.py::TestOpenAPIDocs::test_openapi_all_endpoints_present PASSED
tests/test_health.py::TestOpenAPIDocs::test_openapi_schema_has_examples PASSED

============================== 12 passed in 0.11s ==============================
```

## Code Quality

### Linting
```bash
$ ruff check src/maia_vectordb/main.py src/maia_vectordb/schemas/health.py tests/test_health.py
All checks passed!
```

### Type Checking
```bash
$ mypy src/maia_vectordb/main.py src/maia_vectordb/schemas/health.py tests/test_health.py
Success: no issues found in 3 source files
```

## Documentation Updates

**Updated**: `docs/DEVELOPMENT.md`
- Added "Health Check" section to API Endpoints
- Documented request format, response examples, and status codes
- Explained health checks performed (database connectivity, API key presence)

## Acceptance Criteria

✅ `/health` returns 200 with db connection status and component health
✅ Returns 503 if database unreachable
✅ OpenAPI docs render correctly at `/docs` with all endpoints grouped by tags
✅ All request/response models have examples
✅ `/redoc` documentation endpoint works correctly
✅ OpenAPI schema has proper title, description, and version
✅ Comprehensive test coverage (12 tests, all passing)
✅ No lint or type checking issues
✅ Documentation updated

## Files Changed

**Modified**:
- `src/maia_vectordb/main.py` - Added health endpoint and OpenAPI configuration
- `src/maia_vectordb/schemas/file.py` - Added examples to file schemas
- `src/maia_vectordb/schemas/search.py` - Added examples to search schemas
- `src/maia_vectordb/schemas/vector_store.py` - Added examples to vector store schemas
- `docs/DEVELOPMENT.md` - Added health check documentation

**Created**:
- `src/maia_vectordb/schemas/health.py` - Health check schemas with examples
- `tests/test_health.py` - Comprehensive health and OpenAPI tests
- `docs/REVIEW-TASK-HEALTH-OPENAPI.md` - This review document

## API Usage Examples

### Check Service Health
```bash
curl http://localhost:8000/health
```

### View API Documentation
```bash
# Swagger UI (interactive)
open http://localhost:8000/docs

# ReDoc (clean, readable)
open http://localhost:8000/redoc

# OpenAPI JSON schema
curl http://localhost:8000/openapi.json
```

### Integration with Monitoring
The health endpoint can be used with:
- Kubernetes liveness/readiness probes
- Docker HEALTHCHECK instructions
- Load balancer health checks
- Monitoring tools (Prometheus, Datadog, etc.)

**Example Kubernetes Probe**:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

## Notes

- Health check does not validate OpenAI API key (only checks if it's configured)
- Database check runs a simple `SELECT 1` query for fast response
- Service returns 503 (not 500) for degraded state to indicate temporary issue
- All Pydantic models use `model_config` with `json_schema_extra` for examples
- Examples appear in both Swagger UI and ReDoc documentation
- Tag metadata provides clear organization in API documentation
