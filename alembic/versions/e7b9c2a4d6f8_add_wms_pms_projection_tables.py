"""add wms pms projection tables

Revision ID: e7b9c2a4d6f8
Revises: c91e7c4f2a31
Create Date: 2026-05-09 05:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e7b9c2a4d6f8"
down_revision: Union[str, Sequence[str], None] = "c91e7c4f2a31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LOT_SOURCE_POLICY = postgresql.ENUM(
    "INTERNAL_ONLY",
    "SUPPLIER_ONLY",
    name="lot_source_policy",
    create_type=False,
)

EXPIRY_POLICY = postgresql.ENUM(
    "NONE",
    "REQUIRED",
    name="expiry_policy",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "wms_pms_item_projection",
        sa.Column("item_id", sa.Integer(), nullable=False, autoincrement=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("spec", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_event_id", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.BigInteger(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
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
        sa.PrimaryKeyConstraint("item_id", name="pk_wms_pms_item_projection"),
        sa.UniqueConstraint("sku", name="uq_wms_pms_item_projection_sku"),
    )
    op.create_index(
        "ix_wms_pms_item_projection_enabled",
        "wms_pms_item_projection",
        ["enabled"],
        unique=False,
    )
    op.create_index(
        "ix_wms_pms_item_projection_brand_id",
        "wms_pms_item_projection",
        ["brand_id"],
        unique=False,
    )
    op.create_index(
        "ix_wms_pms_item_projection_category_id",
        "wms_pms_item_projection",
        ["category_id"],
        unique=False,
    )

    op.create_table(
        "wms_pms_item_uom_projection",
        sa.Column("item_uom_id", sa.Integer(), nullable=False, autoincrement=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("uom", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=32), nullable=True),
        sa.Column("ratio_to_base", sa.Integer(), nullable=False),
        sa.Column("is_base", sa.Boolean(), nullable=False),
        sa.Column("is_purchase_default", sa.Boolean(), nullable=False),
        sa.Column("is_inbound_default", sa.Boolean(), nullable=False),
        sa.Column("is_outbound_default", sa.Boolean(), nullable=False),
        sa.Column("net_weight_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_event_id", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.BigInteger(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
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
        sa.PrimaryKeyConstraint("item_uom_id", name="pk_wms_pms_item_uom_projection"),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["wms_pms_item_projection.item_id"],
            name="fk_wms_pms_item_uom_projection_item",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "item_uom_id",
            "item_id",
            name="uq_wms_pms_item_uom_id_item_id",
        ),
        sa.UniqueConstraint(
            "item_id",
            "uom",
            name="uq_wms_pms_item_uom_item_uom",
        ),
        sa.CheckConstraint(
            "ratio_to_base >= 1",
            name="ck_wms_pms_item_uom_ratio_ge_1",
        ),
    )
    op.create_index(
        "ix_wms_pms_item_uom_item_id",
        "wms_pms_item_uom_projection",
        ["item_id"],
        unique=False,
    )
    op.create_index(
        "uq_wms_pms_item_uom_one_base",
        "wms_pms_item_uom_projection",
        ["item_id"],
        unique=True,
        postgresql_where=sa.text("is_base = true"),
    )
    op.create_index(
        "uq_wms_pms_item_uom_one_purchase_default",
        "wms_pms_item_uom_projection",
        ["item_id"],
        unique=True,
        postgresql_where=sa.text("is_purchase_default = true"),
    )
    op.create_index(
        "uq_wms_pms_item_uom_one_inbound_default",
        "wms_pms_item_uom_projection",
        ["item_id"],
        unique=True,
        postgresql_where=sa.text("is_inbound_default = true"),
    )
    op.create_index(
        "uq_wms_pms_item_uom_one_outbound_default",
        "wms_pms_item_uom_projection",
        ["item_id"],
        unique=True,
        postgresql_where=sa.text("is_outbound_default = true"),
    )

    op.create_table(
        "wms_pms_item_policy_projection",
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("lot_source_policy", LOT_SOURCE_POLICY, nullable=False),
        sa.Column("expiry_policy", EXPIRY_POLICY, nullable=False),
        sa.Column("shelf_life_value", sa.Integer(), nullable=True),
        sa.Column("shelf_life_unit", sa.String(length=16), nullable=True),
        sa.Column("derivation_allowed", sa.Boolean(), nullable=False),
        sa.Column("uom_governance_enabled", sa.Boolean(), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_event_id", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.BigInteger(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
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
        sa.PrimaryKeyConstraint("item_id", name="pk_wms_pms_item_policy_projection"),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["wms_pms_item_projection.item_id"],
            name="fk_wms_pms_item_policy_projection_item",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "expiry_policy = 'REQUIRED' OR "
            "(shelf_life_value IS NULL AND shelf_life_unit IS NULL)",
            name="ck_wms_pms_policy_shelf_life_by_expiry",
        ),
        sa.CheckConstraint(
            "(shelf_life_value IS NULL) = (shelf_life_unit IS NULL)",
            name="ck_wms_pms_policy_shelf_life_pair",
        ),
        sa.CheckConstraint(
            "shelf_life_unit IS NULL OR shelf_life_unit IN ('DAY','WEEK','MONTH','YEAR')",
            name="ck_wms_pms_policy_shelf_life_unit",
        ),
        sa.CheckConstraint(
            "shelf_life_value IS NULL OR shelf_life_value > 0",
            name="ck_wms_pms_policy_shelf_life_value_pos",
        ),
    )

    op.create_table(
        "wms_pms_item_sku_code_projection",
        sa.Column("sku_code_id", sa.Integer(), nullable=False, autoincrement=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("code_type", sa.String(length=16), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_event_id", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.BigInteger(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
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
        sa.PrimaryKeyConstraint("sku_code_id", name="pk_wms_pms_item_sku_code_projection"),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["wms_pms_item_projection.item_id"],
            name="fk_wms_pms_item_sku_code_projection_item",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("code", name="uq_wms_pms_item_sku_code_code"),
        sa.UniqueConstraint(
            "sku_code_id",
            "item_id",
            name="uq_wms_pms_item_sku_code_id_item_id",
        ),
        sa.CheckConstraint(
            "length(trim(code)) > 0",
            name="ck_wms_pms_sku_code_non_empty",
        ),
        sa.CheckConstraint(
            "code_type IN ('PRIMARY','ALIAS','LEGACY','MANUAL')",
            name="ck_wms_pms_sku_code_type",
        ),
        sa.CheckConstraint(
            "is_primary = false OR is_active = true",
            name="ck_wms_pms_sku_primary_active",
        ),
        sa.CheckConstraint(
            "is_primary = false OR effective_to IS NULL",
            name="ck_wms_pms_sku_primary_no_effective_to",
        ),
        sa.CheckConstraint(
            "(code_type = 'PRIMARY') = (is_primary = true)",
            name="ck_wms_pms_sku_primary_type",
        ),
    )
    op.create_index(
        "ix_wms_pms_item_sku_code_item_id",
        "wms_pms_item_sku_code_projection",
        ["item_id"],
        unique=False,
    )
    op.create_index(
        "uq_wms_pms_item_sku_code_one_primary",
        "wms_pms_item_sku_code_projection",
        ["item_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    op.create_table(
        "wms_pms_item_barcode_projection",
        sa.Column("barcode_id", sa.BigInteger(), nullable=False, autoincrement=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_uom_id", sa.Integer(), nullable=False),
        sa.Column("barcode", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("symbology", sa.Text(), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_event_id", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.BigInteger(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
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
        sa.PrimaryKeyConstraint("barcode_id", name="pk_wms_pms_item_barcode_projection"),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["wms_pms_item_projection.item_id"],
            name="fk_wms_pms_item_barcode_projection_item",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["item_uom_id", "item_id"],
            [
                "wms_pms_item_uom_projection.item_uom_id",
                "wms_pms_item_uom_projection.item_id",
            ],
            name="fk_wms_pms_item_barcode_projection_uom_pair",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("barcode", name="uq_wms_pms_item_barcode_barcode"),
        sa.CheckConstraint(
            "NOT is_primary OR active",
            name="ck_wms_pms_barcode_primary_active",
        ),
    )
    op.create_index(
        "ix_wms_pms_item_barcode_item_id",
        "wms_pms_item_barcode_projection",
        ["item_id"],
        unique=False,
    )
    op.create_index(
        "ix_wms_pms_item_barcode_item_uom_id",
        "wms_pms_item_barcode_projection",
        ["item_uom_id"],
        unique=False,
    )
    op.create_index(
        "uq_wms_pms_item_barcode_one_primary",
        "wms_pms_item_barcode_projection",
        ["item_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index("uq_wms_pms_item_barcode_one_primary", table_name="wms_pms_item_barcode_projection")
    op.drop_index("ix_wms_pms_item_barcode_item_uom_id", table_name="wms_pms_item_barcode_projection")
    op.drop_index("ix_wms_pms_item_barcode_item_id", table_name="wms_pms_item_barcode_projection")
    op.drop_table("wms_pms_item_barcode_projection")

    op.drop_index("uq_wms_pms_item_sku_code_one_primary", table_name="wms_pms_item_sku_code_projection")
    op.drop_index("ix_wms_pms_item_sku_code_item_id", table_name="wms_pms_item_sku_code_projection")
    op.drop_table("wms_pms_item_sku_code_projection")

    op.drop_table("wms_pms_item_policy_projection")

    op.drop_index("uq_wms_pms_item_uom_one_outbound_default", table_name="wms_pms_item_uom_projection")
    op.drop_index("uq_wms_pms_item_uom_one_inbound_default", table_name="wms_pms_item_uom_projection")
    op.drop_index("uq_wms_pms_item_uom_one_purchase_default", table_name="wms_pms_item_uom_projection")
    op.drop_index("uq_wms_pms_item_uom_one_base", table_name="wms_pms_item_uom_projection")
    op.drop_index("ix_wms_pms_item_uom_item_id", table_name="wms_pms_item_uom_projection")
    op.drop_table("wms_pms_item_uom_projection")

    op.drop_index("ix_wms_pms_item_projection_category_id", table_name="wms_pms_item_projection")
    op.drop_index("ix_wms_pms_item_projection_brand_id", table_name="wms_pms_item_projection")
    op.drop_index("ix_wms_pms_item_projection_enabled", table_name="wms_pms_item_projection")
    op.drop_table("wms_pms_item_projection")
