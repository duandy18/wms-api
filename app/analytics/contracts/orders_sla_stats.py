# app/analytics/contracts/orders_sla_stats.py
from __future__ import annotations

from pydantic import BaseModel, Field


class OrdersSlaStatsModel(BaseModel):
    """
    WMS 出库 SLA 统计：

    - total_orders    : 时间窗口内 WMS 出库完成的订单数
    - avg_ship_hours  : 平均 WMS 出库耗时（小时）
    - p95_ship_hours  : 95 分位 WMS 出库耗时（小时）
    - on_time_orders  : 在 SLA 小时内完成 WMS 出库的订单数
    - on_time_rate    : 准时率 = on_time_orders / total_orders

    字段名暂保持 avg_ship_hours / p95_ship_hours，以维持当前统计 API 的输出合同；
    其计算口径已切换为 order_fulfillment.outbound_completed_at。
    """

    total_orders: int = Field(..., description="时间窗口内 WMS 出库完成的订单数量")
    avg_ship_hours: float | None = Field(
        None,
        description="平均 WMS 出库耗时（小时），无订单时为 null",
    )
    p95_ship_hours: float | None = Field(
        None,
        description="95 分位 WMS 出库耗时（小时），无订单时为 null",
    )
    on_time_orders: int = Field(..., description="在 SLA 小时内完成 WMS 出库的订单数")
    on_time_rate: float = Field(
        ...,
        description="准时率 = on_time_orders / total_orders（无订单时为 0.0）",
    )
