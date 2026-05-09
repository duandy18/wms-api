# app/oms/orders/repos/order_outbound_view_repo.py
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.pms.export.items.services.item_read_service import ItemReadService
from app.pms.export.uoms.contracts.uom import PmsExportUom
from app.pms.export.uoms.services.uom_read_service import PmsExportUomReadService


def _pick_base_uom(rows: list[PmsExportUom]) -> PmsExportUom | None:
    if not rows:
        return None

    for row in rows:
        if bool(row.is_base):
            return row

    return rows[0]


async def load_order_outbound_head(
    session: AsyncSession,
    *,
    order_id: int,
) -> Mapping[str, Any]:
    """
    订单出库页：读取订单头（来源真相 = orders）

    说明：
    - 这里只查真实 orders 表
    - 不掺 order_fulfillment / platform mirror / facts 聚合
    """
    row = (
        (
            await session.execute(
                text(
                    """
                    SELECT
                      id,
                      platform,
                      store_code,
                      ext_order_no,
                      status,
                      created_at,
                      updated_at,
                      buyer_name,
                      buyer_phone,
                      order_amount,
                      pay_amount
                    FROM orders
                    WHERE id = :oid
                    LIMIT 1
                    """
                ),
                {"oid": int(order_id)},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError(f"order not found: id={order_id}")
    return row


async def load_order_outbound_lines(
    session: AsyncSession,
    *,
    order_id: int,
) -> List[Dict[str, Any]]:
    """
    订单出库页：读取订单行（来源真相 = order_lines + PMS export display）

    说明：
    - 核心真相是 order_lines；
    - 商品展示字段 sku / name / spec 通过 PMS export ItemReadService 读取；
    - base_uom 展示通过 PMS export UOM read service 读取；
    - 不直接 JOIN PMS 内部 items / item_uoms 表。
    """
    line_rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT
                      id,
                      order_id,
                      item_id,
                      req_qty
                    FROM order_lines
                    WHERE order_id = :oid
                    ORDER BY id ASC
                    """
                ),
                {"oid": int(order_id)},
            )
        )
        .mappings()
        .all()
    )

    lines = [dict(r) for r in line_rows]
    item_ids = sorted(
        {
            int(r["item_id"])
            for r in lines
            if r.get("item_id") is not None and int(r["item_id"]) > 0
        }
    )

    item_map = await ItemReadService(session).aget_basics_by_item_ids(item_ids=item_ids)
    uom_rows = await PmsExportUomReadService(session).alist_uoms(item_ids=item_ids)

    uoms_by_item_id: Dict[int, List[PmsExportUom]] = {}
    for row in uom_rows:
        uoms_by_item_id.setdefault(int(row.item_id), []).append(row)

    out: List[Dict[str, Any]] = []
    for row in lines:
        item_id = int(row["item_id"])
        item = item_map.get(item_id)
        base_uom = _pick_base_uom(uoms_by_item_id.get(item_id, []))

        out.append(
            {
                **row,
                "item_sku": item.sku if item is not None else None,
                "item_name": item.name if item is not None else None,
                "item_spec": item.spec if item is not None else None,
                "base_uom_id": int(base_uom.id) if base_uom is not None else None,
                "base_uom_name": base_uom.uom_name if base_uom is not None else None,
            }
        )

    return out
