from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import ItemReadQuery
from app.integrations.pms.factory import create_pms_read_client


async def list_active_warehouses(
    session: AsyncSession,
    *,
    active_only: bool,
) -> list[dict[str, Any]]:
    where_sql = "WHERE w.active = TRUE" if active_only else ""
    sql = text(
        f"""
        SELECT
            w.id,
            w.name,
            w.code,
            w.active
        FROM warehouses AS w
        {where_sql}
        ORDER BY w.id ASC
        """
    )
    rows = (await session.execute(sql)).mappings().all()
    return [dict(r) for r in rows]


async def list_public_items(
    session: AsyncSession,
    *,
    q: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    items = await create_pms_read_client(session=session).list_item_basics(
        query=ItemReadQuery(
            enabled=True,
            q=q,
            limit=int(limit),
        )
    )
    return [
        {
            "id": int(item.id),
            "sku": str(item.sku),
            "name": str(item.name),
        }
        for item in items
    ]


__all__ = [
    "list_active_warehouses",
    "list_public_items",
]
