# app/wms/outbound/contracts/logistics_ready.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class LogisticsReadyItemOut(_Base):
    line_no: int
    item_id: int | None = None
    qty: int
    lot_id: int | None = None
    lot_code_snapshot: str | None = None
    item_name_snapshot: str | None = None
    item_sku_snapshot: str | None = None
    item_spec_snapshot: str | None = None


class LogisticsReadyPackageOut(_Base):
    source_package_ref: str
    package_no: int
    warehouse_id: int | None = None
    weight_kg: str | None = None
    items: list[LogisticsReadyItemOut] = Field(default_factory=list)


class LogisticsReadyRowOut(_Base):
    source_system: str = "WMS"
    source_doc_type: str
    source_doc_id: int
    source_doc_no: str
    source_ref: str

    export_status: str
    logistics_status: str

    platform: str | None = None
    store_code: str | None = None
    platform_order_no: str | None = None
    warehouse_id: int | None = None

    receiver_name: str | None = None
    receiver_phone: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None
    address_detail: str | None = None

    outbound_completed_at: datetime | None = None
    handoff_created_at: datetime
    handoff_updated_at: datetime

    packages: list[LogisticsReadyPackageOut] = Field(default_factory=list)
    source_snapshot: dict[str, Any] = Field(default_factory=dict)


class LogisticsReadyListOut(_Base):
    ok: bool = True
    rows: list[LogisticsReadyRowOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
