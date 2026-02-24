"""add content_type and attributes to files

Revision ID: a1b2c3d4e5f6
Revises: 644a7ff8f7fc
Create Date: 2026-02-23 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "644a7ff8f7fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = [c["name"] for c in inspect(bind).get_columns("files")]

    if "content_type" not in columns:
        op.add_column("files", sa.Column("content_type", sa.String(128), nullable=True))
    if "attributes" not in columns:
        op.add_column(
            "files",
            sa.Column("attributes", JSON(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("files", "attributes")
    op.drop_column("files", "content_type")
