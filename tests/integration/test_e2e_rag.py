"""End-to-end RAG test: upload TXT + PDF, search, agent tool call.

Exercises the full pipeline with real OpenAI embeddings and a real LLM
(GPT-4o-mini) that invokes the vector_store_search tool.

Requires:
    - PostgreSQL at localhost:5432 with pgvector
    - OPENAI_API_KEY set to a real key (not the dummy "test-key")
    - llm-factory-toolkit installed

Run with:
    uv run pytest tests/integration/test_e2e_rag.py -v -m e2e --tb=long
"""

from __future__ import annotations

import asyncio
import os
import socket
import sys
import threading
import time
from collections.abc import Iterator
from typing import Any

import fitz  # PyMuPDF — for creating test PDFs
import httpx
import pytest
import pytest_asyncio
import uvicorn
from sqlalchemy.ext.asyncio import create_async_engine

from maia_vectordb.db.base import Base

# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

_api_key = os.environ.get("OPENAI_API_KEY", "")
_skip_reason = ""
if not _api_key or _api_key == "test-key":
    _skip_reason = "OPENAI_API_KEY not set or is dummy 'test-key'"

try:
    from llm_factory_toolkit import LLMClient, ToolFactory
except ImportError:
    _skip_reason = _skip_reason or "llm-factory-toolkit not installed"

# Import the tool registration helper from examples/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))
try:
    from maia_tool import register_vector_store_search  # type: ignore[import-untyped]
except ImportError:
    _skip_reason = _skip_reason or "examples/maia_tool.py not importable"

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(bool(_skip_reason), reason=_skip_reason or "skip"),
]

# ---------------------------------------------------------------------------
# DB config
# ---------------------------------------------------------------------------

_PG_USER = "postgres"
_PG_PASSWORD = "postgres"
_PG_HOST = "localhost"
_PG_PORT = 5432
_TEST_DB = "maia_vectors_test"
_TEST_DSN = (
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}"
    f"@{_PG_HOST}:{_PG_PORT}/{_TEST_DB}"
)

# ---------------------------------------------------------------------------
# Sample content for uploads
# ---------------------------------------------------------------------------

_TXT_CONTENT = """\
FastAPI is a modern, fast web framework for building APIs with Python.
It is based on standard Python type hints and leverages Pydantic for
data validation. FastAPI provides automatic interactive API documentation
via Swagger UI and ReDoc. It supports async/await natively, making it
ideal for high-performance I/O-bound applications. FastAPI is one of
the fastest Python frameworks available, comparable to Node.js and Go
in benchmarks.
"""

_PDF_TEXT = """\
PostgreSQL is a powerful open-source relational database that supports \
the pgvector extension for vector similarity search. With pgvector, \
you can store high-dimensional embedding vectors alongside your \
relational data and perform efficient cosine similarity, inner product, \
and L2 distance queries. This makes PostgreSQL an excellent choice \
for retrieval-augmented generation (RAG) applications where documents \
are chunked, embedded, and searched by semantic similarity.
"""


def _create_sample_pdf(text: str) -> bytes:
    """Create an in-memory PDF with the given text content."""
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(72, 72, page.rect.width - 72, page.rect.height - 72)
    page.insert_textbox(rect, text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _setup_tables(dsn: str) -> None:
    """Create all tables in the test DB (separate engine, separate event loop)."""
    import maia_vectordb.models  # noqa: F401

    async def _inner() -> None:
        engine = create_async_engine(dsn, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_inner())


def _drop_tables(dsn: str) -> None:
    """Drop all tables (cleanup)."""
    async def _inner() -> None:
        engine = create_async_engine(dsn, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_inner())


@pytest.fixture(scope="module")
def e2e_server() -> Iterator[str]:
    """Start a real uvicorn server on a random port with the test DB.

    Yields the base URL (e.g. ``http://127.0.0.1:9876``).
    No embedding mocking — uses real OpenAI API.

    The server uses the app's normal lifespan (which calls ``init_engine``),
    so the DB engine lives in the server's own event loop — no cross-loop
    sharing with the test process.
    """
    from maia_vectordb.core.auth import verify_api_key
    from maia_vectordb.core.config import settings
    from maia_vectordb.main import app

    # 1. Create tables via a throwaway engine (avoids cross-loop issues)
    _setup_tables(_TEST_DSN)

    # 2. Point the app at the test DB, set API keys, and disable auth
    original_db_url = settings.database_url
    original_api_keys = settings.api_keys
    settings.database_url = _TEST_DSN
    settings.api_keys = ["test-key"]
    app.dependency_overrides[verify_api_key] = lambda: "test-key"

    # 3. Start uvicorn — lifespan="on" lets the app create its own engine
    port = _find_free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # 4. Wait for the server to be ready
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            r = httpx.get(f"{base_url}/health", timeout=2)
            if r.status_code in (200, 503):
                break
        except (httpx.ConnectError, httpx.ConnectTimeout):
            pass
        time.sleep(0.2)
    else:
        pytest.fail("E2E server did not start within 16 seconds")

    yield base_url

    # 5. Teardown
    server.should_exit = True
    thread.join(timeout=5)
    app.dependency_overrides.clear()
    settings.database_url = original_db_url
    settings.api_keys = original_api_keys
    _drop_tables(_TEST_DSN)


@pytest_asyncio.fixture()
async def api(e2e_server: str) -> httpx.AsyncClient:
    """Async HTTP client pointing at the e2e server."""
    async with httpx.AsyncClient(base_url=e2e_server, timeout=60) as client:
        yield client


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestEndToEndRAGPipeline:
    """Full RAG pipeline: upload files -> search -> LLM agent with tool use."""

    async def test_upload_search_and_agent_call(
        self, e2e_server: str, api: httpx.AsyncClient
    ) -> None:
        # ---- 1. Create vector store ----
        resp = await api.post(
            "/v1/vector_stores",
            json={"name": "e2e-rag-test"},
        )
        assert resp.status_code == 201, resp.text
        store_id = resp.json()["id"]

        # ---- 2. Upload .txt file ----
        resp = await api.post(
            f"/v1/vector_stores/{store_id}/files",
            files={"file": ("fastapi-guide.txt", _TXT_CONTENT.encode(), "text/plain")},
        )
        assert resp.status_code == 201, resp.text
        txt_body = resp.json()
        assert txt_body["filename"] == "fastapi-guide.txt"
        assert txt_body["content_type"] == "text/plain"
        txt_file_id = txt_body["id"]

        # ---- 3. Upload .pdf file ----
        pdf_bytes = _create_sample_pdf(_PDF_TEXT)
        resp = await api.post(
            f"/v1/vector_stores/{store_id}/files",
            files={"file": ("pgvector-guide.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 201, resp.text
        pdf_body = resp.json()
        assert pdf_body["filename"] == "pgvector-guide.pdf"
        assert pdf_body["content_type"] == "application/pdf"
        pdf_file_id = pdf_body["id"]

        # ---- 4. Verify both files completed ----
        for file_id in (txt_file_id, pdf_file_id):
            for attempt in range(30):
                resp = await api.get(
                    f"/v1/vector_stores/{store_id}/files/{file_id}"
                )
                assert resp.status_code == 200
                if resp.json()["status"] == "completed":
                    break
                await asyncio.sleep(0.5)
            else:
                pytest.fail(
                    f"File {file_id} did not complete within 15 seconds"
                )
            assert resp.json()["chunk_count"] >= 1

        # ---- 5. Search — verify results from both files ----
        resp = await api.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "vector similarity search database", "max_results": 10},
        )
        assert resp.status_code == 200, resp.text
        search_data = resp.json()["data"]
        assert len(search_data) >= 1, "Expected at least 1 search result"

        # Verify we get results from both uploaded files
        result_file_ids = {r["file_id"] for r in search_data}
        assert txt_file_id in result_file_ids, (
            "Expected search results from the .txt file"
        )
        assert pdf_file_id in result_file_ids, (
            "Expected search results from the .pdf file"
        )

        # Scores should be valid floats
        for r in search_data:
            assert isinstance(r["score"], float)

        # ---- 6. Agent call — LLM with vector_store_search tool ----
        tool_factory: Any = ToolFactory()
        register_vector_store_search(tool_factory)

        llm = LLMClient(model="openai/gpt-4o-mini", tool_factory=tool_factory)

        result = await llm.generate(
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant with access to a knowledge base. "
                        "Use the vector_store_search tool to find relevant "
                        "information before answering. "
                        "Always cite information from the search results."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "What does the knowledge base say about pgvector "
                        "and vector similarity search?"
                    ),
                },
            ],
            tool_execution_context={
                "vector_store_id": store_id,
                "maia_api_base": e2e_server,
            },
        )

        # ---- 7. Assert agent results ----
        assert result.content, "LLM returned empty content"
        assert len(result.content) > 50, (
            f"LLM response too short ({len(result.content)} chars), "
            "expected a substantive answer"
        )
        # The tool should have been called at least once
        assert len(result.payloads) >= 1, (
            "Expected at least one tool call (vector_store_search)"
        )
        # The tool payload should contain search results.
        # llm-factory-toolkit wraps payloads as {"metadata": ..., "payload": ...}
        first_payload = result.payloads[0]
        # Navigate to the actual search data (may be nested under "payload")
        search_data_payload = (
            first_payload.get("payload", first_payload)
            if isinstance(first_payload, dict)
            else first_payload
        )
        got = (
            sorted(first_payload.keys())
            if isinstance(first_payload, dict)
            else type(first_payload)
        )
        assert "data" in search_data_payload, (
            f"Tool payload missing 'data' key. Got: {got}"
        )
        assert len(search_data_payload["data"]) >= 1, "Tool returned no search results"
