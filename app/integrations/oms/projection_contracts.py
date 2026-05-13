# app/integrations/oms/projection_contracts.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OmsFulfillmentReadyPlatform = Literal["pdd", "taobao", "jd"]
OmsFulfillmentReadyStatus = Literal["READY"]
OmsFulfillmentLineIdentityKind = Literal[
    "merchant_code",
    "platform_sku_id",
    "platform_item_sku",
]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OmsFulfillmentReadyComponentIn(_Base):
    ready_component_id: str
    ready_line_id: str

    resolved_item_id: int
    resolved_item_sku_code_id: int
    resolved_item_uom_id: int

    component_sku_code: str
    sku_code_snapshot: str
    item_name_snapshot: str
    uom_snapshot: str

    qty_per_fsku: Decimal
    required_qty: Decimal
    alloc_unit_price: Decimal
    sort_order: int


class OmsFulfillmentReadyLineIn(_Base):
    ready_line_id: str
    source_line_id: int

    identity_kind: OmsFulfillmentLineIdentityKind
    identity_value: str

    merchant_sku: str | None = None
    platform_item_id: str | None = None
    platform_sku_id: str | None = None
    platform_goods_name: str | None = None
    platform_sku_name: str | None = None

    ordered_qty: Decimal

    fsku_id: int
    fsku_code: str
    fsku_name: str
    fsku_status_snapshot: str

    components: list[OmsFulfillmentReadyComponentIn] = Field(default_factory=list)


class OmsFulfillmentReadyOrderIn(_Base):
    ready_order_id: str
    source_order_id: int

    platform: OmsFulfillmentReadyPlatform
    store_code: str
    store_name: str
    platform_order_no: str
    platform_status: str | None = None

    receiver_name: str
    receiver_phone: str
    receiver_province: str
    receiver_city: str
    receiver_district: str | None = None
    receiver_address: str
    receiver_postcode: str | None = None

    buyer_remark: str | None = None
    seller_remark: str | None = None

    ready_status: OmsFulfillmentReadyStatus = "READY"
    ready_at: datetime
    source_updated_at: datetime

    lines: list[OmsFulfillmentReadyLineIn] = Field(default_factory=list)


class OmsFulfillmentReadyListDataIn(_Base):
    items: list[OmsFulfillmentReadyOrderIn] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class OmsFulfillmentReadyListEnvelopeIn(_Base):
    ok: bool = True
    data: OmsFulfillmentReadyListDataIn


__all__ = [
    "OmsFulfillmentLineIdentityKind",
    "OmsFulfillmentReadyComponentIn",
    "OmsFulfillmentReadyLineIn",
    "OmsFulfillmentReadyListDataIn",
    "OmsFulfillmentReadyListEnvelopeIn",
    "OmsFulfillmentReadyOrderIn",
    "OmsFulfillmentReadyPlatform",
    "OmsFulfillmentReadyStatus",
]
