# API Reference

Complete reference for all MAIA VectorDB API endpoints.

**Base URL**: `http://localhost:8000` (development)

**API Version**: v1

**OpenAPI Docs**: Available at `/docs` (Swagger UI) and `/redoc` (ReDoc)

---

## Table of Contents

- [Health Check](#health-check)
- [Vector Stores](#vector-stores)
- [File Management](#file-management)
- [Search](#search)
- [Error Responses](#error-responses)

---

## Health Check

### GET /health

Check the health status of the service, including database connectivity.

**Response Codes:**
- `200 OK` - Service is healthy
- `503 Service Unavailable` - Service is degraded (database unreachable)

**Response Body:**
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

**Fields:**
- `status` (string): Overall health status (`"ok"` or `"degraded"`)
- `version` (string): API version
- `database.status` (string): Database connectivity status (`"ok"` or `"error"`)
- `database.detail` (string|null): Error details if database is unreachable
- `openai_api_key_set` (boolean): Whether OpenAI API key is configured

---

## Vector Stores

### POST /v1/vector_stores

Create a new vector store.

**Request Body:**
```json
{
  "name": "My Documents",
  "metadata": {
    "project": "demo",
    "department": "engineering"
  }
}
```

**Fields:**
- `name` (string, optional): Display name for the vector store
- `metadata` (object, optional): Custom metadata key-value pairs

**Response:** `201 Created`
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
  "metadata": {
    "project": "demo",
    "department": "engineering"
  },
  "created_at": 1707868800,
  "updated_at": 1707868800,
  "expires_at": null
}
```

---

### GET /v1/vector_stores

List all vector stores with pagination.

**Query Parameters:**
- `limit` (integer, 1-100, default: 20): Number of results per page
- `offset` (integer, ≥0, default: 0): Number of results to skip
- `order` (string, "asc"|"desc", default: "desc"): Sort order by created_at

**Example:**
```bash
GET /v1/vector_stores?limit=10&offset=0&order=desc
```

**Response:** `200 OK`
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
      "metadata": {...},
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

---

### GET /v1/vector_stores/{id}

Retrieve a single vector store by ID.

**Path Parameters:**
- `id` (UUID, required): Vector store ID

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "object": "vector_store",
  "name": "My Documents",
  "status": "completed",
  "file_counts": {...},
  "metadata": {...},
  "created_at": 1707868800,
  "updated_at": 1707868800,
  "expires_at": null
}
```

**Error Response:** `404 Not Found` if vector store doesn't exist

---

### DELETE /v1/vector_stores/{id}

Delete a vector store and all associated files and chunks.

**Path Parameters:**
- `id` (UUID, required): Vector store ID

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "object": "vector_store.deleted",
  "deleted": true
}
```

**Error Response:** `404 Not Found` if vector store doesn't exist

**Note:** Deletion cascades to all associated files and file chunks.

---

## File Management

### POST /v1/vector_stores/{vector_store_id}/files

Upload a file or raw text to a vector store. The content is automatically chunked, embedded, and stored for semantic search.

**Path Parameters:**
- `vector_store_id` (UUID, required): Vector store ID

**Request Body (multipart/form-data):**

**Option 1: File Upload**
```bash
curl -X POST http://localhost:8000/v1/vector_stores/{id}/files \
  -F "file=@document.txt"
```

**Option 2: Raw Text**
```bash
curl -X POST http://localhost:8000/v1/vector_stores/{id}/files \
  -F "text=Your raw text content here"
```

**Fields:**
- `file` (file, optional): File to upload (.txt or .md)
- `text` (string, optional): Raw text content
- Note: Must provide exactly one of `file` or `text`

**Response (Small File ≤50 KB):** `201 Created`
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

**Response (Large File >50 KB):** `201 Created`
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
- **≤50 KB**: Processed inline, returns `status: "completed"` with chunk count
- **>50 KB**: Processed in background, returns `status: "in_progress"` (poll GET endpoint for completion)

**Error Responses:**
- `404 Not Found` - Vector store doesn't exist
- `400 Bad Request` - Invalid file type or missing file/text

---

### GET /v1/vector_stores/{vector_store_id}/files/{file_id}

Get the processing status and details of an uploaded file.

**Path Parameters:**
- `vector_store_id` (UUID, required): Vector store ID
- `file_id` (UUID, required): File ID

**Response:** `200 OK`
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

**Status Values:**
- `"in_progress"` - File is being processed
- `"completed"` - Processing complete, file is searchable
- `"failed"` - Processing failed
- `"cancelled"` - Processing was cancelled

**Error Responses:**
- `404 Not Found` - Vector store or file doesn't exist

---

## Search

### POST /v1/vector_stores/{vector_store_id}/search

Perform semantic similarity search over a vector store using cosine similarity.

**Path Parameters:**
- `vector_store_id` (UUID, required): Vector store ID

**Request Body:**
```json
{
  "query": "What is machine learning?",
  "max_results": 10,
  "filter": {
    "category": "science",
    "lang": "en"
  },
  "score_threshold": 0.7
}
```

**Fields:**
- `query` (string, required): Text query to search for
- `max_results` (integer, 1-100, default: 10): Maximum number of results
- `filter` (object, optional): Metadata filters (AND logic applied)
- `score_threshold` (float, 0.0-1.0, optional): Minimum similarity score

**Response:** `200 OK`
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
      "metadata": {
        "category": "science",
        "lang": "en"
      }
    },
    {
      "file_id": "660e8400-e29b-41d4-a716-446655440002",
      "filename": "ai_intro.txt",
      "chunk_index": 2,
      "content": "Applications of ML include computer vision, NLP...",
      "score": 0.85,
      "metadata": {
        "category": "science",
        "lang": "en"
      }
    }
  ],
  "search_query": "What is machine learning?"
}
```

**Result Fields:**
- `file_id` (UUID): ID of the file containing the chunk
- `filename` (string): Original filename
- `chunk_index` (integer): Index of the chunk within the file
- `content` (string): Text content of the chunk
- `score` (float): Similarity score (0.0-1.0, higher is better)
- `metadata` (object): Metadata associated with the chunk

**Search Algorithm:**
1. Query text is embedded using OpenAI's embedding API
2. Cosine similarity search performed using pgvector HNSW index
3. Results filtered by metadata (if provided)
4. Results filtered by score threshold (if provided)
5. Results sorted by similarity score (highest first)

**Error Responses:**
- `404 Not Found` - Vector store doesn't exist
- `400 Bad Request` - Invalid query parameters

---

## Error Responses

All errors return a consistent JSON envelope:

```json
{
  "error": {
    "message": "Human-readable error message",
    "type": "error_type",
    "code": 400
  }
}
```

**Error Types:**
- `not_found` (404) - Resource not found
- `bad_request` (400) - Invalid request parameters
- `embedding_service_error` (502) - OpenAI embedding service unavailable
- `database_error` (503) - Database operation failed
- `internal_server_error` (500) - Unexpected server error

**Common HTTP Status Codes:**
- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request parameters
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Unexpected server error
- `502 Bad Gateway` - External service (OpenAI) unavailable
- `503 Service Unavailable` - Database or service unavailable

---

## Rate Limits

Currently, there are no API rate limits enforced. Consider implementing rate limiting for production use.

## Authentication

Currently, there is no authentication required. Consider implementing API key authentication for production use.

## CORS

CORS is currently configured to allow all origins. Update `main.py` to restrict origins in production.

---

## SDKs and Examples

### Python Example

```python
import requests

# Create vector store
response = requests.post(
    "http://localhost:8000/v1/vector_stores",
    json={"name": "My Store"}
)
store_id = response.json()["id"]

# Upload file
with open("document.txt", "rb") as f:
    response = requests.post(
        f"http://localhost:8000/v1/vector_stores/{store_id}/files",
        files={"file": f}
    )

# Search
response = requests.post(
    f"http://localhost:8000/v1/vector_stores/{store_id}/search",
    json={"query": "machine learning", "max_results": 5}
)
results = response.json()["data"]
```

### cURL Examples

See individual endpoint documentation above for cURL examples.

---

For interactive API documentation, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
