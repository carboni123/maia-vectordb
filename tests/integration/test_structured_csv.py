"""Integration test: structured CSV upload -> query -> preview -> cleanup.

Exercises the full structured CSV pipeline against a real PostgreSQL database
with mock embeddings (no OpenAI calls required).

Run with:
    uv run pytest tests/integration/test_structured_csv.py -v -m integration
"""

from __future__ import annotations

import asyncio
import io

import pytest
from httpx import AsyncClient

# All tests in this module require PostgreSQL with pgvector.
pytestmark = pytest.mark.integration

CSV_CONTENT = (
    b"Name,Age,City,Salary\n"
    b"Alice,30,Austin,75000\n"
    b"Bob,25,Dallas,65000\n"
    b"Charlie,35,Houston,90000"
)


async def _wait_for_file(
    client: AsyncClient,
    vs_id: str,
    file_id: str,
    *,
    timeout_seconds: float = 15,
    poll_interval: float = 0.5,
) -> dict:
    """Poll until a file reaches ``completed`` status or timeout."""
    elapsed = 0.0
    while elapsed < timeout_seconds:
        resp = await client.get(f"/v1/vector_stores/{vs_id}/files/{file_id}")
        assert resp.status_code == 200
        data = resp.json()
        if data["status"] == "completed":
            return data
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    pytest.fail(f"File {file_id} did not complete within {timeout_seconds}s")
    return {}  # unreachable, keeps type checker happy


class TestStructuredCsvFlow:
    """Full lifecycle test for structured CSV knowledge."""

    async def test_upload_creates_structured_metadata(
        self, integration_client: AsyncClient
    ) -> None:
        """Upload a CSV, verify structured metadata is populated."""
        # 1. Create vector store
        resp = await integration_client.post(
            "/v1/vector_stores",
            json={"name": "test-structured-csv-upload"},
        )
        assert resp.status_code == 201
        vs_id = resp.json()["id"]

        try:
            # 2. Upload CSV
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/files",
                files={
                    "file": ("employees.csv", io.BytesIO(CSV_CONTENT), "text/csv")
                },
            )
            assert resp.status_code == 201
            file_id = resp.json()["id"]

            # 3. Poll until processed
            file_data = await _wait_for_file(integration_client, vs_id, file_id)

            assert file_data["status"] == "completed"

            # 4. Verify structured metadata in attributes
            attrs = file_data.get("attributes") or {}
            structured = attrs.get("structured")
            assert structured, "Expected structured metadata in file attributes"
            assert isinstance(structured, dict)
            assert structured.get("table_name") == "csv_rows"
            assert structured.get("row_count") == 3

            columns = structured.get("columns", [])
            assert len(columns) == 4

            # Verify column normalization (headers lowered to snake_case)
            col_names = [c["normalized"] for c in columns]
            assert "name" in col_names
            assert "age" in col_names
            assert "city" in col_names
            assert "salary" in col_names

            # Verify original headers are preserved
            originals = {c["normalized"]: c["original_header"] for c in columns}
            assert originals["name"] == "Name"
            assert originals["salary"] == "Salary"

            # Verify types are inferred
            types = {c["normalized"]: c["inferred_type"] for c in columns}
            assert types["name"] == "text"
            assert types["age"] in ("integer", "numeric")
            assert types["salary"] in ("integer", "numeric")

        finally:
            await integration_client.delete(f"/v1/vector_stores/{vs_id}")

    async def test_query_structured_data(
        self, integration_client: AsyncClient
    ) -> None:
        """Query structured CSV data with SQL and verify results."""
        # Setup
        resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "test-structured-csv-query"}
        )
        assert resp.status_code == 201
        vs_id = resp.json()["id"]

        try:
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/files",
                files={
                    "file": ("data.csv", io.BytesIO(CSV_CONTENT), "text/csv")
                },
            )
            assert resp.status_code == 201
            file_id = resp.json()["id"]

            await _wait_for_file(integration_client, vs_id, file_id)

            # Query: find people with salary > 70000
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/query",
                json={
                    "sql": (
                        f"SELECT data->>'name' AS name, "
                        f"(data->>'salary')::numeric AS salary "
                        f"FROM csv_rows "
                        f"WHERE file_id = '{file_id}' "
                        f"AND (data->>'salary')::numeric > 70000 "
                        f"ORDER BY salary DESC"
                    ),
                },
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["row_count"] == 2  # Charlie (90k) and Alice (75k)
            assert result["columns"] == ["name", "salary"]
            assert result["truncated"] is False
            # First row should be Charlie (highest salary)
            assert result["rows"][0][0] == "Charlie"
            assert result["rows"][0][1] == 90000
            # Second row is Alice
            assert result["rows"][1][0] == "Alice"
            assert result["rows"][1][1] == 75000

        finally:
            await integration_client.delete(f"/v1/vector_stores/{vs_id}")

    async def test_query_all_rows(
        self, integration_client: AsyncClient
    ) -> None:
        """Query all rows without filters to verify full ingestion."""
        resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "test-structured-csv-all-rows"}
        )
        vs_id = resp.json()["id"]

        try:
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/files",
                files={
                    "file": ("data.csv", io.BytesIO(CSV_CONTENT), "text/csv")
                },
            )
            file_id = resp.json()["id"]
            await _wait_for_file(integration_client, vs_id, file_id)

            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/query",
                json={"sql": "SELECT data FROM csv_rows"},
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["row_count"] == 3

        finally:
            await integration_client.delete(f"/v1/vector_stores/{vs_id}")

    async def test_preview_structured_data(
        self, integration_client: AsyncClient
    ) -> None:
        """Preview first N rows of structured CSV with column metadata."""
        resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "test-structured-csv-preview"}
        )
        vs_id = resp.json()["id"]

        try:
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/files",
                files={
                    "file": ("data.csv", io.BytesIO(CSV_CONTENT), "text/csv")
                },
            )
            file_id = resp.json()["id"]
            await _wait_for_file(integration_client, vs_id, file_id)

            # Preview with limit=2
            resp = await integration_client.get(
                f"/v1/vector_stores/{vs_id}/files/{file_id}/preview",
                params={"limit": 2},
            )
            assert resp.status_code == 200
            preview = resp.json()
            assert preview["total_rows"] == 3
            assert len(preview["rows"]) == 2
            assert len(preview["columns"]) == 4

            # Verify column metadata structure
            col = preview["columns"][0]
            assert "normalized" in col
            assert "original_header" in col
            assert "inferred_type" in col

            # Verify rows contain dict data
            first_row = preview["rows"][0]
            assert isinstance(first_row, dict)
            assert "name" in first_row

        finally:
            await integration_client.delete(f"/v1/vector_stores/{vs_id}")

    async def test_preview_default_limit(
        self, integration_client: AsyncClient
    ) -> None:
        """Preview without explicit limit returns all rows (within default)."""
        resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "test-structured-csv-preview-default"}
        )
        vs_id = resp.json()["id"]

        try:
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/files",
                files={
                    "file": ("data.csv", io.BytesIO(CSV_CONTENT), "text/csv")
                },
            )
            file_id = resp.json()["id"]
            await _wait_for_file(integration_client, vs_id, file_id)

            resp = await integration_client.get(
                f"/v1/vector_stores/{vs_id}/files/{file_id}/preview",
            )
            assert resp.status_code == 200
            preview = resp.json()
            assert preview["total_rows"] == 3
            assert len(preview["rows"]) == 3  # default limit > 3, so all rows

        finally:
            await integration_client.delete(f"/v1/vector_stores/{vs_id}")

    async def test_query_rejects_non_select(
        self, integration_client: AsyncClient
    ) -> None:
        """Query endpoint rejects dangerous SQL statements."""
        resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "test-structured-csv-reject"}
        )
        vs_id = resp.json()["id"]

        try:
            # DROP TABLE
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/query",
                json={"sql": "DROP TABLE csv_rows"},
            )
            assert resp.status_code == 400

            # DELETE
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/query",
                json={"sql": "DELETE FROM csv_rows WHERE 1=1"},
            )
            assert resp.status_code == 400

            # INSERT
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/query",
                json={"sql": "INSERT INTO csv_rows VALUES ('a', 1, '{}')"},
            )
            assert resp.status_code == 400

        finally:
            await integration_client.delete(f"/v1/vector_stores/{vs_id}")

    async def test_cleanup_on_file_delete(
        self, integration_client: AsyncClient
    ) -> None:
        """Deleting a file removes its JSONB rows from the csv_rows table."""
        resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "test-structured-csv-cleanup"}
        )
        vs_id = resp.json()["id"]

        try:
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/files",
                files={
                    "file": ("data.csv", io.BytesIO(CSV_CONTENT), "text/csv")
                },
            )
            file_id = resp.json()["id"]
            await _wait_for_file(integration_client, vs_id, file_id)

            # Confirm data exists before delete
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/query",
                json={
                    "sql": (
                        f"SELECT COUNT(*) AS cnt FROM csv_rows "
                        f"WHERE file_id = '{file_id}'"
                    ),
                },
            )
            assert resp.status_code == 200
            assert resp.json()["rows"][0][0] == 3

            # Delete the file
            resp = await integration_client.delete(
                f"/v1/vector_stores/{vs_id}/files/{file_id}"
            )
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

            # Query should return 0 rows (schema still exists, but data gone)
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/query",
                json={
                    "sql": (
                        f"SELECT COUNT(*) AS cnt FROM csv_rows "
                        f"WHERE file_id = '{file_id}'"
                    ),
                },
            )
            assert resp.status_code == 200
            assert resp.json()["rows"][0][0] == 0

        finally:
            await integration_client.delete(f"/v1/vector_stores/{vs_id}")

    async def test_preview_rejects_non_structured_file(
        self, integration_client: AsyncClient
    ) -> None:
        """Preview returns 400 for a plain text file (no structured metadata)."""
        resp = await integration_client.post(
            "/v1/vector_stores", json={"name": "test-structured-csv-reject-preview"}
        )
        vs_id = resp.json()["id"]

        try:
            # Upload a plain text file (not CSV)
            resp = await integration_client.post(
                f"/v1/vector_stores/{vs_id}/files",
                files={
                    "file": (
                        "readme.txt",
                        io.BytesIO(b"This is plain text, not CSV."),
                        "text/plain",
                    )
                },
            )
            assert resp.status_code == 201
            file_id = resp.json()["id"]

            await _wait_for_file(integration_client, vs_id, file_id)

            # Preview should fail because this is not structured CSV
            resp = await integration_client.get(
                f"/v1/vector_stores/{vs_id}/files/{file_id}/preview",
            )
            assert resp.status_code == 400

        finally:
            await integration_client.delete(f"/v1/vector_stores/{vs_id}")
