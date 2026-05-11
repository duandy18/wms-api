"""add_wms_pms_read_projection_tables

Revision ID: a8c1f4e2d9b0
Revises: 9f3d2c8a7b41
Create Date: 2026-05-11 13:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8c1f4e2d9b0"
down_revision: Union[str, Sequence[str], None] = "9f3d2c8a7b41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "wms_pms_item_projection",
        sa.Column("item_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("spec", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=True),
        sa.Column("brand", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("expiry_policy", sa.String(length=32), nullable=True),
        sa.Column("shelf_life_value", sa.Integer(), nullable=True),
        sa.Column("shelf_life_unit", sa.String(length=16), nullable=True),
        sa.Column("lot_source_policy", sa.String(length=32), nullable=True),
        sa.Column("derivation_allowed", sa.Boolean(), nullable=True),
        sa.Column("uom_governance_enabled", sa.Boolean(), nullable=True),
        sa.Column("pms_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("sync_version", sa.String(length=64), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("item_id", name="pk_wms_pms_item_projection"),
        sa.UniqueConstraint("sku", name="uq_wms_pms_item_projection_sku"),
        sa.CheckConstraint(
            "expiry_policy IS NULL OR expiry_policy IN ('NONE', 'REQUIRED')",
            name="ck_wms_pms_item_projection_expiry_policy",
        ),
        sa.CheckConstraint(
            "shelf_life_unit IS NULL OR shelf_life_unit IN ('DAY', 'WEEK', 'MONTH', 'YEAR')",
            name="ck_wms_pms_item_projection_shelf_life_unit",
        ),
        sa.CheckConstraint(
            "(shelf_life_value IS NULL) = (shelf_life_unit IS NULL)",
            name="ck_wms_pms_item_projection_shelf_life_pair",
        ),
        sa.CheckConstraint(
            "shelf_life_value IS NULL OR shelf_life_value > 0",
            name="ck_wms_pms_item_projection_shelf_life_value_pos",
        ),
        sa.CheckConstraint(
            "lot_source_policy IS NULL OR lot_source_policy IN ('INTERNAL_ONLY', 'SUPPLIER_ONLY')",
            name="ck_wms_pms_item_projection_lot_source_policy",
        ),
    )
    op.create_index(
        "ix_wms_pms_item_projection_enabled",
        "wms_pms_item_projection",
        ["enabled"],
    )
    op.create_index(
        "ix_wms_pms_item_projection_name",
        "wms_pms_item_projection",
        ["name"],
    )
    op.create_index(
        "ix_wms_pms_item_projection_synced_at",
        "wms_pms_item_projection",
        ["synced_at"],
    )

    op.create_table(
        "wms_pms_uom_projection",
        sa.Column("item_uom_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("uom", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=32), nullable=True),
        sa.Column("uom_name", sa.String(length=32), nullable=False),
        sa.Column("ratio_to_base", sa.Integer(), nullable=False),
        sa.Column("net_weight_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("is_base", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_purchase_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_inbound_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_outbound_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("pms_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("sync_version", sa.String(length=64), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("item_uom_id", name="pk_wms_pms_uom_projection"),
        sa.UniqueConstraint("item_id", "uom", name="uq_wms_pms_uom_projection_item_uom"),
        sa.CheckConstraint(
            "ratio_to_base >= 1",
            name="ck_wms_pms_uom_projection_ratio_ge_1",
        ),
    )
    op.create_index(
        "ix_wms_pms_uom_projection_item_id",
        "wms_pms_uom_projection",
        ["item_id"],
    )
    op.create_index(
        "ix_wms_pms_uom_projection_synced_at",
        "wms_pms_uom_projection",
        ["synced_at"],
    )

    op.create_table(
        "wms_pms_sku_code_projection",
        sa.Column("sku_code_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("sku_code", sa.String(length=128), nullable=False),
        sa.Column("code_type", sa.String(length=16), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pms_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("sync_version", sa.String(length=64), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("sku_code_id", name="pk_wms_pms_sku_code_projection"),
        sa.UniqueConstraint("sku_code", name="uq_wms_pms_sku_code_projection_sku_code"),
        sa.CheckConstraint(
            "length(trim(sku_code)) > 0",
            name="ck_wms_pms_sku_code_projection_sku_code_non_empty",
        ),
        sa.CheckConstraint(
            "code_type IN ('PRIMARY', 'ALIAS', 'LEGACY', 'MANUAL')",
            name="ck_wms_pms_sku_code_projection_code_type",
        ),
        sa.CheckConstraint(
            "is_primary = false OR is_active = true",
            name="ck_wms_pms_sku_code_projection_primary_active",
        ),
        sa.CheckConstraint(
            "is_primary = false OR effective_to IS NULL",
            name="ck_wms_pms_sku_code_projection_primary_no_effective_to",
        ),
    )
    op.create_index(
        "ix_wms_pms_sku_code_projection_item_id",
        "wms_pms_sku_code_projection",
        ["item_id"],
    )
    op.create_index(
        "ix_wms_pms_sku_code_projection_is_active",
        "wms_pms_sku_code_projection",
        ["is_active"],
    )
    op.create_index(
        "ix_wms_pms_sku_code_projection_synced_at",
        "wms_pms_sku_code_projection",
        ["synced_at"],
    )

    op.create_table(
        "wms_pms_barcode_projection",
        sa.Column("barcode_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_uom_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("barcode", sa.String(length=128), nullable=False),
        sa.Column("symbology", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("pms_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("sync_version", sa.String(length=64), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("barcode_id", name="pk_wms_pms_barcode_projection"),
        sa.UniqueConstraint("barcode", name="uq_wms_pms_barcode_projection_barcode"),
        sa.CheckConstraint(
            "length(trim(barcode)) > 0",
            name="ck_wms_pms_barcode_projection_barcode_non_empty",
        ),
        sa.CheckConstraint(
            "is_primary = false OR active = true",
            name="ck_wms_pms_barcode_projection_primary_active",
        ),
    )
    op.create_index(
        "ix_wms_pms_barcode_projection_item_id",
        "wms_pms_barcode_projection",
        ["item_id"],
    )
    op.create_index(
        "ix_wms_pms_barcode_projection_item_uom_id",
        "wms_pms_barcode_projection",
        ["item_uom_id"],
    )
    op.create_index(
        "ix_wms_pms_barcode_projection_active",
        "wms_pms_barcode_projection",
        ["active"],
    )
    op.create_index(
        "ix_wms_pms_barcode_projection_synced_at",
        "wms_pms_barcode_projection",
        ["synced_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index("ix_wms_pms_barcode_projection_synced_at", table_name="wms_pms_barcode_projection")
    op.drop_index("ix_wms_pms_barcode_projection_active", table_name="wms_pms_barcode_projection")
    op.drop_index("ix_wms_pms_barcode_projection_item_uom_id", table_name="wms_pms_barcode_projection")
    op.drop_index("ix_wms_pms_barcode_projection_item_id", table_name="wms_pms_barcode_projection")
    op.drop_table("wms_pms_barcode_projection")

    op.drop_index("ix_wms_pms_sku_code_projection_synced_at", table_name="wms_pms_sku_code_projection")
    op.drop_index("ix_wms_pms_sku_code_projection_is_active", table_name="wms_pms_sku_code_projection")
    op.drop_index("ix_wms_pms_sku_code_projection_item_id", table_name="wms_pms_sku_code_projection")
    op.drop_table("wms_pms_sku_code_projection")

    op.drop_index("ix_wms_pms_uom_projection_synced_at", table_name="wms_pms_uom_projection")
    op.drop_index("ix_wms_pms_uom_projection_item_id", table_name="wms_pms_uom_projection")
    op.drop_table("wms_pms_uom_projection")

    op.drop_index("ix_wms_pms_item_projection_synced_at", table_name="wms_pms_item_projection")
    op.drop_index("ix_wms_pms_item_projection_name", table_name="wms_pms_item_projection")
    op.drop_index("ix_wms_pms_item_projection_enabled", table_name="wms_pms_item_projection")
    op.drop_table("wms_pms_item_projection")
