# app/wms/outbound/models/logistics_export_record.py
# WMS -> Logistics 交接状态表模型。
from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WmsLogisticsExportRecord(Base):
    """
    wms_logistics_export_records：WMS 出库事实交接给 Logistics 的状态表。

    - WMS 订单出库完成：source_doc_type = ORDER_OUTBOUND
    - WMS 手工出库完成：source_doc_type = MANUAL_OUTBOUND
    - export_status：WMS 交接导出状态
    - logistics_status：Logistics 处理状态
    """

    __tablename__ = "wms_logistics_export_records"

    __table_args__ = (
        sa.UniqueConstraint("source_doc_type", "source_doc_id", name="uq_wms_logistics_export_records_doc"),
        sa.UniqueConstraint("source_ref", name="uq_wms_logistics_export_records_source_ref"),
        sa.CheckConstraint(
            "source_doc_type IN ('ORDER_OUTBOUND', 'MANUAL_OUTBOUND')",
            name="ck_wms_logistics_export_records_doc_type",
        ),
        sa.CheckConstraint(
            "export_status IN ('PENDING', 'EXPORTED', 'FAILED', 'CANCELLED')",
            name="ck_wms_logistics_export_records_export_status",
        ),
        sa.CheckConstraint(
            "logistics_status IN ('NOT_IMPORTED', 'IMPORTED', 'IN_PROGRESS', 'COMPLETED', 'FAILED')",
            name="ck_wms_logistics_export_records_logistics_status",
        ),
        sa.Index("ix_wms_logistics_export_records_export_status", "export_status", "logistics_status"),
        sa.Index("ix_wms_logistics_export_records_doc_type", "source_doc_type", "source_doc_id"),
        sa.Index("ix_wms_logistics_export_records_request_no", "logistics_request_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    source_doc_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="WMS 来源单据类型：ORDER_OUTBOUND / MANUAL_OUTBOUND",
    )
    source_doc_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="WMS 来源单据主键：orders.id 或 manual_outbound_docs.id",
    )
    source_doc_no: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="WMS 来源单据展示号：平台订单号或手工出库单号",
    )
    source_ref: Mapped[str] = mapped_column(
        String(192),
        nullable=False,
        comment="WMS 到 Logistics 的稳定幂等键",
    )

    export_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="PENDING",
        comment="交接导出状态：PENDING / EXPORTED / FAILED / CANCELLED",
    )
    logistics_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="NOT_IMPORTED",
        comment="Logistics 处理状态：NOT_IMPORTED / IMPORTED / IN_PROGRESS / COMPLETED / FAILED",
    )

    logistics_request_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Logistics 发货请求 ID",
    )
    logistics_request_no: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Logistics 发货请求号",
    )

    exported_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Logistics 成功导入时间",
    )
    logistics_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Logistics 物流处理完成时间",
    )
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最近一次导入/回写尝试时间",
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="最近一次失败原因",
    )

    source_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="创建交接记录时的 WMS 来源快照",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
