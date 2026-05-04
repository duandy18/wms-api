# app/pms/fsku/routers/router_fskus.py
from __future__ import annotations

from fastapi import APIRouter

from .router_fskus_routes_crud import register as register_crud
from .router_fskus_routes_lifecycle import register as register_lifecycle


def register(router: APIRouter) -> None:
    r = APIRouter(prefix="/fskus", tags=["pms-fsku"])

    register_crud(r)
    register_lifecycle(r)

    router.include_router(r)
