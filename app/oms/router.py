# app/oms/router.py
from __future__ import annotations

from fastapi import APIRouter

from app.oms.fulfillment_projection.routers.fulfillment_projection import (
    router as fulfillment_projection_router,
)

router = APIRouter(prefix="/oms", tags=["OMS"])
router.include_router(fulfillment_projection_router)

__all__ = ["router"]
