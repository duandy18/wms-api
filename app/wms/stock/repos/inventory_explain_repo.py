from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.inprocess_client import InProcessPmsReadClient


def _norm_text(v: str | None) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _clean_item_ids(values: Iterable[int] | None) -> list[int]:
    if values is None:
        return []
    out: set[int] = set()
    for value in values:
        if value is None:
            continue
        item_id = int(value)
        if item_id > 0:
            out.add(item_id)
    return sorted(out)


async def _load_item_display_maps(
    session: AsyncSession,
    *,
    item_ids: Iterable[int],
) -> tuple[dict[int, str], dict[int, dict[str, object | None]]]:
    """
    通过 PMS integration client 批量读取库存解释页展示所需商品信息。

    注意：
    - 这里只补当前查询展示信息；
    - WMS inventory explain 不直接读取 PMS owner items / item_uoms；
    - 历史事实解释仍以 ledger / lot / snapshot 等 WMS 事实为准。
    """
    ids = _clean_item_ids(item_ids)
    if not ids:
        return {}, {}

    pms_client = InProcessPmsReadClient(session)
    basics = await pms_client.get_item_basics(item_ids=ids)
    item_name_map = {
        int(item_id): str(item.name).strip()
        for item_id, item in basics.items()
        if str(item.name or "").strip()
    }

    base_uom_map: dict[int, dict[str, object | None]] = {
        item_id: {"base_item_uom_id": None, "base_uom_name": None}
        for item_id in ids
    }
    uoms = await pms_client.list_uoms(item_ids=ids)
    for uom in uoms:
        if not bool(getattr(uom, "is_base", False)):
            continue

        item_id = int(uom.item_id)
        if item_id not in base_uom_map:
            continue
        if base_uom_map[item_id]["base_item_uom_id"] is not None:
            continue

        base_uom_map[item_id] = {
            "base_item_uom_id": int(uom.id),
            "base_uom_name": str(uom.uom_name or uom.display_name or uom.uom or "").strip() or None,
        }

    return item_name_map, base_uom_map


async def _enrich_item_display(
    session: AsyncSession,
    *,
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    out = [dict(row) for row in rows]
    item_ids = _clean_item_ids(row.get("item_id") for row in out)
    item_name_map, base_uom_map = await _load_item_display_maps(
        session,
        item_ids=item_ids,
    )

    for row in out:
        item_id = int(row["item_id"])
        base_uom = base_uom_map.get(item_id, {})

        row["item_name"] = item_name_map.get(item_id) or f"ITEM-{item_id}"
        row["base_item_uom_id"] = base_uom.get("base_item_uom_id")
        row["base_uom_name"] = base_uom.get("base_uom_name")

    return out


async def resolve_inventory_explain_anchor(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
    lot_id: int | None,
    lot_code: str | None,
) -> dict[str, Any] | None:
    cond = [
        "s.item_id = :item_id",
        "s.warehouse_id = :warehouse_id",
        "s.qty <> 0",
    ]
    params: dict[str, Any] = {
        "item_id": int(item_id),
        "warehouse_id": int(warehouse_id),
    }

    if lot_id is not None:
        cond.append("s.lot_id = :lot_id")
        params["lot_id"] = int(lot_id)
    else:
        norm_lot_code = _norm_text(lot_code)
        if norm_lot_code is None:
            cond.append("l.lot_code IS NULL")
        else:
            cond.append("l.lot_code = :lot_code")
            params["lot_code"] = norm_lot_code

    sql = text(
        f"""
        SELECT
            s.item_id,
            s.warehouse_id,
            w.name AS warehouse_name,
            s.lot_id,
            l.lot_code,
            s.qty AS current_qty
        FROM stocks_lot AS s
        JOIN warehouses AS w
          ON w.id = s.warehouse_id
        LEFT JOIN lots AS l
          ON l.id = s.lot_id
        WHERE {" AND ".join(cond)}
        ORDER BY s.id ASC
        """
    )
    rows = (await session.execute(sql, params)).mappings().all()
    if not rows:
        return None
    if len(rows) > 1:
        raise RuntimeError("ambiguous_inventory_explain_anchor")

    enriched = await _enrich_item_display(session, rows=[dict(rows[0])])
    return enriched[0]


async def count_inventory_explain_ledger_rows(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
    lot_id: int,
) -> int:
    sql = text(
        """
        SELECT COUNT(*)::int AS total
        FROM stock_ledger
        WHERE item_id = :item_id
          AND warehouse_id = :warehouse_id
          AND lot_id = :lot_id
        """
    )
    row = (await session.execute(
        sql,
        {
            "item_id": int(item_id),
            "warehouse_id": int(warehouse_id),
            "lot_id": int(lot_id),
        },
    )).mappings().first()
    return int((row or {}).get("total") or 0)


async def query_inventory_explain_ledger_rows(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
    lot_id: int,
    limit: int,
) -> list[dict[str, Any]]:
    sql = text(
        """
        WITH picked AS (
            SELECT
                sl.id,
                sl.occurred_at,
                sl.created_at,
                sl.reason,
                sl.reason_canon,
                sl.sub_reason,
                sl.ref,
                sl.ref_line,
                sl.delta,
                sl.after_qty,
                sl.trace_id,
                sl.item_id,
                sl.warehouse_id,
                sl.lot_id,
                l.lot_code
            FROM stock_ledger AS sl
            LEFT JOIN lots AS l
              ON l.id = sl.lot_id
            WHERE sl.item_id = :item_id
              AND sl.warehouse_id = :warehouse_id
              AND sl.lot_id = :lot_id
            ORDER BY sl.occurred_at DESC, sl.id DESC
            LIMIT :limit
        )
        SELECT *
        FROM picked
        ORDER BY occurred_at ASC, id ASC
        """
    )
    rows = (await session.execute(
        sql,
        {
            "item_id": int(item_id),
            "warehouse_id": int(warehouse_id),
            "lot_id": int(lot_id),
            "limit": int(limit),
        },
    )).mappings().all()
    return await _enrich_item_display(session, rows=[dict(r) for r in rows])


async def query_inventory_explain_latest_after_qty(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
    lot_id: int,
) -> int | None:
    sql = text(
        """
        SELECT after_qty
        FROM stock_ledger
        WHERE item_id = :item_id
          AND warehouse_id = :warehouse_id
          AND lot_id = :lot_id
        ORDER BY occurred_at DESC, id DESC
        LIMIT 1
        """
    )
    row = (await session.execute(
        sql,
        {
            "item_id": int(item_id),
            "warehouse_id": int(warehouse_id),
            "lot_id": int(lot_id),
        },
    )).first()
    if row is None:
        return None
    return int(row[0])
