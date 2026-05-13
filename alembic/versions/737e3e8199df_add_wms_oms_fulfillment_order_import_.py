"""add wms oms fulfillment order import bridge tables

Revision ID: 737e3e8199df
Revises: 20260513152656_drop_wms_legacy_oms_owner_schema
Create Date: 2026-05-13

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "737e3e8199df"
down_revision: Union[str, Sequence[str], None] = "20260513152656_drop_wms_legacy_oms_owner_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wms_oms_fulfillment_order_imports",
        sa.Column("ready_order_id", sa.String(length=192), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("store_code", sa.String(length=128), nullable=False),
        sa.Column("platform_order_no", sa.String(length=128), nullable=False),
        sa.Column("source_order_id", sa.BigInteger(), nullable=False),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("import_status", sa.String(length=32), nullable=False, server_default=sa.text("'IMPORTED'")),
        sa.Column("order_line_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("component_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("imported_by_user_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("ready_order_id", name="pk_wms_oms_fulfill_order_imports"),
        sa.UniqueConstraint("order_id", name="uq_wms_oms_fulfill_order_import_order_id"),
        sa.UniqueConstraint(
            "platform",
            "store_code",
            "platform_order_no",
            name="uq_wms_oms_fulfill_order_import_platform_store_no",
        ),
        sa.CheckConstraint(
            "import_status IN ('IMPORTED')",
            name="ck_wms_oms_fulfill_order_import_status",
        ),
        sa.CheckConstraint(
            "order_line_count >= 0",
            name="ck_wms_oms_fulfill_order_import_line_count_ge0",
        ),
        sa.CheckConstraint(
            "component_count >= 0",
            name="ck_wms_oms_fulfill_order_import_component_count_ge0",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_wms_oms_fulfill_order_import_order",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["imported_by_user_id"],
            ["users.id"],
            name="fk_wms_oms_fulfill_order_import_user",
            ondelete="SET NULL",
        ),
    )

    op.create_index(
        "ix_wms_oms_fulfill_order_import_imported_at",
        "wms_oms_fulfillment_order_imports",
        ["imported_at"],
    )

    op.create_table(
        "wms_oms_fulfillment_component_imports",
        sa.Column("ready_component_id", sa.String(length=256), nullable=False),
        sa.Column("ready_order_id", sa.String(length=192), nullable=False),
        sa.Column("ready_line_id", sa.String(length=192), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("order_line_id", sa.BigInteger(), nullable=False),
        sa.Column("resolved_item_id", sa.BigInteger(), nullable=False),
        sa.Column("resolved_item_sku_code_id", sa.BigInteger(), nullable=False),
        sa.Column("resolved_item_uom_id", sa.BigInteger(), nullable=False),
        sa.Column("component_sku_code", sa.String(length=128), nullable=False),
        sa.Column("sku_code_snapshot", sa.String(length=128), nullable=False),
        sa.Column("item_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("uom_snapshot", sa.String(length=64), nullable=False),
        sa.Column("required_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("ready_component_id", name="pk_wms_oms_fulfill_component_imports"),
        sa.UniqueConstraint("order_line_id", name="uq_wms_oms_fulfill_component_import_order_line"),
        sa.CheckConstraint(
            "required_qty > 0",
            name="ck_wms_oms_fulfill_component_import_required_qty_pos",
        ),
        sa.ForeignKeyConstraint(
            ["ready_order_id"],
            ["wms_oms_fulfillment_order_imports.ready_order_id"],
            name="fk_wms_oms_fulfill_component_import_order_import",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name="fk_wms_oms_fulfill_component_import_order",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_line_id"],
            ["order_lines.id"],
            name="fk_wms_oms_fulfill_component_import_order_line",
            ondelete="RESTRICT",
        ),
    )

    op.create_index(
        "ix_wms_oms_fulfill_component_import_ready_order",
        "wms_oms_fulfillment_component_imports",
        ["ready_order_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wms_oms_fulfill_component_import_ready_order",
        table_name="wms_oms_fulfillment_component_imports",
    )
    op.drop_table("wms_oms_fulfillment_component_imports")

    op.drop_index(
        "ix_wms_oms_fulfill_order_import_imported_at",
        table_name="wms_oms_fulfillment_order_imports",
    )
    op.drop_table("wms_oms_fulfillment_order_imports")
