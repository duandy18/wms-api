# app/shipping_assist/records/router.py
#
# 分拆说明：
# - 本文件是 TMS / Records 的路由装配入口。
# - logistics ledger（shipping_records）相关接口已物理收口到 app/shipping_assist/records/；
# - 当前 WMS 只保留物流台账读取、成本分析与从 Logistics 同步事实入口。
from __future__ import annotations

from fastapi import APIRouter

from app.shipping_assist.records import routes_cost_analysis
from app.shipping_assist.records import routes_read
from app.shipping_assist.records import routes_sync

router = APIRouter(prefix="/shipping-assist/records", tags=["shipping-assist-records"])


def _register_all_routes() -> None:
    routes_read.register(router)
    routes_cost_analysis.register(router)
    routes_sync.register(router)


_register_all_routes()
