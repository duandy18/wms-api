from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import ItemReadQuery
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


async def _resolve_inventory_q_item_ids(
    session: AsyncSession,
    *,
    q: str | None,
) -> list[int] | None:
    """
    将库存页 q 搜索交给 PMS integration item read client。

    返回语义：
    - None：未传 q，不加商品过滤；
    - []：传了 q，但 PMS 没有匹配商品，应返回空库存结果；
    - [ids...]：按 item_id 集合过滤库存事实。
    """
    q_norm = _norm_text(q)
    if q_norm is None:
        return None

    items = await InProcessPmsReadClient(session).list_item_basics(
        query=ItemReadQuery(
            q=q_norm,
            limit=None,
        )
    )
    return [int(item.id) for item in items]


async def _load_inventory_display_maps(
    session: AsyncSession,
    *,
    item_ids: Iterable[int],
    include_main_barcode: bool,
):
    ids = _clean_item_ids(item_ids)
    if not ids:
        return {}, {}, {}

    pms_client = InProcessPmsReadClient(session)
    item_map = await pms_client.get_item_basics(item_ids=ids)

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

    main_barcode_map: dict[int, str | None] = {}
    if include_main_barcode:
        barcodes = await pms_client.list_barcodes(
            item_ids=ids,
            active=True,
        )
        for barcode in barcodes:
            item_id = int(barcode.item_id)
            if item_id in main_barcode_map:
                continue
            main_barcode_map[item_id] = str(barcode.barcode).strip() or None

    return item_map, base_uom_map, main_barcode_map


async def _enrich_inventory_rows(
    session: AsyncSession,
    *,
    rows: Iterable[dict[str, Any]],
    include_main_barcode: bool,
) -> list[dict[str, Any]]:
    out = [dict(row) for row in rows]
    item_ids = _clean_item_ids(row.get("item_id") for row in out)

    item_map, base_uom_map, main_barcode_map = await _load_inventory_display_maps(
        session,
        item_ids=item_ids,
        include_main_barcode=include_main_barcode,
    )

    for row in out:
        item_id = int(row["item_id"])
        item = item_map.get(item_id)
        base_uom = base_uom_map.get(item_id, {})

        row["item_name"] = str(getattr(item, "name", "") or f"ITEM-{item_id}")
        row["item_code"] = getattr(item, "sku", None) if item is not None else None
        row["spec"] = getattr(item, "spec", None) if item is not None else None
        row["brand"] = getattr(item, "brand", None) if item is not None else None
        row["category"] = getattr(item, "category", None) if item is not None else None
        row["base_item_uom_id"] = base_uom.get("base_item_uom_id")
        row["base_uom_name"] = base_uom.get("base_uom_name")

        if include_main_barcode:
            row["main_barcode"] = main_barcode_map.get(item_id)

    return out


def _build_inventory_where(
    *,
    q: str | None,
    q_item_ids: Iterable[int] | None,
    item_id: int | None,
    warehouse_id: int | None,
    lot_code: str | None,
    near_expiry: bool | None,
) -> tuple[str, dict[str, Any]]:
    cond = ["s.qty <> 0"]
    params: dict[str, Any] = {}

    q_norm = _norm_text(q)
    lot_norm = _norm_text(lot_code)

    if q_norm is not None:
        item_ids = _clean_item_ids(q_item_ids)
        if item_ids:
            cond.append("s.item_id = ANY(:q_item_ids)")
            params["q_item_ids"] = item_ids
        else:
            cond.append("FALSE")

    if item_id is not None:
        cond.append("s.item_id = :item_id")
        params["item_id"] = int(item_id)

    if warehouse_id is not None:
        cond.append("s.warehouse_id = :warehouse_id")
        params["warehouse_id"] = int(warehouse_id)

    if lot_norm is not None:
        cond.append("l.lot_code = :lot_code")
        params["lot_code"] = lot_norm

    if near_expiry is True:
        cond.append(
            "l.expiry_date IS NOT NULL "
            "AND l.expiry_date >= CURRENT_DATE "
            "AND l.expiry_date <= CURRENT_DATE + 30"
        )

    return " AND ".join(cond), params


async def query_inventory_rows(
    session: AsyncSession,
    *,
    q: str | None,
    item_id: int | None,
    warehouse_id: int | None,
    lot_code: str | None,
    near_expiry: bool | None,
    offset: int,
    limit: int,
) -> tuple[int, list[dict[str, Any]]]:
    q_item_ids = await _resolve_inventory_q_item_ids(session, q=q)
    where_sql, params = _build_inventory_where(
        q=q,
        q_item_ids=q_item_ids,
        item_id=item_id,
        warehouse_id=warehouse_id,
        lot_code=lot_code,
        near_expiry=near_expiry,
    )
    params["offset"] = int(offset)
    params["limit"] = int(limit)

    count_sql = text(
        f"""
        WITH base AS (
            SELECT
                s.item_id,
                s.warehouse_id,
                s.lot_id
            FROM stocks_lot AS s
            JOIN warehouses AS w
              ON w.id = s.warehouse_id
            LEFT JOIN lots AS l
              ON l.id = s.lot_id
            WHERE {where_sql}
        )
        SELECT COUNT(*)::int AS total
        FROM base
        """
    )
    total_row = (await session.execute(count_sql, params)).mappings().first()
    total = int((total_row or {}).get("total") or 0)

    list_sql = text(
        f"""
        SELECT
            s.item_id,
            s.warehouse_id,
            w.name AS warehouse_name,
            l.lot_code AS lot_code,
            l.production_date AS production_date,
            l.expiry_date AS expiry_date,
            s.qty
        FROM stocks_lot AS s
        JOIN warehouses AS w
          ON w.id = s.warehouse_id
        LEFT JOIN lots AS l
          ON l.id = s.lot_id
        WHERE {where_sql}
        ORDER BY s.item_id ASC, s.warehouse_id ASC, l.lot_code NULLS FIRST
        OFFSET :offset
        LIMIT :limit
        """
    )
    rows = (await session.execute(list_sql, params)).mappings().all()
    enriched = await _enrich_inventory_rows(
        session,
        rows=[dict(r) for r in rows],
        include_main_barcode=True,
    )
    return total, enriched


async def query_inventory_detail_rows(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int | None,
    lot_code: str | None,
) -> list[dict[str, Any]]:
    cond = [
        "s.item_id = :item_id",
        "s.qty <> 0",
    ]
    params: dict[str, Any] = {"item_id": int(item_id)}

    lot_norm = _norm_text(lot_code)
    if warehouse_id is not None:
        cond.append("s.warehouse_id = :warehouse_id")
        params["warehouse_id"] = int(warehouse_id)
    if lot_norm is not None:
        cond.append("l.lot_code = :lot_code")
        params["lot_code"] = lot_norm

    sql = text(
        f"""
        SELECT
            s.item_id,
            s.warehouse_id,
            w.name AS warehouse_name,
            l.lot_code AS lot_code,
            l.production_date AS production_date,
            l.expiry_date AS expiry_date,
            s.qty
        FROM stocks_lot AS s
        JOIN warehouses AS w
          ON w.id = s.warehouse_id
        LEFT JOIN lots AS l
          ON l.id = s.lot_id
        WHERE {" AND ".join(cond)}
        ORDER BY s.warehouse_id ASC, l.lot_code NULLS FIRST
        """
    )
    rows = (await session.execute(sql, params)).mappings().all()
    return await _enrich_inventory_rows(
        session,
        rows=[dict(r) for r in rows],
        include_main_barcode=False,
    )


__all__ = [
    "query_inventory_rows",
    "query_inventory_detail_rows",
]
