# app/oms/services/platform_order_resolve_loaders.py
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.pms.public.items.services.item_read_service import ItemReadService


async def load_fsku_components(
    session: AsyncSession,
    *,
    fsku_id: int,
) -> List[Dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                """
                SELECT
                  c.resolved_item_id AS item_id,
                  c.qty_per_fsku AS qty,
                  'primary' AS role,
                  c.component_sku_code,
                  c.alloc_unit_price,
                  c.resolved_item_sku_code_id,
                  c.resolved_item_uom_id,
                  c.sku_code_snapshot,
                  c.item_name_snapshot,
                  c.uom_snapshot
                FROM oms_fsku_components c
                JOIN oms_fskus f ON f.id = c.fsku_id
                WHERE c.fsku_id = :fid
                  AND f.status = 'published'
                ORDER BY c.sort_order ASC, c.id ASC
                """
            ),
            {"fid": int(fsku_id)},
        )
    ).mappings().all()

    return [dict(r) for r in rows]


async def load_items_brief(
    session: AsyncSession,
    *,
    item_ids: List[int],
) -> Dict[int, Dict[str, Any]]:
    if not item_ids:
        return {}

    svc = ItemReadService(session)
    rows = await svc.aget_basics_by_item_ids(item_ids=[int(x) for x in item_ids])

    out: Dict[int, Dict[str, Any]] = {}
    for item_id, item in rows.items():
        out[int(item_id)] = {
            "sku": item.sku,
            "name": item.name,
        }
    return out
