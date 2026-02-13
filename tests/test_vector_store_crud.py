"""Tests for vector store CRUD endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from tests.conftest import make_refresh, make_store

# ---------------------------------------------------------------------------
# POST /v1/vector_stores
# ---------------------------------------------------------------------------


class TestCreateVectorStore:
    """Tests for the create endpoint."""

    def test_create_returns_201(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        store = make_store(name="my-store")
        mock_session.refresh = AsyncMock(side_effect=make_refresh(store))

        resp = client.post("/v1/vector_stores", json={"name": "my-store"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["object"] == "vector_store"
        assert body["name"] == "my-store"
        assert body["status"] == "completed"

    def test_create_with_metadata(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        meta = {"env": "test"}
        store = make_store(name="meta-store", metadata_=meta)
        mock_session.refresh = AsyncMock(side_effect=make_refresh(store))

        resp = client.post(
            "/v1/vector_stores", json={"name": "meta-store", "metadata": meta}
        )
        assert resp.status_code == 201
        assert resp.json()["metadata"] == meta

    def test_create_response_has_timestamps(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        store = make_store()
        mock_session.refresh = AsyncMock(side_effect=make_refresh(store))

        resp = client.post("/v1/vector_stores", json={"name": "ts-store"})
        body = resp.json()
        assert isinstance(body["created_at"], int)
        assert isinstance(body["updated_at"], int)


# ---------------------------------------------------------------------------
# GET /v1/vector_stores
# ---------------------------------------------------------------------------


class TestListVectorStores:
    """Tests for the list endpoint."""

    def test_list_empty(self, client: TestClient, mock_session: MagicMock) -> None:
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/v1/vector_stores")
        assert resp.status_code == 200
        body = resp.json()
        assert body["object"] == "list"
        assert body["data"] == []
        assert body["has_more"] is False

    def test_list_returns_stores(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        stores = [make_store(name=f"store-{i}") for i in range(3)]

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = stores
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/v1/vector_stores")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 3
        assert body["first_id"] == str(stores[0].id)
        assert body["last_id"] == str(stores[2].id)

    def test_list_pagination_has_more(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        # Return limit+1 items to trigger has_more
        stores = [make_store(name=f"s-{i}") for i in range(3)]

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = stores
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/v1/vector_stores?limit=2")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["has_more"] is True

    def test_list_with_offset(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        stores = [make_store(name="only-one")]

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = stores
        mock_session.execute = AsyncMock(return_value=result_mock)

        resp = client.get("/v1/vector_stores?offset=5")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    def test_list_order_param(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=result_mock)

        for order in ("asc", "desc"):
            resp = client.get(f"/v1/vector_stores?order={order}")
            assert resp.status_code == 200

    def test_list_invalid_order(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        resp = client.get("/v1/vector_stores?order=invalid")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/vector_stores/{id}
# ---------------------------------------------------------------------------


class TestGetVectorStore:
    """Tests for the retrieve endpoint."""

    def test_get_existing(self, client: TestClient, mock_session: MagicMock) -> None:
        store = make_store(name="found")
        mock_session.get = AsyncMock(return_value=store)

        resp = client.get(f"/v1/vector_stores/{store.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(store.id)
        assert body["name"] == "found"
        assert body["object"] == "vector_store"

    def test_get_not_found(self, client: TestClient, mock_session: MagicMock) -> None:
        mock_session.get = AsyncMock(return_value=None)

        resp = client.get(f"/v1/vector_stores/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_response_shape(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        store = make_store()
        mock_session.get = AsyncMock(return_value=store)

        resp = client.get(f"/v1/vector_stores/{store.id}")
        body = resp.json()
        # Verify all required OpenAI-compatible fields
        required_keys = {
            "id",
            "object",
            "name",
            "status",
            "file_counts",
            "created_at",
            "updated_at",
        }
        assert required_keys.issubset(body.keys())
        # file_counts sub-object
        fc = body["file_counts"]
        for key in ("in_progress", "completed", "cancelled", "failed", "total"):
            assert key in fc


# ---------------------------------------------------------------------------
# DELETE /v1/vector_stores/{id}
# ---------------------------------------------------------------------------


class TestDeleteVectorStore:
    """Tests for the delete endpoint."""

    def test_delete_existing(self, client: TestClient, mock_session: MagicMock) -> None:
        store = make_store(name="to-delete")
        mock_session.get = AsyncMock(return_value=store)

        resp = client.delete(f"/v1/vector_stores/{store.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(store.id)
        assert body["object"] == "vector_store.deleted"
        assert body["deleted"] is True
        mock_session.delete.assert_called_once_with(store)
        mock_session.commit.assert_called()

    def test_delete_not_found(
        self, client: TestClient, mock_session: MagicMock
    ) -> None:
        mock_session.get = AsyncMock(return_value=None)

        resp = client.delete(f"/v1/vector_stores/{uuid.uuid4()}")
        assert resp.status_code == 404
