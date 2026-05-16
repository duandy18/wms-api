from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session as get_session
from app.wms.system.service_auth.deps import require_wms_service_capability
from app.wms.warehouses.contracts.warehouse_read_v1 import (
    WmsReadWarehouseListOut,
    WmsReadWarehouseOut,
)

require_wms_read_warehouses = require_wms_service_capability("wms.read.warehouses")


def _row_to_read_warehouse(row: Mapping[str, Any]) -> WmsReadWarehouseOut:
    return WmsReadWarehouseOut(
        id=int(row["id"]),
        code=str(row["code"]) if row.get("code") is not None else None,
        name=str(row["name"]),
        active=bool(row["active"]),
    )


def register(router: APIRouter) -> None:
    @router.get(
        "/wms/read/v1/warehouses",
        response_model=WmsReadWarehouseListOut,
        tags=["wms-read-v1"],
    )
    async def list_wms_read_warehouses(
        active: bool | None = Query(
            True,
            description=(
                "是否过滤启用仓库；默认只返回 active=true，用于跨系统下拉。"
            ),
        ),
        limit: int = Query(200, ge=1, le=500),
        session: AsyncSession = Depends(get_session),
        _service_permission: None = Depends(require_wms_read_warehouses),
    ) -> WmsReadWarehouseListOut:
        """List WMS warehouses for cross-system read contracts.

        Boundary:
        - No consumer system should read WMS DB directly.
        - No management-only fields are exposed.
        - Consumers should store scalar id + code/name snapshot when needed.
        """

        where_clause = ""
        params: dict[str, Any] = {
            "limit": int(limit),
        }

        if active is not None:
            where_clause = "WHERE w.active = :active"
            params["active"] = bool(active)

        rows = (
            await session.execute(
                text(
                    f"""
                    SELECT
                      w.id,
                      w.code,
                      w.name,
                      w.active
                    FROM warehouses AS w
                    {where_clause}
                    ORDER BY w.id
                    LIMIT :limit
                    """
                ),
                params,
            )
        ).mappings().all()

        return WmsReadWarehouseListOut(
            items=[_row_to_read_warehouse(row) for row in rows],
        )

    @router.get(
        "/wms/read/v1/warehouses/{warehouse_id}",
        response_model=WmsReadWarehouseOut,
        tags=["wms-read-v1"],
    )
    async def get_wms_read_warehouse(
        warehouse_id: int = Path(..., ge=1),
        session: AsyncSession = Depends(get_session),
        _service_permission: None = Depends(require_wms_read_warehouses),
    ) -> WmsReadWarehouseOut:
        row = (
            await session.execute(
                text(
                    """
                    SELECT
                      w.id,
                      w.code,
                      w.name,
                      w.active
                    FROM warehouses AS w
                    WHERE w.id = :warehouse_id
                    """
                ),
                {"warehouse_id": int(warehouse_id)},
            )
        ).mappings().first()

        if row is None:
            raise HTTPException(status_code=404, detail="warehouse not found")

        return _row_to_read_warehouse(row)


__all__ = ["register", "require_wms_read_warehouses"]
