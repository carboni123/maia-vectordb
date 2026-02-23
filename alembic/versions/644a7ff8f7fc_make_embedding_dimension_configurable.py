"""make embedding dimension configurable

Revision ID: 644a7ff8f7fc
Revises: 5e4cb5abbe73
Create Date: 2026-02-23 01:50:00.000000

"""

import os
from typing import Sequence, Union

import pgvector.sqlalchemy.vector  # noqa: F401
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "644a7ff8f7fc"
down_revision: Union[str, Sequence[str]] = "5e4cb5abbe73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Read dimension from env (matches Settings.embedding_dimension default)
_NEW_DIM = int(os.environ.get("EMBEDDING_DIMENSION", "1536"))
_OLD_DIM = 1536


def upgrade() -> None:
    """Alter embedding column to the configured dimension."""
    if _NEW_DIM == _OLD_DIM:
        return  # No-op when dimension hasn't changed

    # Drop the HNSW index first (it references the old column type)
    op.drop_index(
        "ix_file_chunks_embedding_hnsw",
        table_name="file_chunks",
        postgresql_using="hnsw",
    )

    # Null out existing embeddings — pgvector cannot cast between dimensions.
    op.execute("UPDATE file_chunks SET embedding = NULL")
    op.execute(f"ALTER TABLE file_chunks ALTER COLUMN embedding SET DATA TYPE vector({_NEW_DIM})")

    # Recreate the HNSW index with the new dimension
    op.create_index(
        "ix_file_chunks_embedding_hnsw",
        "file_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Revert embedding column to 1536 dimensions."""
    if _NEW_DIM == _OLD_DIM:
        return

    op.drop_index(
        "ix_file_chunks_embedding_hnsw",
        table_name="file_chunks",
        postgresql_using="hnsw",
    )

    op.execute("UPDATE file_chunks SET embedding = NULL")
    op.execute(f"ALTER TABLE file_chunks ALTER COLUMN embedding SET DATA TYPE vector({_OLD_DIM})")

    op.create_index(
        "ix_file_chunks_embedding_hnsw",
        "file_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
