"""add GIN index for full-text search on file_chunks.content

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-06 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_file_chunks_content_fts
        ON file_chunks
        USING GIN (to_tsvector('english', content))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_file_chunks_content_fts")
