from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProcurementPurchaseOrderStatus = Literal["CREATED", "CLOSED", "CANCELED"]
ProcurementPurchaseOrderCompletionStatus = Literal["NOT_RECEIVED", "PARTIAL", "RECEIVED"]


class ProcurementPurchaseOrderLineOut(BaseModel):
    id: int
    po_id: int
    line_no: int

    item_id: int
    item_sku_snapshot: str | None = None
    item_name_snapshot: str
    spec_text_snapshot: str | None = None

    purchase_uom_id_snapshot: int
    purchase_uom_name_snapshot: str
    purchase_ratio_to_base_snapshot: int

    qty_ordered_input: Decimal
    qty_ordered_base: int

    supply_price: Decimal | None = None
    discount_amount: Decimal | None = None
    line_amount: Decimal
    remark: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(extra="forbid")


class ProcurementPurchaseOrderOut(BaseModel):
    id: int
    po_no: str

    supplier_id: int
    supplier_code_snapshot: str
    supplier_name_snapshot: str

    target_warehouse_id: int
    target_warehouse_code_snapshot: str | None = None
    target_warehouse_name_snapshot: str | None = None

    purchaser: str
    purchase_time: datetime

    status: ProcurementPurchaseOrderStatus
    total_amount: Decimal
    remark: str | None = None

    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    canceled_at: datetime | None = None

    editable: bool = False
    edit_block_reason: str | None = None

    total_ordered_base: int = Field(default=0, ge=0)
    total_received_base: int = Field(default=0, ge=0)
    total_remaining_base: int = Field(default=0, ge=0)
    completion_status: ProcurementPurchaseOrderCompletionStatus = "NOT_RECEIVED"
    last_received_at: datetime | None = None

    lines: list[ProcurementPurchaseOrderLineOut] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ProcurementPurchaseOrderSourceOptionOut(BaseModel):
    po_id: int
    po_no: str

    target_warehouse_id: int
    target_warehouse_code_snapshot: str | None = None
    target_warehouse_name_snapshot: str | None = None

    supplier_id: int
    supplier_code_snapshot: str
    supplier_name_snapshot: str

    purchase_time: datetime

    order_status: str
    completion_status: ProcurementPurchaseOrderCompletionStatus
    last_received_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class ProcurementPurchaseOrderSourceOptionsOut(BaseModel):
    items: list[ProcurementPurchaseOrderSourceOptionOut] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
