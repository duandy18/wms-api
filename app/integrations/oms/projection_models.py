# app/integrations/oms/projection_models.py
"""
WMS-owned OMS fulfillment read projection ORM models.

Boundary:
- OMS owner runtime remains in oms-api.
- Source must be oms-api /oms/read/v1/fulfillment-ready-orders.
- These tables are WMS local read indexes for OMS fulfillment-ready output.
- These tables must not be used as OMS owner tables.
- These tables must not be written by WMS business workflows directly.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


PROJECTION_TABLE_INFO = {
    "owner": "wms-api",
    "source_owner": "oms-api",
    "projection": True,
    "read_only_index": True,
}


class WmsOmsFulfillmentOrderProjection(Base):
    __tablename__ = "wms_oms_fulfillment_order_projection"
    __table_args__ = (
        sa.UniqueConstraint(
            "platform",
            "store_code",
            "platform_order_no",
            name="uq_wms_oms_fulfill_order_platform_store_no",
        ),
        sa.CheckConstraint(
            "platform IN ('pdd', 'taobao', 'jd')",
            name="ck_wms_oms_fulfill_order_platform",
        ),
        sa.CheckConstraint(
            "ready_status = 'READY'",
            name="ck_wms_oms_fulfill_order_ready_status",
        ),
        sa.CheckConstraint(
            "line_count >= 0",
            name="ck_wms_oms_fulfill_order_line_count_ge0",
        ),
        sa.CheckConstraint(
            "component_count >= 0",
            name="ck_wms_oms_fulfill_order_component_count_ge0",
        ),
        sa.CheckConstraint(
            "total_required_qty >= 0",
            name="ck_wms_oms_fulfill_order_required_qty_ge0",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_order_platform_store",
            "platform",
            "store_code",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_order_ready_status",
            "ready_status",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_order_source_updated_at",
            "source_updated_at",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_order_synced_at",
            "synced_at",
        ),
        {"info": PROJECTION_TABLE_INFO},
    )

    ready_order_id: Mapped[str] = mapped_column(sa.String(192), primary_key=True)
    source_order_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    platform: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    store_code: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    store_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    platform_order_no: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    platform_status: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)

    receiver_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    receiver_phone: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    receiver_province: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    receiver_city: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    receiver_district: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    receiver_address: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    receiver_postcode: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)

    buyer_remark: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    seller_remark: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    ready_status: Mapped[str] = mapped_column(
        sa.String(16),
        nullable=False,
        server_default=sa.text("'READY'"),
    )
    ready_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    line_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    component_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    total_required_qty: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 6),
        nullable=False,
        server_default=sa.text("0"),
    )

    source_hash: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    sync_version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


class WmsOmsFulfillmentLineProjection(Base):
    __tablename__ = "wms_oms_fulfillment_line_projection"
    __table_args__ = (
        sa.UniqueConstraint(
            "ready_order_id",
            "source_line_id",
            name="uq_wms_oms_fulfill_line_order_source_line",
        ),
        sa.CheckConstraint(
            "identity_kind IN ('merchant_code', 'platform_sku_id', 'platform_item_sku')",
            name="ck_wms_oms_fulfill_line_identity_kind",
        ),
        sa.CheckConstraint(
            "ordered_qty > 0",
            name="ck_wms_oms_fulfill_line_ordered_qty_pos",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_line_ready_order",
            "ready_order_id",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_line_identity",
            "platform",
            "store_code",
            "identity_kind",
            "identity_value",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_line_fsku_id",
            "fsku_id",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_line_synced_at",
            "synced_at",
        ),
        {"info": PROJECTION_TABLE_INFO},
    )

    ready_line_id: Mapped[str] = mapped_column(sa.String(192), primary_key=True)
    ready_order_id: Mapped[str] = mapped_column(sa.String(192), nullable=False)
    source_line_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    platform: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    store_code: Mapped[str] = mapped_column(sa.String(128), nullable=False)

    identity_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    identity_value: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    merchant_sku: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    platform_item_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    platform_sku_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    platform_goods_name: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    platform_sku_name: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)

    ordered_qty: Mapped[Decimal] = mapped_column(sa.Numeric(18, 6), nullable=False)

    fsku_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    fsku_code: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    fsku_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    fsku_status_snapshot: Mapped[str] = mapped_column(sa.String(32), nullable=False)

    source_hash: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    sync_version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


class WmsOmsFulfillmentComponentProjection(Base):
    __tablename__ = "wms_oms_fulfillment_component_projection"
    __table_args__ = (
        sa.UniqueConstraint(
            "ready_line_id",
            "sort_order",
            "resolved_item_id",
            "resolved_item_sku_code_id",
            "resolved_item_uom_id",
            name="uq_wms_oms_fulfill_component_line_component",
        ),
        sa.CheckConstraint(
            "qty_per_fsku > 0",
            name="ck_wms_oms_fulfill_component_qty_per_fsku_pos",
        ),
        sa.CheckConstraint(
            "required_qty > 0",
            name="ck_wms_oms_fulfill_component_required_qty_pos",
        ),
        sa.CheckConstraint(
            "alloc_unit_price >= 0",
            name="ck_wms_oms_fulfill_component_alloc_price_ge0",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_wms_oms_fulfill_component_sort_order_ge0",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_component_ready_order",
            "ready_order_id",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_component_ready_line",
            "ready_line_id",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_component_item_id",
            "resolved_item_id",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_component_sku_code_id",
            "resolved_item_sku_code_id",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_component_synced_at",
            "synced_at",
        ),
        {"info": PROJECTION_TABLE_INFO},
    )

    ready_component_id: Mapped[str] = mapped_column(sa.String(256), primary_key=True)
    ready_line_id: Mapped[str] = mapped_column(sa.String(192), nullable=False)
    ready_order_id: Mapped[str] = mapped_column(sa.String(192), nullable=False)

    resolved_item_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    resolved_item_sku_code_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    resolved_item_uom_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    component_sku_code: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    sku_code_snapshot: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    item_name_snapshot: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    uom_snapshot: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    qty_per_fsku: Mapped[Decimal] = mapped_column(sa.Numeric(18, 6), nullable=False)
    required_qty: Mapped[Decimal] = mapped_column(sa.Numeric(18, 6), nullable=False)
    alloc_unit_price: Mapped[Decimal] = mapped_column(sa.Numeric(18, 6), nullable=False)
    sort_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    source_hash: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    sync_version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


class WmsOmsFulfillmentOrderImport(Base):
    __tablename__ = "wms_oms_fulfillment_order_imports"
    __table_args__ = (
        sa.UniqueConstraint(
            "order_id",
            name="uq_wms_oms_fulfill_order_import_order_id",
        ),
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
        sa.Index(
            "ix_wms_oms_fulfill_order_import_imported_at",
            "imported_at",
        ),
        {"info": {"owner": "wms-api", "projection_import_audit": True}},
    )

    ready_order_id: Mapped[str] = mapped_column(sa.String(192), primary_key=True)
    order_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey(
            "orders.id",
            name="fk_wms_oms_fulfill_order_import_order",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    platform: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    store_code: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    platform_order_no: Mapped[str] = mapped_column(sa.String(128), nullable=False)

    source_order_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    source_hash: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)

    import_status: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
        server_default=sa.text("'IMPORTED'"),
    )
    order_line_count: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        server_default=sa.text("0"),
    )
    component_count: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        server_default=sa.text("0"),
    )

    imported_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    imported_by_user_id: Mapped[int | None] = mapped_column(
        sa.Integer,
        sa.ForeignKey(
            "users.id",
            name="fk_wms_oms_fulfill_order_import_user",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)


class WmsOmsFulfillmentComponentImport(Base):
    __tablename__ = "wms_oms_fulfillment_component_imports"
    __table_args__ = (
        sa.UniqueConstraint(
            "order_line_id",
            name="uq_wms_oms_fulfill_component_import_order_line",
        ),
        sa.CheckConstraint(
            "required_qty > 0",
            name="ck_wms_oms_fulfill_component_import_required_qty_pos",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_component_import_ready_order",
            "ready_order_id",
        ),
        {"info": {"owner": "wms-api", "projection_import_audit": True}},
    )

    ready_component_id: Mapped[str] = mapped_column(sa.String(256), primary_key=True)
    ready_order_id: Mapped[str] = mapped_column(
        sa.String(192),
        sa.ForeignKey(
            "wms_oms_fulfillment_order_imports.ready_order_id",
            name="fk_wms_oms_fulfill_component_import_order_import",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    ready_line_id: Mapped[str] = mapped_column(sa.String(192), nullable=False)

    order_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey(
            "orders.id",
            name="fk_wms_oms_fulfill_component_import_order",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    order_line_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey(
            "order_lines.id",
            name="fk_wms_oms_fulfill_component_import_order_line",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    resolved_item_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    resolved_item_sku_code_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    resolved_item_uom_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    component_sku_code: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    sku_code_snapshot: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    item_name_snapshot: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    uom_snapshot: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    required_qty: Mapped[Decimal] = mapped_column(sa.Numeric(18, 6), nullable=False)
    source_hash: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)

    imported_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


class WmsOmsFulfillmentProjectionSyncRun(Base):
    __tablename__ = "wms_oms_fulfillment_projection_sync_runs"
    __table_args__ = (
        sa.CheckConstraint(
            "resource IN ('fulfillment-ready-orders', 'all')",
            name="ck_wms_oms_fulfill_sync_resource",
        ),
        sa.CheckConstraint(
            "platform IS NULL OR platform IN ('pdd', 'taobao', 'jd')",
            name="ck_wms_oms_fulfill_sync_platform",
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCESS', 'FAILED')",
            name="ck_wms_oms_fulfill_sync_status",
        ),
        sa.CheckConstraint(
            "fetched >= 0",
            name="ck_wms_oms_fulfill_sync_fetched_ge0",
        ),
        sa.CheckConstraint(
            "upserted_orders >= 0",
            name="ck_wms_oms_fulfill_sync_orders_ge0",
        ),
        sa.CheckConstraint(
            "upserted_lines >= 0",
            name="ck_wms_oms_fulfill_sync_lines_ge0",
        ),
        sa.CheckConstraint(
            "upserted_components >= 0",
            name="ck_wms_oms_fulfill_sync_components_ge0",
        ),
        sa.CheckConstraint(
            "pages >= 0",
            name="ck_wms_oms_fulfill_sync_pages_ge0",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_wms_oms_fulfill_sync_duration_ge0",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_sync_started_at",
            "started_at",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_sync_platform_started",
            "platform",
            "started_at",
        ),
        sa.Index(
            "ix_wms_oms_fulfill_sync_status",
            "status",
        ),
        {"info": {"owner": "wms-api", "projection_sync_log": True}},
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    resource: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    platform: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
    store_code: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)

    fetched: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    upserted_orders: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    upserted_lines: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    upserted_components: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))
    pages: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))

    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    triggered_by_user_id: Mapped[int | None] = mapped_column(
        sa.Integer,
        sa.ForeignKey(
            "users.id",
            name="fk_wms_oms_fulfill_sync_user",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    oms_api_base_url_snapshot: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    sync_version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)


__all__ = [
    "WmsOmsFulfillmentComponentProjection",
    "WmsOmsFulfillmentLineProjection",
    "WmsOmsFulfillmentOrderProjection",
    "WmsOmsFulfillmentOrderImport",
    "WmsOmsFulfillmentComponentImport",
    "WmsOmsFulfillmentProjectionSyncRun",
]
