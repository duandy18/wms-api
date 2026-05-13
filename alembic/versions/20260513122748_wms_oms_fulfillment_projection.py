# alembic/versions/20260513122748_wms_oms_fulfillment_projection.py
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260513122748_wms_oms_fulfillment_projection"
down_revision: str | Sequence[str] | None = "8a4f2d6c9b31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wms_oms_fulfillment_order_projection",
        sa.Column("ready_order_id", sa.String(length=192), nullable=False),
        sa.Column("source_order_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("store_code", sa.String(length=128), nullable=False),
        sa.Column("store_name", sa.String(length=255), nullable=False),
        sa.Column("platform_order_no", sa.String(length=128), nullable=False),
        sa.Column("platform_status", sa.String(length=64), nullable=True),
        sa.Column("receiver_name", sa.String(length=128), nullable=False),
        sa.Column("receiver_phone", sa.String(length=64), nullable=False),
        sa.Column("receiver_province", sa.String(length=64), nullable=False),
        sa.Column("receiver_city", sa.String(length=64), nullable=False),
        sa.Column("receiver_district", sa.String(length=64), nullable=True),
        sa.Column("receiver_address", sa.String(length=255), nullable=False),
        sa.Column("receiver_postcode", sa.String(length=32), nullable=True),
        sa.Column("buyer_remark", sa.Text(), nullable=True),
        sa.Column("seller_remark", sa.Text(), nullable=True),
        sa.Column("ready_status", sa.String(length=16), server_default=sa.text("'READY'"), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("line_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("component_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_required_qty", sa.Numeric(18, 6), server_default=sa.text("0"), nullable=False),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("sync_version", sa.String(length=64), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("platform IN ('pdd', 'taobao', 'jd')", name="ck_wms_oms_fulfill_order_platform"),
        sa.CheckConstraint("ready_status = 'READY'", name="ck_wms_oms_fulfill_order_ready_status"),
        sa.CheckConstraint("line_count >= 0", name="ck_wms_oms_fulfill_order_line_count_ge0"),
        sa.CheckConstraint("component_count >= 0", name="ck_wms_oms_fulfill_order_component_count_ge0"),
        sa.CheckConstraint("total_required_qty >= 0", name="ck_wms_oms_fulfill_order_required_qty_ge0"),
        sa.PrimaryKeyConstraint("ready_order_id"),
        sa.UniqueConstraint("platform", "store_code", "platform_order_no", name="uq_wms_oms_fulfill_order_platform_store_no"),
    )
    op.create_index("ix_wms_oms_fulfill_order_platform_store", "wms_oms_fulfillment_order_projection", ["platform", "store_code"])
    op.create_index("ix_wms_oms_fulfill_order_ready_status", "wms_oms_fulfillment_order_projection", ["ready_status"])
    op.create_index("ix_wms_oms_fulfill_order_source_updated_at", "wms_oms_fulfillment_order_projection", ["source_updated_at"])
    op.create_index("ix_wms_oms_fulfill_order_synced_at", "wms_oms_fulfillment_order_projection", ["synced_at"])

    op.create_table(
        "wms_oms_fulfillment_line_projection",
        sa.Column("ready_line_id", sa.String(length=192), nullable=False),
        sa.Column("ready_order_id", sa.String(length=192), nullable=False),
        sa.Column("source_line_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("store_code", sa.String(length=128), nullable=False),
        sa.Column("identity_kind", sa.String(length=32), nullable=False),
        sa.Column("identity_value", sa.String(length=255), nullable=False),
        sa.Column("merchant_sku", sa.String(length=255), nullable=True),
        sa.Column("platform_item_id", sa.String(length=128), nullable=True),
        sa.Column("platform_sku_id", sa.String(length=128), nullable=True),
        sa.Column("platform_goods_name", sa.String(length=512), nullable=True),
        sa.Column("platform_sku_name", sa.String(length=512), nullable=True),
        sa.Column("ordered_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("fsku_id", sa.BigInteger(), nullable=False),
        sa.Column("fsku_code", sa.String(length=128), nullable=False),
        sa.Column("fsku_name", sa.String(length=255), nullable=False),
        sa.Column("fsku_status_snapshot", sa.String(length=32), nullable=False),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("sync_version", sa.String(length=64), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("identity_kind IN ('merchant_code', 'platform_sku_id', 'platform_item_sku')", name="ck_wms_oms_fulfill_line_identity_kind"),
        sa.CheckConstraint("ordered_qty > 0", name="ck_wms_oms_fulfill_line_ordered_qty_pos"),
        sa.PrimaryKeyConstraint("ready_line_id"),
        sa.UniqueConstraint("ready_order_id", "source_line_id", name="uq_wms_oms_fulfill_line_order_source_line"),
    )
    op.create_index("ix_wms_oms_fulfill_line_ready_order", "wms_oms_fulfillment_line_projection", ["ready_order_id"])
    op.create_index("ix_wms_oms_fulfill_line_identity", "wms_oms_fulfillment_line_projection", ["platform", "store_code", "identity_kind", "identity_value"])
    op.create_index("ix_wms_oms_fulfill_line_fsku_id", "wms_oms_fulfillment_line_projection", ["fsku_id"])
    op.create_index("ix_wms_oms_fulfill_line_synced_at", "wms_oms_fulfillment_line_projection", ["synced_at"])

    op.create_table(
        "wms_oms_fulfillment_component_projection",
        sa.Column("ready_component_id", sa.String(length=256), nullable=False),
        sa.Column("ready_line_id", sa.String(length=192), nullable=False),
        sa.Column("ready_order_id", sa.String(length=192), nullable=False),
        sa.Column("resolved_item_id", sa.BigInteger(), nullable=False),
        sa.Column("resolved_item_sku_code_id", sa.BigInteger(), nullable=False),
        sa.Column("resolved_item_uom_id", sa.BigInteger(), nullable=False),
        sa.Column("component_sku_code", sa.String(length=128), nullable=False),
        sa.Column("sku_code_snapshot", sa.String(length=128), nullable=False),
        sa.Column("item_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("uom_snapshot", sa.String(length=64), nullable=False),
        sa.Column("qty_per_fsku", sa.Numeric(18, 6), nullable=False),
        sa.Column("required_qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("alloc_unit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("sync_version", sa.String(length=64), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("qty_per_fsku > 0", name="ck_wms_oms_fulfill_component_qty_per_fsku_pos"),
        sa.CheckConstraint("required_qty > 0", name="ck_wms_oms_fulfill_component_required_qty_pos"),
        sa.CheckConstraint("alloc_unit_price >= 0", name="ck_wms_oms_fulfill_component_alloc_price_ge0"),
        sa.CheckConstraint("sort_order >= 0", name="ck_wms_oms_fulfill_component_sort_order_ge0"),
        sa.PrimaryKeyConstraint("ready_component_id"),
        sa.UniqueConstraint(
            "ready_line_id",
            "sort_order",
            "resolved_item_id",
            "resolved_item_sku_code_id",
            "resolved_item_uom_id",
            name="uq_wms_oms_fulfill_component_line_component",
        ),
    )
    op.create_index("ix_wms_oms_fulfill_component_ready_order", "wms_oms_fulfillment_component_projection", ["ready_order_id"])
    op.create_index("ix_wms_oms_fulfill_component_ready_line", "wms_oms_fulfillment_component_projection", ["ready_line_id"])
    op.create_index("ix_wms_oms_fulfill_component_item_id", "wms_oms_fulfillment_component_projection", ["resolved_item_id"])
    op.create_index("ix_wms_oms_fulfill_component_sku_code_id", "wms_oms_fulfillment_component_projection", ["resolved_item_sku_code_id"])
    op.create_index("ix_wms_oms_fulfill_component_synced_at", "wms_oms_fulfillment_component_projection", ["synced_at"])

    op.create_table(
        "wms_oms_fulfillment_projection_sync_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("resource", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=True),
        sa.Column("store_code", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("fetched", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("upserted_orders", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("upserted_lines", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("upserted_components", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("pages", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("oms_api_base_url_snapshot", sa.String(length=512), nullable=True),
        sa.Column("sync_version", sa.String(length=64), nullable=True),
        sa.CheckConstraint("resource IN ('fulfillment-ready-orders', 'all')", name="ck_wms_oms_fulfill_sync_resource"),
        sa.CheckConstraint("platform IS NULL OR platform IN ('pdd', 'taobao', 'jd')", name="ck_wms_oms_fulfill_sync_platform"),
        sa.CheckConstraint("status IN ('RUNNING', 'SUCCESS', 'FAILED')", name="ck_wms_oms_fulfill_sync_status"),
        sa.CheckConstraint("fetched >= 0", name="ck_wms_oms_fulfill_sync_fetched_ge0"),
        sa.CheckConstraint("upserted_orders >= 0", name="ck_wms_oms_fulfill_sync_orders_ge0"),
        sa.CheckConstraint("upserted_lines >= 0", name="ck_wms_oms_fulfill_sync_lines_ge0"),
        sa.CheckConstraint("upserted_components >= 0", name="ck_wms_oms_fulfill_sync_components_ge0"),
        sa.CheckConstraint("pages >= 0", name="ck_wms_oms_fulfill_sync_pages_ge0"),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_wms_oms_fulfill_sync_duration_ge0"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], name="fk_wms_oms_fulfill_sync_user", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wms_oms_fulfill_sync_started_at", "wms_oms_fulfillment_projection_sync_runs", ["started_at"])
    op.create_index("ix_wms_oms_fulfill_sync_platform_started", "wms_oms_fulfillment_projection_sync_runs", ["platform", "started_at"])
    op.create_index("ix_wms_oms_fulfill_sync_status", "wms_oms_fulfillment_projection_sync_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_wms_oms_fulfill_sync_status", table_name="wms_oms_fulfillment_projection_sync_runs")
    op.drop_index("ix_wms_oms_fulfill_sync_platform_started", table_name="wms_oms_fulfillment_projection_sync_runs")
    op.drop_index("ix_wms_oms_fulfill_sync_started_at", table_name="wms_oms_fulfillment_projection_sync_runs")
    op.drop_table("wms_oms_fulfillment_projection_sync_runs")

    op.drop_index("ix_wms_oms_fulfill_component_synced_at", table_name="wms_oms_fulfillment_component_projection")
    op.drop_index("ix_wms_oms_fulfill_component_sku_code_id", table_name="wms_oms_fulfillment_component_projection")
    op.drop_index("ix_wms_oms_fulfill_component_item_id", table_name="wms_oms_fulfillment_component_projection")
    op.drop_index("ix_wms_oms_fulfill_component_ready_line", table_name="wms_oms_fulfillment_component_projection")
    op.drop_index("ix_wms_oms_fulfill_component_ready_order", table_name="wms_oms_fulfillment_component_projection")
    op.drop_table("wms_oms_fulfillment_component_projection")

    op.drop_index("ix_wms_oms_fulfill_line_synced_at", table_name="wms_oms_fulfillment_line_projection")
    op.drop_index("ix_wms_oms_fulfill_line_fsku_id", table_name="wms_oms_fulfillment_line_projection")
    op.drop_index("ix_wms_oms_fulfill_line_identity", table_name="wms_oms_fulfillment_line_projection")
    op.drop_index("ix_wms_oms_fulfill_line_ready_order", table_name="wms_oms_fulfillment_line_projection")
    op.drop_table("wms_oms_fulfillment_line_projection")

    op.drop_index("ix_wms_oms_fulfill_order_synced_at", table_name="wms_oms_fulfillment_order_projection")
    op.drop_index("ix_wms_oms_fulfill_order_source_updated_at", table_name="wms_oms_fulfillment_order_projection")
    op.drop_index("ix_wms_oms_fulfill_order_ready_status", table_name="wms_oms_fulfillment_order_projection")
    op.drop_index("ix_wms_oms_fulfill_order_platform_store", table_name="wms_oms_fulfillment_order_projection")
    op.drop_table("wms_oms_fulfillment_order_projection")
