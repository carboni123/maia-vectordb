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
- [Structured CSV](#structured-csv)
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

**Option 1: File Upload (text)**
```bash
curl -X POST http://localhost:8000/v1/vector_stores/{id}/files \
  -F "file=@document.txt"
```

**Option 2: File Upload (binary -- PDF or DOCX)**
```bash
curl -X POST http://localhost:8000/v1/vector_stores/{id}/files \
  -F "file=@report.pdf" \
  -F 'attributes={"department":"engineering","priority":"high"}'
```

**Option 3: Raw Text**
```bash
curl -X POST http://localhost:8000/v1/vector_stores/{id}/files \
  -F "text=Your raw text content here" \
  -F "filename=my-notes.md"
```

**Fields:**
- `file` (file, optional): File to upload. Supported formats: `.txt`, `.md`, `.json`, `.html`, `.htm`, `.csv`, `.xml`, `.yaml`, `.yml`, `.pdf`, `.docx`
- `text` (string, optional): Raw text content
- `filename` (string, optional): Override the filename. When provided with `file`, overrides the uploaded filename. When provided with `text`, replaces the default `raw_text.txt`. The extension determines content type detection.
- `attributes` (string, optional): JSON-encoded object of custom metadata to attach to the file. Must be a valid JSON object (not array or scalar). Example: `'{"department":"sales"}'`
- Note: Must provide exactly one of `file` or `text`

**Supported File Formats:**

| Extension | Content Type | Extraction Method |
|-----------|-------------|-------------------|
| `.txt` | `text/plain` | UTF-8 decode |
| `.md` | `text/markdown` | UTF-8 decode |
| `.json` | `application/json` | UTF-8 decode |
| `.html`, `.htm` | `text/html` | UTF-8 decode |
| `.csv` | `text/csv` | UTF-8 decode |
| `.xml` | `application/xml` | UTF-8 decode |
| `.yaml`, `.yml` | `application/x-yaml` | UTF-8 decode |
| `.pdf` | `application/pdf` | PyMuPDF text extraction |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx paragraph extraction |

**Response (Small File ≤50 KB):** `201 Created`
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "object": "vector_store.file",
  "vector_store_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "report.pdf",
  "status": "completed",
  "bytes": 1024,
  "chunk_count": 3,
  "content_type": "application/pdf",
  "attributes": {"department": "engineering"},
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
  "filename": "large_document.docx",
  "status": "in_progress",
  "bytes": 75000,
  "chunk_count": 0,
  "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "attributes": null,
  "purpose": "assistants",
  "created_at": 1707868900
}
```

**New Response Fields:**
- `content_type` (string|null): MIME type detected from the file extension. Null if the extension is not in the known mapping.
- `attributes` (object|null): Custom metadata attached to the file at upload time. Null if not provided.

**Processing Behavior:**
- **≤50 KB**: Processed inline, returns `status: "completed"` with chunk count
- **>50 KB**: Processed in background, returns `status: "in_progress"` (poll GET endpoint for completion)
- **Binary files (PDF, DOCX)**: Text is extracted before chunking. Empty documents (no extractable text) return a `400` error.

**Error Responses:**
- `404 Not Found` - Vector store doesn't exist
- `400 Bad Request` - Unsupported file format, empty binary document, invalid attributes JSON, invalid UTF-8 text, or missing file/text
- `413 Request Entity Too Large` - File exceeds configured `MAX_FILE_SIZE_BYTES` limit

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
  "filename": "report.pdf",
  "status": "completed",
  "bytes": 75000,
  "chunk_count": 95,
  "content_type": "application/pdf",
  "attributes": {"department": "engineering"},
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
      "filename": "ml_guide.pdf",
      "chunk_index": 0,
      "content": "Machine learning is a subset of artificial intelligence...",
      "score": 0.92,
      "metadata": {
        "category": "science",
        "lang": "en"
      },
      "file_attributes": {
        "department": "research"
      }
    },
    {
      "file_id": "660e8400-e29b-41d4-a716-446655440002",
      "filename": "ai_intro.docx",
      "chunk_index": 2,
      "content": "Applications of ML include computer vision, NLP...",
      "score": 0.85,
      "metadata": {
        "category": "science",
        "lang": "en"
      },
      "file_attributes": null
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
- `metadata` (object|null): Metadata associated with the chunk
- `file_attributes` (object|null): Custom attributes attached to the file at upload time

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

## Structured CSV

When CSV files are uploaded, their rows are also stored as JSONB for structured queries. See [STRUCTURED-CSV.md](STRUCTURED-CSV.md) for architecture details.

### POST /v1/vector_stores/{vector_store_id}/query

Execute a read-only SQL query against structured CSV data in a vector store.

**Path Parameters:**
- `vector_store_id` (UUID, required): Vector store ID

**Request Body:**
```json
{
  "sql": "SELECT data->>'city' AS city, COUNT(*) AS total FROM csv_rows WHERE file_id = 'abc123' AND (data->>'beds')::integer >= 3 GROUP BY data->>'city' ORDER BY total DESC LIMIT 100"
}
```

**Fields:**
- `sql` (string, required, max 10,000 chars): SQL SELECT query to execute. Must only reference the `csv_rows` table. Use `data->>'column_name'` to access fields, with casts for non-text types (e.g. `(data->>'price')::numeric`).

**Response:** `200 OK`
```json
{
  "columns": ["city", "total"],
  "rows": [["Austin", 47], ["Dallas", 32], ["Houston", 28]],
  "row_count": 3,
  "truncated": false
}
```

**Response Fields:**
- `columns` (list[string]): Column names from the SELECT clause
- `rows` (list[list]): Row data as arrays (positional, matching column order)
- `row_count` (integer): Number of rows returned
- `truncated` (boolean): True if results were cut off at 100 KB

**Safety:**
- Only single SELECT statements are allowed
- Only the `csv_rows` table may be referenced (subqueries, joins, and CTEs included)
- DML/DDL keywords (INSERT, DROP, etc.) are rejected
- Cross-schema references are rejected
- `LIMIT 5000` is auto-injected if no LIMIT clause is present
- A 10-second statement timeout is enforced

**Error Responses:**
- `400 Bad Request` - Non-SELECT SQL, forbidden keywords, invalid table references, SQL execution error
- `404 Not Found` - Vector store doesn't exist

---

### GET /v1/vector_stores/{vector_store_id}/files/{file_id}/preview

Preview the first N rows of a structured CSV file with column metadata.

**Path Parameters:**
- `vector_store_id` (UUID, required): Vector store ID
- `file_id` (UUID, required): File ID

**Query Parameters:**
- `limit` (integer, 1-500, default: 50): Number of rows to return

**Response:** `200 OK`
```json
{
  "columns": [
    {
      "normalized": "price_usd",
      "original_header": "Price (USD)",
      "inferred_type": "numeric",
      "sample_values": [450000, 620000, 380000]
    },
    {
      "normalized": "beds",
      "original_header": "Beds / Bedrooms",
      "inferred_type": "integer",
      "sample_values": [2, 3, 4]
    }
  ],
  "rows": [
    {"price_usd": 450000, "beds": 3, "city": "Austin"},
    {"price_usd": 620000, "beds": 4, "city": "Dallas"}
  ],
  "total_rows": 45230
}
```

**Response Fields:**
- `columns` (list[PreviewColumn]): Column metadata with normalized names, original headers, inferred types, and up to 3 sample values
- `rows` (list[dict]): Row data as objects with normalized column names as keys
- `total_rows` (integer): Total row count for this file (not just the preview)

**Error Responses:**
- `400 Bad Request` - File does not contain structured CSV data
- `404 Not Found` - Vector store or file doesn't exist, or file belongs to a different store

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
- `http_error` (401) - Missing or invalid API key
- `validation_error` (400) - Invalid request parameters (unsupported file format, invalid JSON, etc.)
- `not_found` (404) - Resource not found
- `file_too_large` (413) - Uploaded file exceeds configured size limit
- `rate_limit_exceeded` (429) - Request rate limit exceeded
- `embedding_service_error` (502) - OpenAI embedding service unavailable
- `database_error` (503) - Database operation failed
- `api_error` (500) - Unexpected server error

**Common HTTP Status Codes:**
- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Missing or invalid `X-API-Key` header
- `404 Not Found` - Resource not found
- `413 Request Entity Too Large` - File exceeds size limit
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Unexpected server error
- `502 Bad Gateway` - External service (OpenAI) unavailable
- `503 Service Unavailable` - Database or service unavailable

---

## Rate Limits

Currently, there are no API rate limits enforced. Consider implementing rate limiting for production use.

## Authentication

All `/v1/*` endpoints require an `X-API-Key` header containing a valid API key.
The `/health` endpoint is **exempt** from authentication and can be used for liveness/readiness probes without credentials.

**Configuration:** set `API_KEYS` in your environment to a comma-separated list of accepted keys:

```bash
API_KEYS=key-one,key-two,key-three
```

The server will refuse to start if `API_KEYS` is empty or unset.

**Error response when the key is absent or unrecognised (`401 Unauthorized`):**

```json
{
  "error": {
    "message": "Invalid or missing API key",
    "type": "http_error",
    "code": 401
  }
}
```

## CORS

CORS is currently configured to allow all origins. Update `main.py` to restrict origins in production.

---

## SDKs and Examples

### Python Example

```python
import requests

BASE_URL = "http://localhost:8000"
HEADERS = {"X-API-Key": "your-api-key"}

# Create vector store
response = requests.post(
    f"{BASE_URL}/v1/vector_stores",
    json={"name": "My Store"},
    headers=HEADERS,
)
store_id = response.json()["id"]

# Upload a text file
with open("document.txt", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/v1/vector_stores/{store_id}/files",
        files={"file": f},
        headers=HEADERS,
    )

# Upload a PDF with custom attributes
import json
with open("report.pdf", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/v1/vector_stores/{store_id}/files",
        files={"file": f},
        data={"attributes": json.dumps({"department": "engineering"})},
        headers=HEADERS,
    )

# Search
response = requests.post(
    f"{BASE_URL}/v1/vector_stores/{store_id}/search",
    json={"query": "machine learning", "max_results": 5},
    headers=HEADERS,
)
results = response.json()["data"]
```

### cURL Examples

See individual endpoint documentation above for cURL examples.

---

For interactive API documentation, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
