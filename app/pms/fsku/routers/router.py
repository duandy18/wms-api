# app/pms/fsku/routers/router.py
from __future__ import annotations

from fastapi import APIRouter

from .router_fskus import register as register_fskus

router = APIRouter(prefix="/pms", tags=["pms-fsku"])

register_fskus(router)

__all__ = ["router"]
