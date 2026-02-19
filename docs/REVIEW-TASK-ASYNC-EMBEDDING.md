# Code Review: Fix Async Blocking in Embedding Service

## Task Summary

**Task**: Fix Async Blocking in Embedding Service
**Status**: ✅ Complete
**Sprint**: Performance / Async Correctness
**Date**: 2026-02-19
**Commit**: `133e21d`
**Dependencies**: Embedding service (`services/embedding.py`), call sites (`api/files.py`, `api/search.py`)

### What Was Implemented

Migrated `services/embedding.py` from a synchronous `openai.OpenAI` client and
`time.sleep()` retry loop to a fully async implementation using `openai.AsyncOpenAI`
and `asyncio.sleep()`. Updated both call sites to `await` the now-async function.

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/maia_vectordb/services/embedding.py` | Modified | `_get_client()` returns `AsyncOpenAI`; `embed_texts` and `_call_with_retry` are `async`; `asyncio.sleep()` replaces `time.sleep()` |
| `src/maia_vectordb/api/files.py` | Modified | `embeddings = await embed_texts(chunks)` (line 61) |
| `src/maia_vectordb/api/search.py` | Modified | `query_embedding = (await embed_texts([body.query]))[0]` (line 53) |

---

## Acceptance Criteria Verification

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | `embed_texts` is async using `AsyncOpenAI` | ✅ | `async def embed_texts(...)` + `_get_client() -> openai.AsyncOpenAI` in `embedding.py:26,31` |
| 2 | Retry loop uses `asyncio.sleep()` | ✅ | `await asyncio.sleep(backoff)` at `embedding.py:111`; `import time` is absent |
| 3 | No `time.sleep()` in hot path | ✅ | `time.sleep` only in `embedding_provider.py:OpenAIEmbeddingProvider` — a sync utility class never imported by any FastAPI endpoint |
| 4 | All existing embedding unit tests pass | ✅ | `pytest -m "not integration"` → **299 passed**, 27 deselected (15.69s) |
| 5 | Concurrent requests do not block the event loop | ✅ | `AsyncOpenAI` uses `httpx` (fully async HTTP); `await asyncio.sleep()` yields during back-off |

---

## Code Quality Review

### `services/embedding.py`

**✅ Strengths:**
- `_get_client()` is a pure factory — easy to mock in tests
- `async def _call_with_retry(...)` signature is internally consistent: all
  retryable error classes are caught, backoff doubles correctly, exhausted
  retries re-raise the last exception
- `chunk_and_embed` was already awaiting `embed_texts` — no change needed
- No `import time` remaining in the file

**✅ Test coverage:**
- `TestEmbedTexts` — batching, multi-batch, empty input
- `TestRetryLogic` — 429 rate limit, 500 server error, exhausted retries,
  non-retryable error, exponential backoff values, connection errors
- `TestChunkAndEmbed` — tuple output, empty text
- `TestEmbeddingClientCreation` — `AsyncOpenAI` is instantiated with the correct
  API key from settings
- `TestEmbedTextsEdgeCases` — default model, custom model override, order
  preservation across batches

### `embedding_provider.py` — Note on `time.sleep()`

`OpenAIEmbeddingProvider._call_with_retry` still uses `time.sleep()`. This is
intentional and correct: `OpenAIEmbeddingProvider` is a **synchronous** utility
class with a sync `embed_texts` method. It is used only in
`examples/ask_any_provider.py` and the integration test scaffold
(`conftest_integration.py`) — never imported by any FastAPI route handler. It
does **not** block the event loop.

---

## Quality Gates

| Check | Command | Result |
|-------|---------|--------|
| Linting | `ruff check .` | ✅ All checks passed |
| Formatting | `ruff format --check .` | ✅ 57 files already formatted |
| Type checking | `mypy src/maia_vectordb` | ✅ No issues found in 30 source files |
| Unit tests | `pytest -m "not integration"` | ✅ 299 passed, 27 deselected in 15.69s |

---

## Security Review

**✅ No security issues introduced.**

- API key handling unchanged — loaded from `settings.openai_api_key` only
- No new environment variables or configuration
- `AsyncOpenAI` uses the same TLS/HTTPS transport as the sync client

---

## Reviewer Verdict

**✅ APPROVED** — All acceptance criteria met. Quality gates pass. Documentation updated.

**Reviewer**: QA Agent
**Date**: 2026-02-19
