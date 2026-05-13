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


class OmsProjectionOrderImportCandidateOut(BaseModel):
    """
    订单出库页专用：OMS fulfillment projection 待接入候选订单。

    Boundary:
    - 来源是 WMS 本地 OMS fulfillment projection。
    - import_status 来自 WMS 导入审计表。
    - 给订单出库页展示/导入使用，不回写 projection。
    """

    model_config = ConfigDict(extra="ignore")

    ready_order_id: str
    platform: str
    store_code: str
    store_name: str | None = None
    platform_order_no: str
    platform_status: str | None = None

    receiver_name: str | None = None
    receiver_phone: str | None = None

    ready_status: str
    ready_at: str | None = None
    synced_at: str | None = None

    line_count: int = 0
    component_count: int = 0
    total_required_qty: str | None = None

    import_status: str
    imported_order_id: int | None = None
    imported_at: str | None = None
    can_import: bool = True


class OmsProjectionOrderImportCandidatesOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[OmsProjectionOrderImportCandidateOut]
    total: int
    limit: int
    offset: int
