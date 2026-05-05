# app/oms/routers/platform_orders_manual_decisions.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session as get_session
from app.oms.contracts.platform_orders_manual_decisions import ManualDecisionOrdersOut
from app.oms.services.platform_order_resolve_service import norm_platform

router = APIRouter(tags=["platform-orders"])


def _as_int(v: Any) -> Optional[int]:
    try:
        n = int(v)
        return n
    except Exception:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _load_store_code_by_store_id(session: AsyncSession, *, platform: str, store_id: int) -> Optional[str]:
    plat = norm_platform(platform)
    row = (
        (
            await session.execute(
                text(
                    """
                    SELECT store_code
                      FROM stores
                     WHERE id = :sid
                       AND platform = :p
                     LIMIT 1
                    """
                ),
                {"sid": int(store_id), "p": plat},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    v = row.get("store_code")
    s = str(v).strip() if v is not None else ""
    return s or None


@router.get(
    "/platform-orders/manual-decisions/latest",
    response_model=ManualDecisionOrdersOut,
    summary="读取最近的人工救火批次（platform_order_manual_decisions），用于治理证据回流（不写绑定）",
)
async def list_latest_manual_decisions(
    platform: str = Query(..., description="平台（如 DEMO/PDD/TB），大小写不敏感"),
    store_id: int = Query(..., ge=1, description="内部店铺 store_id（stores.id）"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> ManualDecisionOrdersOut:
    plat = norm_platform(platform)
    sid = int(store_id)

    batch_rows = (
        await session.execute(
            text(
                """
                SELECT batch_id, MAX(created_at) AS latest_created_at
                  FROM platform_order_manual_decisions
                 WHERE platform = :platform
                   AND store_id = :store_id
                 GROUP BY batch_id
                 ORDER BY latest_created_at DESC
                 LIMIT :limit OFFSET :offset
                """
            ),
            {"platform": plat, "store_id": sid, "limit": int(limit), "offset": int(offset)},
        )
    ).mappings().all()

    total_row = (
        await session.execute(
            text(
                """
                SELECT COUNT(DISTINCT batch_id) AS n
                  FROM platform_order_manual_decisions
                 WHERE platform = :platform
                   AND store_id = :store_id
                """
            ),
            {"platform": plat, "store_id": sid},
        )
    ).mappings().first()
    total = int(total_row.get("n") or 0) if total_row else 0

    batch_ids: List[str] = [str(r.get("batch_id")) for r in batch_rows if r.get("batch_id") is not None]
    if not batch_ids:
        return ManualDecisionOrdersOut(items=[], total=total, limit=int(limit), offset=int(offset))

    fact_rows = (
        await session.execute(
            text(
                """
                SELECT
                    batch_id,
                    platform, store_id, ext_order_no, order_id,
                    line_key, line_no,
                    filled_code,
                    fact_qty,
                    item_id, qty, note,
                    manual_reason, risk_flags,
                    created_at
                  FROM platform_order_manual_decisions
                 WHERE batch_id = ANY(:batch_ids)
                 ORDER BY created_at DESC, id ASC
                """
            ),
            {"batch_ids": batch_ids},
        )
    ).mappings().all()

    order_ids: List[int] = []
    for r in fact_rows:
        oid = _as_int(r.get("order_id"))
        if oid is not None:
            order_ids.append(oid)
    order_ids = sorted(set(order_ids))

    order_store_map: Dict[int, str] = {}
    if order_ids:
        o_rows = (
            await session.execute(
                text(
                    """
                    SELECT id, store_code
                      FROM orders
                     WHERE id = ANY(:order_ids)
                    """
                ),
                {"order_ids": order_ids},
            )
        ).mappings().all()
        for o in o_rows:
            oid = _as_int(o.get("id"))
            if oid is None:
                continue
            order_store_map[oid] = str(o.get("store_code") or "")

    batch_latest_map: Dict[str, Any] = {}
    for br in batch_rows:
        bid = str(br.get("batch_id"))
        batch_latest_map[bid] = br.get("latest_created_at")

    grouped: Dict[str, Dict[str, Any]] = {}
    for r in fact_rows:
        bid = str(r.get("batch_id"))
        if bid not in grouped:
            oid = _as_int(r.get("order_id"))
            store_code = order_store_map.get(oid, "") if oid is not None else ""
            ext = str(r.get("ext_order_no") or "")
            p = str(r.get("platform") or plat)

            grouped[bid] = {
                "batch_id": bid,
                "created_at": batch_latest_map.get(bid) or r.get("created_at"),
                "order_id": int(oid) if oid is not None else 0,
                "platform": p,
                "store_code": store_code,
                "ext_order_no": ext,
                "ref": f"ORD:{p}:{store_code}:{ext}",
                "store_id": int(r.get("store_id") or sid),
                "manual_reason": r.get("manual_reason") if isinstance(r.get("manual_reason"), str) else None,
                "risk_flags": [],
                "manual_decisions": [],
            }

        rf = r.get("risk_flags")
        if isinstance(rf, list):
            for x in rf:
                if isinstance(x, str) and x not in grouped[bid]["risk_flags"]:
                    grouped[bid]["risk_flags"].append(x)

        grouped[bid]["manual_decisions"].append(
            {
                "line_key": r.get("line_key"),
                "line_no": r.get("line_no"),
                "filled_code": r.get("filled_code"),
                "fact_qty": r.get("fact_qty"),
                "item_id": r.get("item_id"),
                "qty": r.get("qty"),
                "note": r.get("note"),
            }
        )

    items: List[Dict[str, Any]] = []
    for br in batch_rows:
        bid = str(br.get("batch_id"))
        if bid in grouped:
            items.append(grouped[bid])

    return ManualDecisionOrdersOut(items=items, total=total, limit=int(limit), offset=int(offset))
