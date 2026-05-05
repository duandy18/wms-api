from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ResolutionStatus = Literal["resolved", "needs_mapping"]
ResolutionSource = Literal["direct_fsku_code", "code_mapping", "unresolved"]
IdentityKind = Literal["merchant_code", "platform_sku_id", "platform_item_sku"]


class OrderSkuResolutionNextActionOut(BaseModel):
    action: str
    label: str
    route_path: str
    payload: dict[str, str | int | None] = Field(default_factory=dict)


class OrderSkuResolutionComponentOut(BaseModel):
    item_id: int
    item_sku_code_id: int | None = None
    item_uom_id: int | None = None

    sku_code: str
    item_name: str
    uom: str

    qty: str
    alloc_unit_price: str
    sort_order: int


class OrderSkuResolutionLineOut(BaseModel):
    platform: str
    mirror_id: int
    line_id: int
    collector_order_id: int
    collector_line_id: int

    store_code: str
    platform_order_no: str

    merchant_code: str | None = None
    platform_item_id: str | None = None
    platform_sku_id: str | None = None
    title: str | None = None
    quantity: str
    line_amount: str | None = None

    resolution_status: ResolutionStatus
    resolution_source: ResolutionSource

    resolved_identity_kind: IdentityKind | None = None
    resolved_identity_value: str | None = None

    fsku_id: int | None = None
    fsku_code: str | None = None
    fsku_name: str | None = None

    unresolved_reason: str | None = None
    next_actions: list[OrderSkuResolutionNextActionOut] = Field(default_factory=list)
    components: list[OrderSkuResolutionComponentOut] = Field(default_factory=list)


class OrderSkuResolutionDataOut(BaseModel):
    platform: str
    mirror_id: int
    platform_order_no: str
    store_code: str
    status: ResolutionStatus
    lines: list[OrderSkuResolutionLineOut] = Field(default_factory=list)


class OrderSkuResolutionOut(BaseModel):
    ok: bool = True
    data: OrderSkuResolutionDataOut
