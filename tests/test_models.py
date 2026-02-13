"""Tests for SQLAlchemy database models."""

import uuid

from sqlalchemy import inspect

from maia_vectordb.db.base import Base
from maia_vectordb.models import (
    EMBEDDING_DIMENSION,
    File,
    FileChunk,
    FileStatus,
    VectorStore,
    VectorStoreStatus,
)

# ---------------------------------------------------------------------------
# AC: all 3 models defined with proper columns/types
# ---------------------------------------------------------------------------


class TestVectorStoreModel:
    """VectorStore model tests."""

    def test_table_name(self) -> None:
        assert VectorStore.__tablename__ == "vector_stores"

    def test_inherits_base(self) -> None:
        assert issubclass(VectorStore, Base)

    def test_columns_exist(self) -> None:
        mapper = inspect(VectorStore)
        col_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id",
            "name",
            "metadata_",
            "file_counts",
            "status",
            "created_at",
            "updated_at",
            "expires_at",
        }
        assert expected.issubset(col_names)

    def test_uuid_primary_key(self) -> None:
        table = VectorStore.__table__
        pk_cols = [c.name for c in table.primary_key.columns]
        assert pk_cols == ["id"]
        assert table.c.id.type.__class__.__name__ == "Uuid"

    def test_status_enum_values(self) -> None:
        assert set(VectorStoreStatus) == {
            VectorStoreStatus.expired,
            VectorStoreStatus.in_progress,
            VectorStoreStatus.completed,
        }

    def test_expires_at_nullable(self) -> None:
        assert VectorStore.__table__.c.expires_at.nullable is True


class TestFileModel:
    """File model tests."""

    def test_table_name(self) -> None:
        assert File.__tablename__ == "files"

    def test_inherits_base(self) -> None:
        assert issubclass(File, Base)

    def test_columns_exist(self) -> None:
        mapper = inspect(File)
        col_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id",
            "vector_store_id",
            "filename",
            "status",
            "bytes",
            "purpose",
            "created_at",
        }
        assert expected.issubset(col_names)

    def test_uuid_primary_key(self) -> None:
        table = File.__table__
        pk_cols = [c.name for c in table.primary_key.columns]
        assert pk_cols == ["id"]

    def test_foreign_key_to_vector_store(self) -> None:
        table = File.__table__
        fk_targets = {
            str(fk.target_fullname) for fk in table.foreign_keys
        }
        assert "vector_stores.id" in fk_targets

    def test_cascade_delete_on_fk(self) -> None:
        table = File.__table__
        for fk in table.foreign_keys:
            if str(fk.target_fullname) == "vector_stores.id":
                assert fk.ondelete == "CASCADE"

    def test_status_enum_values(self) -> None:
        assert set(FileStatus) == {
            FileStatus.in_progress,
            FileStatus.completed,
            FileStatus.cancelled,
            FileStatus.failed,
        }


class TestFileChunkModel:
    """FileChunk model tests."""

    def test_table_name(self) -> None:
        assert FileChunk.__tablename__ == "file_chunks"

    def test_inherits_base(self) -> None:
        assert issubclass(FileChunk, Base)

    def test_columns_exist(self) -> None:
        mapper = inspect(FileChunk)
        col_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id",
            "file_id",
            "vector_store_id",
            "chunk_index",
            "content",
            "token_count",
            "embedding",
            "metadata_",
            "created_at",
        }
        assert expected.issubset(col_names)

    def test_uuid_primary_key(self) -> None:
        table = FileChunk.__table__
        pk_cols = [c.name for c in table.primary_key.columns]
        assert pk_cols == ["id"]

    def test_foreign_key_to_file(self) -> None:
        table = FileChunk.__table__
        fk_targets = {
            str(fk.target_fullname) for fk in table.foreign_keys
        }
        assert "files.id" in fk_targets

    def test_foreign_key_to_vector_store(self) -> None:
        table = FileChunk.__table__
        fk_targets = {
            str(fk.target_fullname) for fk in table.foreign_keys
        }
        assert "vector_stores.id" in fk_targets

    def test_cascade_delete_on_fks(self) -> None:
        table = FileChunk.__table__
        for fk in table.foreign_keys:
            assert fk.ondelete == "CASCADE"

    def test_vector_column_dimension(self) -> None:
        col = FileChunk.__table__.c.embedding
        assert col.type.dim == EMBEDDING_DIMENSION  # type: ignore[union-attr]
        assert EMBEDDING_DIMENSION == 1536

    def test_hnsw_index_exists(self) -> None:
        table = FileChunk.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_file_chunks_embedding_hnsw" in index_names

    def test_hnsw_index_uses_cosine_ops(self) -> None:
        table = FileChunk.__table__
        for idx in table.indexes:
            if idx.name == "ix_file_chunks_embedding_hnsw":
                dialect_options = idx.dialect_options.get("postgresql", {})
                assert dialect_options.get("using") == "hnsw"
                ops = dialect_options.get("ops", {})
                assert ops.get("embedding") == "vector_cosine_ops"
                break
        else:
            raise AssertionError("HNSW index not found")


class TestModelsImportable:
    """AC: models importable from models package."""

    def test_import_from_package(self) -> None:
        from maia_vectordb.models import (  # noqa: F811
            File,
            FileChunk,
            VectorStore,
        )

        assert VectorStore is not None
        assert File is not None
        assert FileChunk is not None

    def test_default_uuid_factory(self) -> None:
        """Verify UUID default factory is set on all models."""
        for model in (VectorStore, File, FileChunk):
            col = model.__table__.c.id
            assert col.default is not None
            # Call the factory to verify it produces a UUID
            result = col.default.arg(None)  # type: ignore[union-attr]
            assert isinstance(result, uuid.UUID)
