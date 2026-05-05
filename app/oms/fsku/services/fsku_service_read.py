# app/oms/fsku/services/fsku_service_read.py
from __future__ import annotations

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.oms.fsku.contracts.fsku import FskuDetailOut, FskuListItem, FskuListOut
from app.oms.fsku.models.fsku import Fsku, FskuComponent
from app.oms.fsku.services.fsku_service_mapper import to_detail


def get_detail(db: Session, fsku_id: int) -> FskuDetailOut | None:
    obj = db.get(Fsku, int(fsku_id))
    if obj is None:
        return None

    comps = (
        db.scalars(
            select(FskuComponent)
            .where(FskuComponent.fsku_id == int(fsku_id))
            .order_by(FskuComponent.sort_order.asc(), FskuComponent.id.asc())
        )
        .all()
    )
    return to_detail(obj, list(comps))


def list_fskus(
    db: Session,
    *,
    query: str | None,
    status: str | None,
    store_id: int | None,
    limit: int,
    offset: int,
) -> FskuListOut:
    _ = store_id

    where_sql = " WHERE 1=1 "
    params: dict[str, Any] = {"limit": int(limit), "offset": int(offset)}

    if query:
        params["q"] = f"%{query.strip()}%"
        where_sql += " AND (f.name ILIKE :q OR f.code ILIKE :q OR f.normalized_expr ILIKE :q) "

    if status:
        params["status"] = status
        where_sql += " AND f.status = :status "

    total = int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                  FROM oms_fskus f
                """
                + where_sql
            ),
            params,
        ).scalar()
        or 0
    )

    rows = (
        db.execute(
            text(
                """
                SELECT
                  f.id,
                  f.code,
                  f.name,
                  f.shape,
                  f.status,
                  f.fsku_expr,
                  f.normalized_expr,
                  f.expr_type,
                  f.component_count,
                  f.updated_at,
                  f.published_at,
                  f.retired_at,
                  COALESCE(
                    STRING_AGG(
                      (c.component_sku_code || '×' || (c.qty_per_fsku::int)::text),
                      ' + '
                      ORDER BY c.sort_order ASC
                    ),
                    ''
                  ) AS components_summary,
                  COALESCE(
                    STRING_AGG(
                      (c.item_name_snapshot || '×' || (c.qty_per_fsku::int)::text),
                      ' + '
                      ORDER BY c.sort_order ASC
                    ),
                    ''
                  ) AS components_summary_name
                FROM oms_fskus f
                LEFT JOIN oms_fsku_components c ON c.fsku_id = f.id
                """
                + where_sql
                + """
                GROUP BY f.id
                ORDER BY f.updated_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        .mappings()
        .all()
    )

    items = [
        FskuListItem(
            id=int(r["id"]),
            code=str(r["code"]),
            name=str(r["name"]),
            shape=str(r["shape"]),
            status=str(r["status"]),
            fsku_expr=str(r["fsku_expr"]),
            normalized_expr=str(r["normalized_expr"]),
            expr_type=str(r["expr_type"]),
            component_count=int(r["component_count"]),
            updated_at=r["updated_at"],
            published_at=r["published_at"],
            retired_at=r["retired_at"],
            components_summary=str(r["components_summary"] or ""),
            components_summary_name=str(r["components_summary_name"] or ""),
        )
        for r in rows
    ]

    return FskuListOut(items=items, total=total, limit=int(limit), offset=int(offset))
