"""Tests for structured CSV query and preview endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from tests.conftest import make_file, make_store

# ---------------------------------------------------------------------------
# POST /v1/vector_stores/{id}/query
# ---------------------------------------------------------------------------


class TestQueryEndpoint:
    """Tests for the structured SQL query endpoint."""

    def test_query_rejects_non_select(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """Non-SELECT SQL returns 400."""
        store = make_store()
        mock_session.get = AsyncMock(return_value=store)

        resp = client.post(
            f"/v1/vector_stores/{store.id}/query",
            json={"sql": "DELETE FROM csv_rows WHERE 1=1"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "error" in body
        assert body["error"]["type"] == "validation_error"

    def test_query_rejects_empty_sql(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """Empty SQL string returns 400."""
        store = make_store()
        mock_session.get = AsyncMock(return_value=store)

        resp = client.post(
            f"/v1/vector_stores/{store.id}/query",
            json={"sql": "   "},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "error" in body
        assert body["error"]["type"] == "validation_error"

    def test_query_returns_404_for_missing_store(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """Query against non-existent store returns 404."""
        mock_session.get = AsyncMock(return_value=None)

        resp = client.post(
            f"/v1/vector_stores/{uuid.uuid4()}/query",
            json={"sql": "SELECT * FROM csv_rows"},
        )
        assert resp.status_code == 404

    def test_query_success(self, client: TestClient, mock_session: MagicMock) -> None:
        """Valid SELECT query returns columns and rows."""
        store = make_store()
        mock_session.get = AsyncMock(return_value=store)

        # Mock the two session.execute calls:
        #   1) SET LOCAL statement_timeout
        #   2) The actual SQL query
        result_mock = MagicMock()
        result_mock.keys.return_value = ["name", "age"]
        result_mock.fetchall.return_value = [
            ("Alice", 30),
            ("Bob", 25),
        ]

        mock_session.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL statement_timeout
                result_mock,  # SELECT query result
            ]
        )

        resp = client.post(
            f"/v1/vector_stores/{store.id}/query",
            json={
                "sql": "SELECT data->>'name' AS name, data->>'age' AS age FROM csv_rows"
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["columns"] == ["name", "age"]
        assert body["row_count"] == 2
        assert body["truncated"] is False
        assert body["rows"] == [["Alice", 30], ["Bob", 25]]

    def test_query_rejects_insert(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """INSERT statement returns 400."""
        store = make_store()
        mock_session.get = AsyncMock(return_value=store)

        resp = client.post(
            f"/v1/vector_stores/{store.id}/query",
            json={"sql": "INSERT INTO csv_rows VALUES ('a', 1, '{}')"},
        )
        assert resp.status_code == 400

    def test_query_rejects_drop(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """DROP statement returns 400."""
        store = make_store()
        mock_session.get = AsyncMock(return_value=store)

        resp = client.post(
            f"/v1/vector_stores/{store.id}/query",
            json={"sql": "DROP TABLE csv_rows"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /v1/vector_stores/{id}/files/{file_id}/preview
# ---------------------------------------------------------------------------


class TestPreviewEndpoint:
    """Tests for the file preview endpoint."""

    def test_preview_returns_404_when_file_not_found(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """Preview returns 404 when file does not exist."""
        store = make_store()
        # First get → store (for get_vector_store), second get → None (file)
        mock_session.get = AsyncMock(side_effect=[store, None])

        resp = client.get(f"/v1/vector_stores/{store.id}/files/{uuid.uuid4()}/preview")
        assert resp.status_code == 404
        body = resp.json()
        assert "File not found" in body["error"]["message"]

    def test_preview_returns_400_when_not_structured(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """Preview returns 400 when file has no structured metadata."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        file_obj = make_file(
            vector_store_id=store_id,
            filename="plain.txt",
            attributes=None,  # No structured metadata
        )

        # First get → store, second get → file
        mock_session.get = AsyncMock(side_effect=[store, file_obj])

        resp = client.get(f"/v1/vector_stores/{store_id}/files/{file_obj.id}/preview")
        assert resp.status_code == 400
        body = resp.json()
        assert "structured" in body["error"]["message"].lower()

    def test_preview_returns_400_when_structured_is_false(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """Preview returns 400 when file attributes exist but structured is falsy."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        file_obj = make_file(
            vector_store_id=store_id,
            filename="data.csv",
            attributes={"structured": False},
        )

        mock_session.get = AsyncMock(side_effect=[store, file_obj])

        resp = client.get(f"/v1/vector_stores/{store_id}/files/{file_obj.id}/preview")
        assert resp.status_code == 400

    def test_preview_returns_404_for_wrong_store(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """File belonging to a different store returns 404."""
        store = make_store()
        other_store_id = uuid.uuid4()
        file_obj = make_file(vector_store_id=other_store_id)

        mock_session.get = AsyncMock(side_effect=[store, file_obj])

        resp = client.get(f"/v1/vector_stores/{store.id}/files/{file_obj.id}/preview")
        assert resp.status_code == 404

    def test_preview_returns_404_for_missing_store(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """Preview against non-existent store returns 404."""
        mock_session.get = AsyncMock(return_value=None)

        resp = client.get(
            f"/v1/vector_stores/{uuid.uuid4()}/files/{uuid.uuid4()}/preview"
        )
        assert resp.status_code == 404

    def test_preview_success(self, client: TestClient, mock_session: MagicMock) -> None:
        """Successful preview returns columns and rows."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        file_id = uuid.uuid4()
        file_obj = make_file(
            vector_store_id=store_id,
            file_id=file_id,
            filename="data.csv",
            attributes={
                "structured": {
                    "columns": [
                        {
                            "normalized": "name",
                            "original_header": "Name",
                            "inferred_type": "text",
                            "sample_values": ["Alice", "Bob"],
                        },
                        {
                            "normalized": "age",
                            "original_header": "Age",
                            "inferred_type": "integer",
                        },
                    ],
                    "row_count": 2,
                }
            },
        )

        # First session.get → store, second session.get → file
        mock_session.get = AsyncMock(side_effect=[store, file_obj])

        # Mock session.execute for the row query and count query
        row_result = MagicMock()
        row_result.fetchall.return_value = [
            ({"name": "Alice", "age": 30},),
            ({"name": "Bob", "age": 25},),
        ]

        count_result = MagicMock()
        count_result.scalar_one.return_value = 2

        mock_session.execute = AsyncMock(side_effect=[row_result, count_result])

        resp = client.get(f"/v1/vector_stores/{store_id}/files/{file_id}/preview")
        assert resp.status_code == 200
        body = resp.json()

        assert body["total_rows"] == 2
        assert len(body["columns"]) == 2
        assert body["columns"][0]["normalized"] == "name"
        assert body["columns"][0]["original_header"] == "Name"
        assert body["columns"][1]["inferred_type"] == "integer"
        assert len(body["rows"]) == 2
        assert body["rows"][0]["name"] == "Alice"

    def test_preview_respects_limit_param(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        """Preview passes the limit query param to the SQL query."""
        store_id = uuid.uuid4()
        store = make_store(store_id=store_id)
        file_id = uuid.uuid4()
        file_obj = make_file(
            vector_store_id=store_id,
            file_id=file_id,
            filename="data.csv",
            attributes={
                "structured": {
                    "columns": [
                        {
                            "normalized": "x",
                            "original_header": "X",
                            "inferred_type": "text",
                        },
                    ],
                    "row_count": 100,
                }
            },
        )

        mock_session.get = AsyncMock(side_effect=[store, file_obj])

        row_result = MagicMock()
        row_result.fetchall.return_value = [({"x": "val"},)]

        count_result = MagicMock()
        count_result.scalar_one.return_value = 100

        mock_session.execute = AsyncMock(side_effect=[row_result, count_result])

        resp = client.get(
            f"/v1/vector_stores/{store_id}/files/{file_id}/preview?limit=10"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_rows"] == 100
