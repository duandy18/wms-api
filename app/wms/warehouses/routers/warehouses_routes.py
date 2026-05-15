# app/wms/warehouses/routers/warehouses_routes.py
from __future__ import annotations

from fastapi import APIRouter

from app.wms.warehouses.routers import warehouses_read_v1
from app.wms.warehouses.routers import warehouses_routes_read
from app.wms.warehouses.routers import warehouses_routes_service_cities
from app.wms.warehouses.routers import warehouses_routes_service_city_split_provinces
from app.wms.warehouses.routers import warehouses_routes_service_provinces
from app.wms.warehouses.routers import warehouses_routes_write


def register(router: APIRouter) -> None:
    # Cross-system read-v1 contract.
    # This is intentionally separate from legacy/admin /warehouses routes,
    # because system consumers such as procurement-api should not bind to
    # user/page-management endpoints.
    warehouses_read_v1.register(router)

    warehouses_routes_read.register(router)
    warehouses_routes_write.register(router)

    # 仓库服务范围（已归入 wms/warehouses 域）
    warehouses_routes_service_provinces.register(router)
    warehouses_routes_service_cities.register(router)
    warehouses_routes_service_city_split_provinces.register(router)
