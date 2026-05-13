# app/pms/router.py
from __future__ import annotations

from fastapi import APIRouter
from app.pms.projections.routers.pms_projection import router as pms_projection_router

router = APIRouter(prefix="/pms", tags=["pms"])

router.include_router(pms_projection_router)

__all__ = ["router"]
