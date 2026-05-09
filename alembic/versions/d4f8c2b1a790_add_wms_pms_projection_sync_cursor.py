"""add_wms_pms_projection_sync_cursor

Revision ID: d4f8c2b1a790
Revises: e7b9c2a4d6f8
Create Date: 2026-05-09 20:10:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d4f8c2b1a790"
down_revision: Union[str, Sequence[str], None] = "e7b9c2a4d6f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "wms_pms_projection_sync_cursors",
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("last_source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'IDLE'"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "source_name",
            name="pk_wms_pms_projection_sync_cursors",
        ),
        sa.CheckConstraint(
            "length(trim(source_name)) > 0",
            name="ck_wms_pms_projection_sync_cursor_source_name_non_empty",
        ),
        sa.CheckConstraint(
            "last_status IN ('IDLE', 'SUCCESS', 'FAILED')",
            name="ck_wms_pms_projection_sync_cursor_status",
        ),
        sa.CheckConstraint(
            "retry_count >= 0",
            name="ck_wms_pms_projection_sync_cursor_retry_non_negative",
        ),
    )
    op.create_index(
        "ix_wms_pms_projection_sync_cursors_status",
        "wms_pms_projection_sync_cursors",
        ["last_status"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_wms_pms_projection_sync_cursors_status",
        table_name="wms_pms_projection_sync_cursors",
    )
    op.drop_table("wms_pms_projection_sync_cursors")
