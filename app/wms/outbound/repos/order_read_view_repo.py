# app/wms/outbound/repos/order_read_view_repo.py
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import PmsExportUom
from app.integrations.pms.factory import create_pms_read_client


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
    WMS 订单出库页：读取订单头。

    Boundary:
    - 只查 WMS 本地执行订单 facts：orders。
    - 不读取 OMS owner 表。
    - 不挂载到 /oms/orders。
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
    WMS 订单出库页：读取订单行。

    Boundary:
    - 核心来源是 WMS 本地 order_lines。
    - 商品展示字段通过 PMS read client / WMS PMS projection 获取。
    - 不直接 JOIN PMS owner 表。
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

    pms_client = create_pms_read_client(session=session)
    item_map = await pms_client.get_item_basics(item_ids=item_ids)
    uom_rows = await pms_client.list_uoms(item_ids=item_ids)

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
