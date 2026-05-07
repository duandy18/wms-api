"""add wms logistics export records

Revision ID: ec6037fb0e66
Revises: '07c12e35bf8e'
Create Date: 2026-05-07

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "ec6037fb0e66"
down_revision: str | Sequence[str] | None = '07c12e35bf8e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLE_NAME = "wms_logistics_export_records"


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("source_doc_type", sa.String(length=32), nullable=False, comment="WMS 来源单据类型：ORDER_OUTBOUND / MANUAL_OUTBOUND"),
        sa.Column("source_doc_id", sa.BigInteger(), nullable=False, comment="WMS 来源单据主键：orders.id 或 manual_outbound_docs.id"),
        sa.Column("source_doc_no", sa.String(length=128), nullable=False, comment="WMS 来源单据展示号：平台订单号或手工出库单号"),
        sa.Column("source_ref", sa.String(length=192), nullable=False, comment="WMS 到 Logistics 的稳定幂等键"),
        sa.Column("export_status", sa.String(length=16), nullable=False, server_default="PENDING", comment="交接导出状态：PENDING / EXPORTED / FAILED / CANCELLED"),
        sa.Column("logistics_status", sa.String(length=16), nullable=False, server_default="NOT_IMPORTED", comment="Logistics 处理状态：NOT_IMPORTED / IMPORTED / IN_PROGRESS / COMPLETED / FAILED"),
        sa.Column("logistics_request_id", sa.BigInteger(), nullable=True, comment="Logistics 发货请求 ID"),
        sa.Column("logistics_request_no", sa.String(length=64), nullable=True, comment="Logistics 发货请求号"),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True, comment="Logistics 成功导入时间"),
        sa.Column("logistics_completed_at", sa.DateTime(timezone=True), nullable=True, comment="Logistics 物流处理完成时间"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True, comment="最近一次导入/回写尝试时间"),
        sa.Column("last_error", sa.Text(), nullable=True, comment="最近一次失败原因"),
        sa.Column(
            "source_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="创建交接记录时的 WMS 来源快照",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_wms_logistics_export_records"),
        sa.UniqueConstraint("source_doc_type", "source_doc_id", name="uq_wms_logistics_export_records_doc"),
        sa.UniqueConstraint("source_ref", name="uq_wms_logistics_export_records_source_ref"),
        sa.CheckConstraint("source_doc_type IN ('ORDER_OUTBOUND', 'MANUAL_OUTBOUND')", name="ck_wms_logistics_export_records_doc_type"),
        sa.CheckConstraint("export_status IN ('PENDING', 'EXPORTED', 'FAILED', 'CANCELLED')", name="ck_wms_logistics_export_records_export_status"),
        sa.CheckConstraint("logistics_status IN ('NOT_IMPORTED', 'IMPORTED', 'IN_PROGRESS', 'COMPLETED', 'FAILED')", name="ck_wms_logistics_export_records_logistics_status"),
    )

    op.create_index(
        "ix_wms_logistics_export_records_export_status",
        TABLE_NAME,
        ["export_status", "logistics_status"],
    )
    op.create_index(
        "ix_wms_logistics_export_records_doc_type",
        TABLE_NAME,
        ["source_doc_type", "source_doc_id"],
    )
    op.create_index(
        "ix_wms_logistics_export_records_request_no",
        TABLE_NAME,
        ["logistics_request_no"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_wms_logistics_export_records_touch_updated_at()
        RETURNS trigger AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_wms_logistics_export_records_updated_at
        BEFORE UPDATE ON wms_logistics_export_records
        FOR EACH ROW
        EXECUTE FUNCTION trg_wms_logistics_export_records_touch_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_wms_logistics_export_records_updated_at ON wms_logistics_export_records")
    op.execute("DROP FUNCTION IF EXISTS trg_wms_logistics_export_records_touch_updated_at")
    op.drop_index("ix_wms_logistics_export_records_request_no", table_name=TABLE_NAME)
    op.drop_index("ix_wms_logistics_export_records_doc_type", table_name=TABLE_NAME)
    op.drop_index("ix_wms_logistics_export_records_export_status", table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
