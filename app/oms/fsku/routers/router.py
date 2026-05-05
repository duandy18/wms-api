# app/oms/fsku/routers/router.py
from __future__ import annotations

from fastapi import APIRouter

from .router_fskus import register as register_fskus

router = APIRouter(prefix="", tags=["oms-fsku"])

register_fskus(router)

__all__ = ["router"]
