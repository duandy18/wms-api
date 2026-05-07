# app/wms/outbound/contracts/logistics_ready.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class LogisticsReadyShipmentItemOut(_Base):
    source_line_type: str
    source_line_id: int | None = None
    source_line_no: int | None = None
    item_id: int | None = None
    item_sku_snapshot: str | None = None
    item_name_snapshot: str | None = None
    item_spec_snapshot: str | None = None
    qty_outbound: int


class LogisticsReadyRowOut(_Base):
    source_system: str = "WMS"
    request_source: str = "API_IMPORT"

    source_doc_type: str
    source_doc_id: int
    source_doc_no: str
    source_ref: str

    export_status: str
    logistics_status: str

    platform: str | None = None
    store_code: str | None = None
    order_ref: str | None = None
    ext_order_no: str | None = None

    warehouse_id: int | None = None
    warehouse_name_snapshot: str | None = None

    receiver_name: str | None = None
    receiver_phone: str | None = None
    receiver_province: str | None = None
    receiver_city: str | None = None
    receiver_district: str | None = None
    receiver_address: str | None = None
    receiver_postcode: str | None = None

    outbound_event_id: int | None = None
    outbound_source_ref: str | None = None
    outbound_completed_at: datetime | None = None

    shipment_items: list[LogisticsReadyShipmentItemOut] = Field(default_factory=list)

    handoff_created_at: datetime
    handoff_updated_at: datetime


class LogisticsReadyListOut(_Base):
    ok: bool = True
    rows: list[LogisticsReadyRowOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
