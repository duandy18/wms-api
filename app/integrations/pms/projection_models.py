# app/integrations/pms/projection_models.py
"""
WMS-owned PMS read projection ORM models.

These tables are WMS local read indexes for PMS current state.

Boundary:
- PMS owner runtime remains in pms-api.
- These tables are not PMS owner tables.
- These tables must be populated by a sync job that reads pms-api read-v1 HTTP.
- Business writes must not write these tables directly.
- These tables do not replace snapshot facts.
- These tables do not replace HTTP validation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


PROJECTION_TABLE_INFO = {
    "owner": "wms-api",
    "source_owner": "pms-api",
    "projection": True,
    "read_only_index": True,
}


class WmsPmsItemProjection(Base):
    __tablename__ = "wms_pms_item_projection"
    __table_args__ = (
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
        sa.Index("ix_wms_pms_item_projection_enabled", "enabled"),
        sa.Index("ix_wms_pms_item_projection_name", "name"),
        sa.Index("ix_wms_pms_item_projection_synced_at", "synced_at"),
        {"info": PROJECTION_TABLE_INFO},
    )

    item_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=False)

    sku: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    spec: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    )

    supplier_id: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    brand: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)

    expiry_policy: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    shelf_life_value: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    shelf_life_unit: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
    lot_source_policy: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    derivation_allowed: Mapped[bool | None] = mapped_column(sa.Boolean(), nullable=True)
    uom_governance_enabled: Mapped[bool | None] = mapped_column(sa.Boolean(), nullable=True)

    pms_updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    source_hash: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    sync_version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


class WmsPmsUomProjection(Base):
    __tablename__ = "wms_pms_uom_projection"
    __table_args__ = (
        sa.UniqueConstraint("item_id", "uom", name="uq_wms_pms_uom_projection_item_uom"),
        sa.CheckConstraint(
            "ratio_to_base >= 1",
            name="ck_wms_pms_uom_projection_ratio_ge_1",
        ),
        sa.Index("ix_wms_pms_uom_projection_item_id", "item_id"),
        sa.Index("ix_wms_pms_uom_projection_synced_at", "synced_at"),
        {"info": PROJECTION_TABLE_INFO},
    )

    item_uom_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=False)
    item_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    uom: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    display_name: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    uom_name: Mapped[str] = mapped_column(sa.String(32), nullable=False)

    ratio_to_base: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    net_weight_kg: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 3), nullable=True)

    is_base: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    is_purchase_default: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    is_inbound_default: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    is_outbound_default: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )

    pms_updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    source_hash: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    sync_version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


class WmsPmsSkuCodeProjection(Base):
    __tablename__ = "wms_pms_sku_code_projection"
    __table_args__ = (
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
        sa.Index("ix_wms_pms_sku_code_projection_item_id", "item_id"),
        sa.Index("ix_wms_pms_sku_code_projection_is_active", "is_active"),
        sa.Index("ix_wms_pms_sku_code_projection_synced_at", "synced_at"),
        {"info": PROJECTION_TABLE_INFO},
    )

    sku_code_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=False)
    item_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    sku_code: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    code_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    is_primary: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    )

    effective_from: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    pms_updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    source_hash: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    sync_version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


class WmsPmsBarcodeProjection(Base):
    __tablename__ = "wms_pms_barcode_projection"
    __table_args__ = (
        sa.UniqueConstraint("barcode", name="uq_wms_pms_barcode_projection_barcode"),
        sa.CheckConstraint(
            "length(trim(barcode)) > 0",
            name="ck_wms_pms_barcode_projection_barcode_non_empty",
        ),
        sa.CheckConstraint(
            "is_primary = false OR active = true",
            name="ck_wms_pms_barcode_projection_primary_active",
        ),
        sa.Index("ix_wms_pms_barcode_projection_item_id", "item_id"),
        sa.Index("ix_wms_pms_barcode_projection_item_uom_id", "item_uom_id"),
        sa.Index("ix_wms_pms_barcode_projection_active", "active"),
        sa.Index("ix_wms_pms_barcode_projection_synced_at", "synced_at"),
        {"info": PROJECTION_TABLE_INFO},
    )

    barcode_id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=False)
    item_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    item_uom_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    barcode: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    symbology: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    active: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    )
    is_primary: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )

    pms_updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    source_hash: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    sync_version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


__all__ = [
    "WmsPmsBarcodeProjection",
    "WmsPmsItemProjection",
    "WmsPmsSkuCodeProjection",
    "WmsPmsUomProjection",
]
