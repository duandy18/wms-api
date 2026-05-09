from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _norm_text(v: str | None) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _build_inventory_where(
    *,
    q: str | None,
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
        cond.append("(p.name ILIKE :q OR p.sku ILIKE :q)")
        params["q"] = f"%{q_norm}%"

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
    where_sql, params = _build_inventory_where(
        q=q,
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
            LEFT JOIN wms_pms_item_projection AS p
              ON p.item_id = s.item_id
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
        WITH primary_barcodes AS (
            SELECT DISTINCT ON (pb.item_id)
                pb.item_id,
                pb.barcode
            FROM wms_pms_item_barcode_projection AS pb
            WHERE pb.active IS TRUE
            ORDER BY pb.item_id ASC, pb.is_primary DESC, pb.barcode_id ASC
        )
        SELECT
            s.item_id,
            COALESCE(p.name, '') AS item_name,
            p.sku AS item_code,
            p.spec AS spec,
            NULL::text AS brand,
            NULL::text AS category,
            s.warehouse_id,
            w.name AS warehouse_name,
            l.lot_code AS lot_code,
            l.production_date AS production_date,
            l.expiry_date AS expiry_date,
            s.qty,
            bu.item_uom_id AS base_item_uom_id,
            COALESCE(NULLIF(bu.display_name, ''), bu.uom) AS base_uom_name,
            pb.barcode AS main_barcode
        FROM stocks_lot AS s
        LEFT JOIN wms_pms_item_projection AS p
          ON p.item_id = s.item_id
        JOIN warehouses AS w
          ON w.id = s.warehouse_id
        LEFT JOIN lots AS l
          ON l.id = s.lot_id
        LEFT JOIN wms_pms_item_uom_projection AS bu
          ON bu.item_id = s.item_id
         AND bu.is_base IS TRUE
        LEFT JOIN primary_barcodes AS pb
          ON pb.item_id = s.item_id
        WHERE {where_sql}
        ORDER BY COALESCE(p.name, '') ASC, s.item_id ASC, s.warehouse_id ASC, l.lot_code NULLS FIRST
        OFFSET :offset
        LIMIT :limit
        """
    )
    rows = (await session.execute(list_sql, params)).mappings().all()
    return total, [dict(r) for r in rows]


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
            COALESCE(p.name, '') AS item_name,
            bu.item_uom_id AS base_item_uom_id,
            COALESCE(NULLIF(bu.display_name, ''), bu.uom) AS base_uom_name,
            s.warehouse_id,
            w.name AS warehouse_name,
            l.lot_code AS lot_code,
            l.production_date AS production_date,
            l.expiry_date AS expiry_date,
            s.qty
        FROM stocks_lot AS s
        LEFT JOIN wms_pms_item_projection AS p
          ON p.item_id = s.item_id
        JOIN warehouses AS w
          ON w.id = s.warehouse_id
        LEFT JOIN lots AS l
          ON l.id = s.lot_id
        LEFT JOIN wms_pms_item_uom_projection AS bu
          ON bu.item_id = s.item_id
         AND bu.is_base IS TRUE
        WHERE {" AND ".join(cond)}
        ORDER BY s.warehouse_id ASC, l.lot_code NULLS FIRST
        """
    )
    rows = (await session.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]


__all__ = [
    "query_inventory_rows",
    "query_inventory_detail_rows",
]
