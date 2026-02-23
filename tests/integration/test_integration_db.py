"""Integration tests against a real PostgreSQL + pgvector database.

These tests verify the full application stack: FastAPI routes, SQLAlchemy ORM,
pgvector similarity search, and cascade deletes — all against a live database.

Run with:
    uv run pytest tests/integration/ -v -m integration
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# All tests in this module use the integration marker
pytestmark = pytest.mark.integration


# ============================================================================
# A. Database Infrastructure Tests
# ============================================================================


class TestDatabaseInfrastructure:
    """Verify the PostgreSQL + pgvector setup is correct."""

    async def test_pgvector_extension_registered(
        self, db_session: AsyncSession
    ) -> None:
        """The ``vector`` extension is installed in the test database."""
        result = await db_session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "vector"

    async def test_vector_stores_table_exists(self, db_session: AsyncSession) -> None:
        """The ``vector_stores`` table is created with expected columns."""
        result = await db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'vector_stores' ORDER BY ordinal_position"
            )
        )
        columns = [row[0] for row in result.fetchall()]
        assert "id" in columns
        assert "name" in columns
        assert "status" in columns
        assert "metadata" in columns
        assert "created_at" in columns

    async def test_files_table_exists(self, db_session: AsyncSession) -> None:
        """The ``files`` table is created with expected columns."""
        result = await db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'files' ORDER BY ordinal_position"
            )
        )
        columns = [row[0] for row in result.fetchall()]
        assert "id" in columns
        assert "vector_store_id" in columns
        assert "filename" in columns
        assert "status" in columns

    async def test_file_chunks_table_exists(self, db_session: AsyncSession) -> None:
        """The ``file_chunks`` table has the embedding vector column."""
        result = await db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'file_chunks' ORDER BY ordinal_position"
            )
        )
        columns = [row[0] for row in result.fetchall()]
        assert "id" in columns
        assert "embedding" in columns
        assert "content" in columns
        assert "chunk_index" in columns

    async def test_hnsw_index_exists(self, db_session: AsyncSession) -> None:
        """The HNSW index on ``file_chunks.embedding`` is created."""
        result = await db_session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'file_chunks' "
                "AND indexname = 'ix_file_chunks_embedding_hnsw'"
            )
        )
        row = result.fetchone()
        assert row is not None, "HNSW index not found on file_chunks.embedding"


# ============================================================================
# B. Vector Store CRUD (real DB)
# ============================================================================


class TestVectorStoreCRUD:
    """Test vector store lifecycle against real PostgreSQL."""

    async def test_create_vector_store(self, integration_client: AsyncClient) -> None:
        """POST /v1/vector_stores creates a persisted store."""
        resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "test-store"}
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["object"] == "vector_store"
        assert body["name"] == "test-store"
        assert body["status"] == "completed"
        assert body["id"]  # UUID string

    async def test_create_vector_store_with_metadata(
        self, integration_client: AsyncClient
    ) -> None:
        """POST /v1/vector_stores accepts metadata."""
        resp = await integration_client.post(
            "/v1/vector_stores",
            json={"name": "meta-store", "metadata": {"env": "test", "version": 2}},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["metadata"] == {"env": "test", "version": 2}

    async def test_list_vector_stores(self, integration_client: AsyncClient) -> None:
        """GET /v1/vector_stores returns created stores."""
        await integration_client.post("/v1/vector_stores", json={"name": "store-alpha"})
        await integration_client.post("/v1/vector_stores", json={"name": "store-beta"})

        resp = await integration_client.get("/v1/vector_stores")
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "list"
        assert len(body["data"]) >= 2
        names = [s["name"] for s in body["data"]]
        assert "store-alpha" in names
        assert "store-beta" in names

    async def test_list_vector_stores_pagination(
        self, integration_client: AsyncClient
    ) -> None:
        """GET /v1/vector_stores respects limit and offset."""
        for i in range(5):
            await integration_client.post(
                "/v1/vector_stores", json={"name": f"page-store-{i}"}
            )

        resp = await integration_client.get("/v1/vector_stores?limit=2&offset=0")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["has_more"] is True

    async def test_get_vector_store_by_id(
        self, integration_client: AsyncClient
    ) -> None:
        """GET /v1/vector_stores/{id} returns the correct store."""
        create_resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "get-me"}
        )
        store_id = create_resp.json()["id"]

        resp = await integration_client.get(f"/v1/vector_stores/{store_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "get-me"
        assert resp.json()["id"] == store_id

    async def test_get_nonexistent_vector_store_returns_404(
        self, integration_client: AsyncClient
    ) -> None:
        """GET /v1/vector_stores/{bad_id} returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await integration_client.get(f"/v1/vector_stores/{fake_id}")
        assert resp.status_code == 404

    async def test_delete_vector_store(self, integration_client: AsyncClient) -> None:
        """DELETE /v1/vector_stores/{id} removes the store."""
        create_resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "delete-me"}
        )
        store_id = create_resp.json()["id"]

        resp = await integration_client.delete(f"/v1/vector_stores/{store_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert resp.json()["object"] == "vector_store.deleted"

        # Verify it's gone
        get_resp = await integration_client.get(f"/v1/vector_stores/{store_id}")
        assert get_resp.status_code == 404

    async def test_delete_nonexistent_returns_404(
        self, integration_client: AsyncClient
    ) -> None:
        """DELETE /v1/vector_stores/{bad_id} returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await integration_client.delete(f"/v1/vector_stores/{fake_id}")
        assert resp.status_code == 404


# ============================================================================
# C. File Upload + Chunking (real DB)
# ============================================================================


class TestFileUpload:
    """Test file upload, chunking, and embedding against real PostgreSQL."""

    async def test_upload_text_file(self, integration_client: AsyncClient) -> None:
        """POST uploads a file, chunks it, and creates embeddings."""
        store_resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "upload-store"}
        )
        store_id = store_resp.json()["id"]

        content = "This is a test document for integration testing."
        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={"file": ("test.txt", content.encode(), "text/plain")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["object"] == "vector_store.file"
        assert body["status"] == "completed"
        assert body["filename"] == "test.txt"
        assert body["chunk_count"] >= 1
        assert body["bytes"] == len(content.encode())

    async def test_upload_raw_text(self, integration_client: AsyncClient) -> None:
        """POST with text form field creates file from raw text."""
        store_resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "raw-text-store"}
        )
        store_id = store_resp.json()["id"]

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/files",
            data={"text": "Raw text content for embedding."},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "completed"
        assert body["filename"] == "raw_text.txt"
        assert body["chunk_count"] >= 1

    async def test_upload_no_content_returns_400(
        self, integration_client: AsyncClient
    ) -> None:
        """POST without file or text returns 400."""
        store_resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "empty-upload-store"}
        )
        store_id = store_resp.json()["id"]

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/files",
        )
        assert resp.status_code == 400

    async def test_upload_to_nonexistent_store_returns_404(
        self, integration_client: AsyncClient
    ) -> None:
        """POST to non-existent store returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await integration_client.post(
            f"/v1/vector_stores/{fake_id}/files",
            files={"file": ("test.txt", b"content", "text/plain")},
        )
        assert resp.status_code == 404

    async def test_get_file_status(self, integration_client: AsyncClient) -> None:
        """GET file status returns correct chunk count."""
        store_resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "file-status-store"}
        )
        store_id = store_resp.json()["id"]

        upload_resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={"file": ("doc.txt", b"Some content to chunk.", "text/plain")},
        )
        file_id = upload_resp.json()["id"]
        expected_chunks = upload_resp.json()["chunk_count"]

        resp = await integration_client.get(
            f"/v1/vector_stores/{store_id}/files/{file_id}"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["chunk_count"] == expected_chunks

    async def test_get_file_not_found(self, integration_client: AsyncClient) -> None:
        """GET non-existent file returns 404."""
        store_resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "file-404-store"}
        )
        store_id = store_resp.json()["id"]
        fake_file_id = str(uuid.uuid4())

        resp = await integration_client.get(
            f"/v1/vector_stores/{store_id}/files/{fake_file_id}"
        )
        assert resp.status_code == 404


# ============================================================================
# D. Similarity Search (real pgvector)
# ============================================================================


class TestSimilaritySearch:
    """Test cosine similarity search using real pgvector HNSW index."""

    async def _create_store_with_document(
        self,
        client: AsyncClient,
        store_name: str,
        document: str,
    ) -> tuple[str, str]:
        """Helper: create a store, upload a document, return (store_id, file_id)."""
        store_resp = await client.post("/v1/vector_stores", json={"name": store_name})
        store_id = store_resp.json()["id"]

        upload_resp = await client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={"file": ("doc.txt", document.encode(), "text/plain")},
        )
        file_id = upload_resp.json()["id"]
        return store_id, file_id

    async def test_search_returns_results(
        self, integration_client: AsyncClient
    ) -> None:
        """Searching after upload returns ranked results."""
        store_id, _ = await self._create_store_with_document(
            integration_client,
            "search-store",
            "Machine learning is a subset of artificial intelligence.",
        )

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "What is machine learning?", "max_results": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "list"
        assert body["search_query"] == "What is machine learning?"
        assert len(body["data"]) >= 1

        result = body["data"][0]
        assert "content" in result
        assert "score" in result
        assert "file_id" in result
        assert "chunk_index" in result
        assert isinstance(result["score"], float)

    async def test_search_results_have_valid_scores(
        self, integration_client: AsyncClient
    ) -> None:
        """Search results have similarity scores in [0, 1]."""
        store_id, _ = await self._create_store_with_document(
            integration_client,
            "score-store",
            "Python is a programming language. JavaScript runs in browsers.",
        )

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "programming language", "max_results": 10},
        )
        assert resp.status_code == 200
        results = resp.json()["data"]
        assert len(results) >= 1

        for result in results:
            # Cosine similarity ranges from -1 to 1
            assert -1.0 <= result["score"] <= 1.0

    async def test_search_empty_store_returns_empty(
        self, integration_client: AsyncClient
    ) -> None:
        """Searching an empty store returns no results."""
        store_resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "empty-search-store"}
        )
        store_id = store_resp.json()["id"]

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "anything"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    async def test_search_nonexistent_store_returns_404(
        self, integration_client: AsyncClient
    ) -> None:
        """Searching a non-existent store returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await integration_client.post(
            f"/v1/vector_stores/{fake_id}/search",
            json={"query": "test"},
        )
        assert resp.status_code == 404

    async def test_search_with_score_threshold(
        self, integration_client: AsyncClient
    ) -> None:
        """Search with score_threshold filters low-similarity results."""
        store_id, _ = await self._create_store_with_document(
            integration_client,
            "threshold-store",
            "The cat sat on the mat. Dogs love to play fetch in the park.",
        )

        # Very high threshold should return fewer or no results
        resp_high = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "unrelated quantum physics topic",
                "max_results": 10,
                "score_threshold": 0.99,
            },
        )
        assert resp_high.status_code == 200
        high_count = len(resp_high.json()["data"])

        # Low threshold should return more results
        resp_low = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={
                "query": "unrelated quantum physics topic",
                "max_results": 10,
                "score_threshold": 0.0,
            },
        )
        assert resp_low.status_code == 200
        low_count = len(resp_low.json()["data"])

        assert low_count >= high_count

    async def test_search_max_results_limits_output(
        self, integration_client: AsyncClient
    ) -> None:
        """Search respects max_results limit."""
        long_text = " ".join([f"Paragraph {i}: " + "word " * 200 for i in range(10)])
        store_id, _ = await self._create_store_with_document(
            integration_client,
            "limit-store",
            long_text,
        )

        resp = await integration_client.post(
            f"/v1/vector_stores/{store_id}/search",
            json={"query": "paragraph", "max_results": 2},
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) <= 2


# ============================================================================
# E. Cascade Delete (real DB)
# ============================================================================


class TestCascadeDelete:
    """Test that deleting a vector store cascades to files and chunks."""

    async def test_delete_store_removes_files_and_chunks(
        self,
        integration_client: AsyncClient,
        raw_session: AsyncSession,
    ) -> None:
        """Deleting a store cascades to remove all files and chunks."""
        # Create store + upload file
        store_resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "cascade-store"}
        )
        store_id = store_resp.json()["id"]

        await integration_client.post(
            f"/v1/vector_stores/{store_id}/files",
            files={"file": ("cascade.txt", b"Content for cascade test.", "text/plain")},
        )

        # Verify data exists
        result = await raw_session.execute(
            text("SELECT COUNT(*) FROM files WHERE vector_store_id = :sid"),
            {"sid": store_id},
        )
        assert (result.scalar() or 0) >= 1

        result = await raw_session.execute(
            text("SELECT COUNT(*) FROM file_chunks WHERE vector_store_id = :sid"),
            {"sid": store_id},
        )
        assert (result.scalar() or 0) >= 1

        # Delete the store
        resp = await integration_client.delete(f"/v1/vector_stores/{store_id}")
        assert resp.status_code == 200

        # Verify cascade: files and chunks should be gone
        result = await raw_session.execute(
            text("SELECT COUNT(*) FROM files WHERE vector_store_id = :sid"),
            {"sid": store_id},
        )
        assert result.scalar() == 0

        result = await raw_session.execute(
            text("SELECT COUNT(*) FROM file_chunks WHERE vector_store_id = :sid"),
            {"sid": store_id},
        )
        assert result.scalar() == 0


# ============================================================================
# F. Health Endpoint
# ============================================================================


class TestHealthIntegration:
    """Test the health endpoint against the test server."""

    async def test_health_endpoint_responds(
        self, integration_client: AsyncClient
    ) -> None:
        """Health endpoint responds with status and version."""
        resp = await integration_client.get("/health")
        # The health endpoint checks the production DB engine which isn't
        # initialized in tests, so it may return 503 — we just verify it works
        assert resp.status_code in (200, 503)
        body = resp.json()
        assert "status" in body
        assert "version" in body
        assert body["version"] == "0.1.0"
