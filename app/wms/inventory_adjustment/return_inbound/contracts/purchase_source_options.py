from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


InboundReceiptPurchaseSourceCompletionStatus = Literal[
    "NOT_RECEIVED",
    "PARTIAL",
    "RECEIVED",
]


class _Base(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class InboundReceiptPurchaseSourceOptionOut(_Base):
    po_id: Annotated[int, Field(ge=1, description="采购单 ID")]
    po_no: Annotated[str, Field(min_length=1, max_length=64, description="采购单号")]

    target_warehouse_id: Annotated[int, Field(ge=1, description="目标仓库 ID")]
    target_warehouse_code_snapshot: Annotated[
        str | None,
        Field(default=None, max_length=64, description="目标仓库编码快照"),
    ]
    target_warehouse_name_snapshot: Annotated[
        str | None,
        Field(default=None, max_length=255, description="目标仓库名称快照"),
    ]

    supplier_id: Annotated[int, Field(ge=1, description="供应商 ID")]
    supplier_code_snapshot: Annotated[
        str,
        Field(min_length=1, max_length=64, description="供应商编码快照"),
    ]
    supplier_name_snapshot: Annotated[
        str,
        Field(min_length=1, max_length=255, description="供应商名称快照"),
    ]

    purchase_time: datetime
    order_status: Annotated[str, Field(min_length=1, max_length=32, description="采购单状态")]
    completion_status: InboundReceiptPurchaseSourceCompletionStatus
    last_received_at: datetime | None = Field(default=None, description="最近收货时间")


class InboundReceiptPurchaseSourceOptionsOut(_Base):
    items: list[InboundReceiptPurchaseSourceOptionOut] = Field(
        default_factory=list,
        description="可生成采购入库单的采购来源",
    )


__all__ = [
    "InboundReceiptPurchaseSourceCompletionStatus",
    "InboundReceiptPurchaseSourceOptionOut",
    "InboundReceiptPurchaseSourceOptionsOut",
]
