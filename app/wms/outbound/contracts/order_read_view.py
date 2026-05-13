# app/wms/outbound/contracts/order_read_view.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrderOutboundViewOrderOut(BaseModel):
    """
    WMS 订单出库页专用：订单头只读模型。

    Boundary:
    - 路由归属 WMS outbound。
    - 来源仍是 WMS 本地执行订单 facts：orders。
    - 不读取 OMS owner 表，不挂在 /oms/orders。
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    platform: str
    store_code: str
    ext_order_no: str

    status: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    buyer_name: Optional[str] = None
    buyer_phone: Optional[str] = None

    order_amount: Optional[Decimal] = None
    pay_amount: Optional[Decimal] = None


class OrderOutboundViewLineOut(BaseModel):
    """
    WMS 订单出库页专用：订单行只读模型。

    Boundary:
    - 核心来源是 WMS 本地 order_lines。
    - 商品展示字段通过 PMS read client / WMS PMS projection 获取。
    - 不直接 JOIN PMS owner 表。
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    order_id: int
    item_id: int
    req_qty: int

    item_sku: Optional[str] = None
    item_name: Optional[str] = None
    item_spec: Optional[str] = None

    base_uom_id: Optional[int] = None
    base_uom_name: Optional[str] = None


class OrderOutboundViewResponse(BaseModel):
    """
    WMS 订单出库页专用：只读聚合响应。
    """

    model_config = ConfigDict(extra="ignore")

    ok: bool = True
    order: OrderOutboundViewOrderOut
    lines: list[OrderOutboundViewLineOut] = Field(default_factory=list)
