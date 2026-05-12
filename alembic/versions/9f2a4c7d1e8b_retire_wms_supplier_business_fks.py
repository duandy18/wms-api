"""retire_wms_supplier_business_fks

Revision ID: 9f2a4c7d1e8b
Revises: 7c9d1a2e4b6f
Create Date: 2026-05-12 11:10:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f2a4c7d1e8b"
down_revision: Union[str, Sequence[str], None] = "7c9d1a2e4b6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # WMS no longer owns supplier master data.
    # Business tables keep supplier_id as scalar reference and rely on:
    # - wms_pms_supplier_projection for current read/validation
    # - snapshot columns for historical display
    # - projection reconciliation for integrity checks
    #
    # Keep supplier_contacts -> suppliers FK for now because supplier_contacts
    # is still the only remaining legacy supplier child table.

    op.drop_constraint("fk_items_supplier", "items", type_="foreignkey")
    op.drop_constraint("fk_purchase_orders_supplier_id", "purchase_orders", type_="foreignkey")
    op.drop_constraint("fk_inbound_receipts_supplier", "inbound_receipts", type_="foreignkey")
    op.drop_constraint(
        "fk_wms_inbound_operations_supplier",
        "wms_inbound_operations",
        type_="foreignkey",
    )

    op.alter_column(
        "purchase_orders",
        "supplier_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        comment="PMS supplier_id 标量引用（由 wms_pms_supplier_projection 校验，不再是 WMS 本地 FK）",
    )
    op.alter_column(
        "purchase_orders",
        "supplier_name",
        existing_type=sa.String(length=255),
        existing_nullable=False,
        comment="下单时的供应商名称快照（来自 PMS supplier projection）",
    )


def downgrade() -> None:
    op.create_foreign_key(
        "fk_wms_inbound_operations_supplier",
        "wms_inbound_operations",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_inbound_receipts_supplier",
        "inbound_receipts",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_purchase_orders_supplier_id",
        "purchase_orders",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_items_supplier",
        "items",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.alter_column(
        "purchase_orders",
        "supplier_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        comment="FK → suppliers.id（必填）",
    )
    op.alter_column(
        "purchase_orders",
        "supplier_name",
        existing_type=sa.String(length=255),
        existing_nullable=False,
        comment="下单时的供应商名称快照（必填，通常来自 suppliers.name）",
    )
