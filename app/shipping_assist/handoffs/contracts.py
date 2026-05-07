# app/shipping_assist/handoffs/contracts.py
#
# 分拆说明：
# - 本文件承载 Shipping Assist / Handoffs（发货交接）只读合同；
# - 主数据源是 wms_logistics_export_records；
# - 发货交接页只观察 WMS -> Logistics 交接状态，不写 shipping_records。
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShippingHandoffRow(_Base):
    id: int

    source_doc_type: str
    source_doc_id: int
    source_doc_no: str
    source_ref: str

    export_status: str
    logistics_status: str

    logistics_request_id: int | None = None
    logistics_request_no: str | None = None

    exported_at: datetime | None = None
    logistics_completed_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_error: str | None = None

    source_snapshot: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime
    updated_at: datetime


class ShippingHandoffListResponse(_Base):
    ok: bool = True
    rows: list[ShippingHandoffRow]
    total: int
