# app/shipping_assist/records/routes_options.py
#
# 分拆说明：
# - 本文件承载 WMS 发货记录页筛选项；
# - 当前 WMS 只保留 shipping_records 本地台帐与从 Logistics 同步事实；
# - 本接口替代前端对 /shipping-assist/pricing/providers 的依赖，避免 records 页面继续耦合旧运价/网点管理路由。
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session as get_session
from app.user.deps.auth import get_current_user


class ShippingRecordsProviderOption(BaseModel):
    id: int
    name: str
    shipping_provider_code: str


class ShippingRecordsWarehouseOption(BaseModel):
    id: int
    name: str


class ShippingRecordsOptionsOut(BaseModel):
    ok: bool = True
    providers: list[ShippingRecordsProviderOption]
    warehouses: list[ShippingRecordsWarehouseOption]


def register(router: APIRouter) -> None:
    @router.get(
        "/options",
        response_model=ShippingRecordsOptionsOut,
        summary="发货记录筛选项",
    )
    async def get_shipping_records_options(
        session: AsyncSession = Depends(get_session),
        current_user: Any = Depends(get_current_user),
    ) -> ShippingRecordsOptionsOut:
        del current_user

        provider_rows = (
            await session.execute(
                text(
                    """
                    SELECT
                      id,
                      name,
                      shipping_provider_code
                    FROM shipping_providers
                    WHERE active IS TRUE
                    ORDER BY priority ASC, name ASC, id ASC
                    """
                )
            )
        ).mappings().all()

        warehouse_rows = (
            await session.execute(
                text(
                    """
                    SELECT
                      id,
                      name
                    FROM warehouses
                    WHERE active IS TRUE
                    ORDER BY name ASC, id ASC
                    """
                )
            )
        ).mappings().all()

        return ShippingRecordsOptionsOut(
            ok=True,
            providers=[
                ShippingRecordsProviderOption(
                    id=int(row["id"]),
                    name=str(row["name"]),
                    shipping_provider_code=str(row["shipping_provider_code"]),
                )
                for row in provider_rows
            ],
            warehouses=[
                ShippingRecordsWarehouseOption(
                    id=int(row["id"]),
                    name=str(row["name"]),
                )
                for row in warehouse_rows
            ],
        )
