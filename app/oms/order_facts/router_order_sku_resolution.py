from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session
from app.oms.order_facts.contracts.order_sku_resolution import OrderSkuResolutionOut
from app.oms.order_facts.services.order_sku_resolution_service import (
    OrderSkuResolutionNotFound,
    OrderSkuResolutionValidationError,
    get_order_sku_resolution,
)


router = APIRouter(tags=["oms-order-sku-resolution"])


def _route_name(platform: str, suffix: str) -> str:
    return f"{platform}_{suffix}"


def _register_platform_routes(platform: str) -> None:
    @router.get(
        f"/{platform}/platform-order-mirrors/{{mirror_id}}/sku-resolution",
        response_model=OrderSkuResolutionOut,
        name=_route_name(platform, "get_platform_order_sku_resolution"),
    )
    async def get_platform_order_sku_resolution(
        mirror_id: int,
        session: AsyncSession = Depends(get_async_session),
    ) -> OrderSkuResolutionOut:
        try:
            data = await get_order_sku_resolution(
                session,
                platform=platform,
                mirror_id=int(mirror_id),
            )
            return OrderSkuResolutionOut(ok=True, data=data)
        except OrderSkuResolutionNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except OrderSkuResolutionValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


for _platform in ("pdd", "taobao", "jd"):
    _register_platform_routes(_platform)
