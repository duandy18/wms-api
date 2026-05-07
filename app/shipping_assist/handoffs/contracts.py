# app/shipping_assist/handoffs/contracts.py
#
# 分拆说明：
# - 本文件承载 Shipping Assist / Handoffs（发货交接）只读合同；
# - 状态来自 wms_logistics_export_records；
# - 交接数据来自 wms_logistics_handoff_payloads；
# - 发货交接页只观察 WMS -> Logistics 交接状态，不写 shipping_records。
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShippingHandoffShipmentItem(_Base):
    source_line_type: str
    source_line_id: int | None = None
    source_line_no: int | None = None
    item_id: int | None = None
    item_sku_snapshot: str | None = None
    item_name_snapshot: str | None = None
    item_spec_snapshot: str | None = None
    qty_outbound: int


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

    source_system: str = "WMS"
    request_source: str = "API_IMPORT"

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

    shipment_items: list[ShippingHandoffShipmentItem] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime


class ShippingHandoffListResponse(_Base):
    ok: bool = True
    rows: list[ShippingHandoffRow]
    total: int
