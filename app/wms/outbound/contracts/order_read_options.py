# app/wms/outbound/contracts/order_read_options.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrderOutboundOptionOut(BaseModel):
    """
    WMS 订单出库页专用：订单选择器列表项。

    Boundary:
    - 路由归属 WMS outbound。
    - 来源仍是 WMS 本地执行订单 facts：orders / order_lines。
    - 不读取 OMS owner 表，不挂在 /oms/orders。
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    platform: str
    store_code: str
    ext_order_no: str

    status: Optional[str] = None
    buyer_name: Optional[str] = None
    created_at: datetime


class OrderOutboundOptionsOut(BaseModel):
    """
    WMS 订单出库页专用：订单选择器列表响应。
    """

    model_config = ConfigDict(extra="ignore")

    items: list[OrderOutboundOptionOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
