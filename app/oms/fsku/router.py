# app/oms/fsku/router.py
from __future__ import annotations

from fastapi import APIRouter

from app.oms.fsku.router_platform_code_mappings import router as platform_code_mappings_router
from app.oms.fsku.routers.router import router as fsku_rules_router

router = APIRouter(tags=["oms-fsku"])
router.include_router(fsku_rules_router)
router.include_router(platform_code_mappings_router)

__all__ = ["router"]
