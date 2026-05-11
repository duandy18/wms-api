from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _norm_text(value: str | None) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


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
    """
    Inventory options read PMS current-state from WMS local projection.

    Boundary:
    - projection is a WMS read index synced from pms-api read-v1 HTTP;
    - this read path must not call pms-api per request;
    - write validation still belongs to pms-api HTTP integration;
    - historical facts still belong to snapshot / ledger / lot rows.
    """
    q_norm = _norm_text(q)
    safe_limit = max(1, min(int(limit), 500))

    conditions = ["p.enabled IS TRUE"]
    params: dict[str, Any] = {"limit": safe_limit}

    if q_norm is not None:
        conditions.append(
            """
            (
                p.sku ILIKE :q
                OR p.name ILIKE :q
            )
            """
        )
        params["q"] = f"%{q_norm}%"

    sql = text(
        f"""
        SELECT
            p.item_id AS id,
            p.sku,
            p.name
        FROM wms_pms_item_projection AS p
        WHERE {" AND ".join(conditions)}
        ORDER BY p.item_id ASC
        LIMIT :limit
        """
    )
    rows = (await session.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]


__all__ = [
    "list_active_warehouses",
    "list_public_items",
]
