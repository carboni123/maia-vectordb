# Architecture Notes: Convention Deviations

> Review of 22 commits (`e8e9cd4..01b0a42`) across the maia-vectordb codebase.
> This document catalogs patterns that deviate from the project's own established
> conventions as defined in `CONTRIBUTING.md`, `pyproject.toml` tooling config,
> and the dominant patterns used throughout the repository.

---

## Severity Legend

| Label | Meaning |
|-------|---------|
| **CRITICAL** | Fundamental architectural violation; affects maintainability at scale |
| **HIGH** | Significant deviation from stated conventions; likely to cause bugs or confusion |
| **MEDIUM** | Inconsistency worth addressing; may accumulate into larger problems |
| **LOW** | Minor style or hygiene issue |

---

## 1. Missing Service Layer  (CRITICAL)

**Convention:** Layered architecture `API -> Schema -> Service -> Model -> DB`
(documented in CONTRIBUTING.md and followed by `services/embedding.py` and
`services/chunking.py`).

**Deviation:** Three of the four API domains bypass the service layer entirely.
All database queries, business logic, and orchestration live directly in route
handlers.

| Domain | File | What lives in the route handler |
|--------|------|---------------------------------|
| Vector Stores | `api/vector_stores.py` | `session.add()`, `session.commit()`, `select()` queries, 404 checks |
| File Upload | `api/files.py` | File validation, content reading, inline vs. background processing decision, chunk creation, embedding calls, error recovery |
| Search | `api/search.py` | Raw SQL construction, parameter binding, distance-to-similarity conversion, result transformation |

Only `services/embedding.py` and `services/chunking.py` exist. There is no
`services/vector_store.py`, `services/file_processing.py`, or
`services/search.py`.

**Impact:** Route handlers are 100-200 lines of business logic rather than thin
dispatchers. Unit testing requires mocking at the HTTP layer instead of testing
services in isolation. Business rules cannot be reused outside the API context.

---

## 2. Custom Exception Hierarchy Is Defined but Never Used  (HIGH)

**Convention:** `core/exceptions.py` defines a custom hierarchy:
```
APIError (base)
  NotFoundError (404)
  ValidationError (400)
  EmbeddingServiceError (502)
  DatabaseError (503)
```
`core/handlers.py` registers a global handler for `APIError` that produces
the project's JSON error envelope: `{"error": {"message", "type", "code"}}`.

**Deviation:** Every route handler uses `raise HTTPException(status_code=404, detail="...")` instead:

```
api/vector_stores.py:76  raise HTTPException(status_code=404, ...)
api/vector_stores.py:88  raise HTTPException(status_code=404, ...)
api/files.py:47          raise HTTPException(status_code=404, ...)
api/files.py:121         raise HTTPException(...)
api/files.py:196         raise HTTPException(status_code=404, ...)
api/search.py:34         raise HTTPException(status_code=404, ...)
```

`NotFoundError`, `ValidationError`, `EmbeddingServiceError`, and `DatabaseError`
are **never imported by any API module**. The `api_error_handler` in
`core/handlers.py` is dead code in production.

**Impact:** Two parallel error-handling paths exist. The `HTTPException` handler
produces a different response shape (`{"detail": "..."}`) than the custom
handler (`{"error": {...}}`), so clients see inconsistent error formats depending
on which code path triggers the error.

---

## 3. Synchronous Blocking Inside Async Event Loop  (HIGH)

**Convention:** "Async throughout (FastAPI, SQLAlchemy async, asyncpg)" per
CONTRIBUTING.md.

### 3a. `time.sleep()` blocks the event loop

```python
# services/embedding.py:111
time.sleep(backoff)   # blocks for 1s, 2s, 4s, 8s, 16s (up to 31s total)
```

Called from async route handlers (`search`) and async background tasks
(`_process_file_background`). During retries the **entire server is
unresponsive**.

### 3b. Synchronous OpenAI client used in async context

```python
# services/embedding.py:26-28
def _get_client() -> openai.OpenAI:           # sync client
    return openai.OpenAI(api_key=...)
```

Every embedding call makes a synchronous HTTP request. Should use
`openai.AsyncOpenAI` or wrap in `asyncio.to_thread()`.

---

## 4. Raw SQL in Route Handler  (HIGH)

**Convention:** Use SQLAlchemy ORM constructs; keep queries in a data-access or
service layer.

**Deviation:** `api/search.py:86-100` constructs raw SQL via f-string
interpolation:

```python
sql = text(f"""
    SELECT ... FROM file_chunks fc
    JOIN files f ON f.id = fc.file_id
    WHERE {where_sql}
    ORDER BY fc.embedding <=> :query_embedding
    LIMIT :max_results
""")
```

User-supplied values are parameterized (no SQL injection risk), but the WHERE
clause construction (`f"fc.metadata->>:{param_key} = :{param_val}"`) mixes
dynamic SQL with parameterized queries. This pattern is fragile and belongs in a
repository/data-access layer, not in a route handler.

---

## 5. Duplicated Code Across Modules  (MEDIUM)

`_validate_vector_store` is copy-pasted identically in two files:

- `api/files.py:41-48`
- `api/search.py:28-35`

Both fetch a `VectorStore` by ID and raise `HTTPException(404)`. Should be a
shared utility or service method.

---

## 6. Committed Build Artifacts  (HIGH)

### `.coverage` binary tracked in git

```
$ git ls-files | grep .coverage
.coverage
```

The `.coverage` SQLite file (generated by `pytest-cov`) is checked into the
repository. Commit `01b0a42` ("chore: remove non-deliverable files") actually
**adds** this file instead of removing it. The root `.gitignore` does not
contain a `.coverage` entry.

---

## 7. Hardcoded Values That Should Be Configurable  (MEDIUM)

| Value | Location | Issue |
|-------|----------|-------|
| `postgres:postgres` credentials | `core/config.py:14`, `alembic.ini:89` | Default DB URL contains plaintext credentials; `alembic.ini` URL differs from app default (`localhost` vs `host.docker.internal`) |
| `"0.1.0"` version string | `main.py:65`, `main.py:126`, `pyproject.toml:3` | Duplicated in 3 places; should be single-sourced from `pyproject.toml` |
| `pool_size=5, max_overflow=10` | `db/engine.py:22-28` | Connection pool params are hardcoded; should differ per environment |
| `_BACKGROUND_THRESHOLD = 50_000` | `api/files.py:38` | Background processing threshold is a module constant, not a setting |
| `tiktoken.encoding_for_model("gpt-4o")` | `services/chunking.py:49` | Tiktoken model is hardcoded to `gpt-4o` regardless of configured `embedding_model` |

---

## 8. Incorrect Token Counting in File Processing  (MEDIUM)

```python
# api/files.py:70
token_count=len(chunk_text.split()),  # word count, NOT token count
```

The `token_count` field stored in the database uses whitespace splitting (word
count), while `services/chunking.py` uses proper tiktoken-based token counting
for chunk splitting. The field name `token_count` is misleading -- it stores a
word count.

---

## 9. CORS Misconfiguration  (HIGH)

```python
# main.py:79-85
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,    # <-- incompatible with wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Per the CORS specification, `allow_credentials=True` with `allow_origins=["*"]`
is invalid -- browsers will reject credentialed requests when the server responds
with `Access-Control-Allow-Origin: *`. The origins should be configurable via
`Settings` with explicit domain allowlisting for production.

---

## 10. File Upload Returns 201 on Processing Failure  (MEDIUM)

```python
# api/files.py:177-182
except Exception:
    logger.exception(...)
    file_obj.status = FileStatus.failed
    await session.commit()
    await session.refresh(file_obj)
    return FileResponse.from_orm_model(file_obj)  # HTTP 201!
```

When inline processing fails, the endpoint returns **201 Created** with
`status: "failed"` in the body. The client receives a success status code for a
failed operation. This conflicts with the project's error envelope convention and
forces clients to inspect the response body to detect failures.

---

## 11. Health Endpoint Deviations  (MEDIUM)

### 11a. Bypasses FastAPI response serialization

```python
# main.py:103, 131
async def health() -> JSONResponse:
    ...
    return JSONResponse(content=body.model_dump(), status_code=status_code)
```

Declares `response_model=HealthResponse` but returns `JSONResponse` directly,
bypassing FastAPI's schema validation and serialization pipeline. All other
endpoints return Pydantic models and let FastAPI handle serialization.

### 11b. Leaks infrastructure details

- `str(exc)` from database exceptions (may contain hostnames, connection strings)
  is returned verbatim in the `detail` field to unauthenticated callers.
- `openai_api_key_set` boolean confirms API key presence to any requester.

---

## 12. Test Anti-Patterns  (MEDIUM)

### 12a. Module-level TestClient bypasses dependency injection

```python
# tests/test_health.py:11
client = TestClient(app)  # no dependency override
```

All other test files use the `client` fixture from `conftest.py` which overrides
`get_db_session`. The health tests create their own `TestClient` without the
override, requiring ad-hoc `patch()` calls for every test.

### 12b. Tests mutate global app state

```python
# tests/test_error_handling.py:123-135
@app.get("/test-custom-error")   # adds route to production app object
def raise_custom(): ...
# then _clean_route() to remove it
```

Adding and removing routes on the live `app` object mutates global state and can
cause ordering-dependent test failures.

### 12c. Manual try/except instead of `pytest.raises`

```python
# tests/test_embedding.py:192-196
try:
    embed_texts(texts)
    raise AssertionError("Expected RateLimitError")
except openai.RateLimitError:
    pass
```

This pattern appears in `test_embedding.py` and `test_chunking.py` while other
test files correctly use `with pytest.raises(...)`.

---

## 13. `from_orm_model` Uses `getattr` on `Any`  (LOW)

```python
# schemas/vector_store.py:96-107, schemas/file.py:44-52
@classmethod
def from_orm_model(cls, obj: Any) -> VectorStoreResponse:
    return cls(id=str(getattr(obj, "id")), ...)
```

The `obj` parameter is typed as `Any` and accessed via `getattr()` with string
literals. This provides zero type safety -- the comment "for type safety" is
inaccurate. Should accept the concrete ORM model type (using `TYPE_CHECKING`
if needed to avoid circular imports).

---

## 14. Orphan Function in Chunking Service  (LOW)

```python
# services/chunking.py:159-171
def read_file(path: str) -> str:
    """Read a plain-text or Markdown file and return its contents."""
```

`read_file()` is defined in the chunking service but is **never called** by any
source file. It only appears in tests. It performs synchronous file I/O and
doesn't belong in a text-splitting service.

---

## Summary

| Severity | Count | Key Themes |
|----------|-------|------------|
| CRITICAL | 1 | Missing service layer across 3 of 4 API domains |
| HIGH | 5 | Unused exception hierarchy, sync-in-async, raw SQL in handlers, committed `.coverage`, CORS misconfiguration |
| MEDIUM | 6 | Duplicated code, hardcoded config, wrong token counting, misleading HTTP status, test anti-patterns, health endpoint inconsistencies |
| LOW | 2 | Weak typing in `from_orm_model`, orphan `read_file` function |

### Top 3 Recommendations

1. **Extract service modules** for vector stores, file processing, and search.
   Move all database queries and business logic out of route handlers.

2. **Use the custom exception hierarchy** that already exists. Replace all
   `HTTPException` calls with `NotFoundError`, `ValidationError`, etc. to get
   consistent error envelopes project-wide.

3. **Make the embedding service async.** Switch to `openai.AsyncOpenAI`,
   replace `time.sleep()` with `asyncio.sleep()`, and eliminate event loop
   blocking.
