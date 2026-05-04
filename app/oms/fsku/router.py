# app/oms/fsku/router.py
from __future__ import annotations

from fastapi import APIRouter

from .router_merchant_code_bindings import router as merchant_code_bindings_router

router = APIRouter(tags=["oms-merchant-code-fsku-bindings"])
router.include_router(merchant_code_bindings_router)

__all__ = ["router"]
