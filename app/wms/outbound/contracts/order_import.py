# app/wms/outbound/contracts/order_import.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OmsProjectionOrderImportIn(BaseModel):
    """
    从 WMS 本地 OMS fulfillment projection 手动导入 WMS 执行订单。

    Boundary:
    - 输入是 ready_order_id。
    - 来源只允许 wms_oms_fulfillment_* projection。
    - 输出写入 WMS 执行 facts：orders / order_address / order_items / order_lines / order_fulfillment。
    - 不写回 projection 表。
    """

    model_config = ConfigDict(extra="forbid")

    ready_order_ids: list[str] = Field(min_length=1, max_length=200)
    dry_run: bool = False


class OmsProjectionOrderImportRowOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ready_order_id: str
    status: str
    order_id: int | None = None
    platform: str | None = None
    store_code: str | None = None
    platform_order_no: str | None = None
    order_line_count: int = 0
    component_count: int = 0
    message: str | None = None


class OmsProjectionOrderImportOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dry_run: bool
    requested: int
    imported: int
    already_imported: int
    failed: int
    results: list[OmsProjectionOrderImportRowOut]
