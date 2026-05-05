from __future__ import annotations

from fastapi import APIRouter

from app.oms.order_facts.router_code_mapping import (
    router as code_mapping_router,
)
from app.oms.order_facts.router_order_sku_resolution import (
    router as order_sku_resolution_router,
)
from app.oms.order_facts.router_platform_order_mirrors import (
    router as platform_order_mirrors_router,
)

router = APIRouter()
router.include_router(platform_order_mirrors_router)
router.include_router(code_mapping_router)
router.include_router(order_sku_resolution_router)

__all__ = ["router"]
