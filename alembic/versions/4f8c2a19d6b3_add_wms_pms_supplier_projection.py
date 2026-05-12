"""add_wms_pms_supplier_projection

Revision ID: 4f8c2a19d6b3
Revises: 9b7f2c1d8e44
Create Date: 2026-05-12 10:25:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f8c2a19d6b3"
down_revision: Union[str, Sequence[str], None] = "9b7f2c1d8e44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wms_pms_supplier_projection",
        sa.Column("supplier_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("supplier_code", sa.String(length=64), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("pms_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("sync_version", sa.String(length=64), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("supplier_id", name="pk_wms_pms_supplier_projection"),
        sa.UniqueConstraint(
            "supplier_code",
            name="uq_wms_pms_supplier_projection_supplier_code",
        ),
        sa.CheckConstraint(
            "length(trim(supplier_code)) > 0",
            name="ck_wms_pms_supplier_projection_supplier_code_non_empty",
        ),
        sa.CheckConstraint(
            "length(trim(supplier_name)) > 0",
            name="ck_wms_pms_supplier_projection_supplier_name_non_empty",
        ),
    )
    op.create_index(
        "ix_wms_pms_supplier_projection_active",
        "wms_pms_supplier_projection",
        ["active"],
    )
    op.create_index(
        "ix_wms_pms_supplier_projection_supplier_name",
        "wms_pms_supplier_projection",
        ["supplier_name"],
    )
    op.create_index(
        "ix_wms_pms_supplier_projection_synced_at",
        "wms_pms_supplier_projection",
        ["synced_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wms_pms_supplier_projection_synced_at",
        table_name="wms_pms_supplier_projection",
    )
    op.drop_index(
        "ix_wms_pms_supplier_projection_supplier_name",
        table_name="wms_pms_supplier_projection",
    )
    op.drop_index(
        "ix_wms_pms_supplier_projection_active",
        table_name="wms_pms_supplier_projection",
    )
    op.drop_table("wms_pms_supplier_projection")
