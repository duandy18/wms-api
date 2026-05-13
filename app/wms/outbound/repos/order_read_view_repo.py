# app/wms/outbound/repos/order_read_view_repo.py
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import PmsExportUom
from app.integrations.pms.factory import create_pms_read_client


def _clean_text(value: object | None) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


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


async def _load_pms_display_maps(
    session: AsyncSession,
    *,
    item_ids: list[int],
) -> tuple[dict[int, Any], dict[int, list[PmsExportUom]]]:
    """
    Try PMS read client for display enrichment.

    PMS display enrichment must not be required for WMS outbound execution:
    - imported OMS projection orders have local snapshots in
      wms_oms_fulfillment_component_imports;
    - dev/test environments may intentionally not configure PMS_API_BASE_URL;
    - missing PMS display data should degrade to snapshots/nulls, not 500.
    """

    if not item_ids:
        return {}, {}

    try:
        pms_client = create_pms_read_client(session=session)
        item_map = await pms_client.get_item_basics(item_ids=item_ids)
        uom_rows = await pms_client.list_uoms(item_ids=item_ids)
    except Exception:
        return {}, {}

    uoms_by_item_id: dict[int, list[PmsExportUom]] = {}
    for row in uom_rows:
        uoms_by_item_id.setdefault(int(row.item_id), []).append(row)

    return item_map, uoms_by_item_id


async def load_order_outbound_lines(
    session: AsyncSession,
    *,
    order_id: int,
) -> List[Dict[str, Any]]:
    """
    WMS 订单出库页：读取订单行。

    Boundary:
    - 核心来源是 WMS 本地 order_lines。
    - 商品展示字段优先通过 PMS read client / WMS PMS projection 获取。
    - 对 OMS projection 导入订单，允许使用导入审计快照兜底。
    - 不直接 JOIN PMS owner 表。
    """

    line_rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT
                      ol.id,
                      ol.order_id,
                      ol.item_id,
                      ol.req_qty,
                      ci.sku_code_snapshot AS import_sku_code_snapshot,
                      ci.item_name_snapshot AS import_item_name_snapshot,
                      ci.resolved_item_uom_id AS import_uom_id,
                      ci.uom_snapshot AS import_uom_snapshot
                    FROM order_lines AS ol
                    LEFT JOIN wms_oms_fulfillment_component_imports AS ci
                      ON ci.order_line_id = ol.id
                    WHERE ol.order_id = :oid
                    ORDER BY ol.id ASC
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

    item_map, uoms_by_item_id = await _load_pms_display_maps(
        session,
        item_ids=item_ids,
    )

    out: List[Dict[str, Any]] = []
    for row in lines:
        item_id = int(row["item_id"])
        item = item_map.get(item_id)
        base_uom = _pick_base_uom(uoms_by_item_id.get(item_id, []))

        import_uom_id = row.get("import_uom_id")
        import_uom_id_int = int(import_uom_id) if import_uom_id is not None else None

        out.append(
            {
                "id": row["id"],
                "order_id": row["order_id"],
                "item_id": row["item_id"],
                "req_qty": row["req_qty"],
                "item_sku": (
                    item.sku
                    if item is not None
                    else _clean_text(row.get("import_sku_code_snapshot"))
                ),
                "item_name": (
                    item.name
                    if item is not None
                    else _clean_text(row.get("import_item_name_snapshot"))
                ),
                "item_spec": item.spec if item is not None else None,
                "base_uom_id": (
                    int(base_uom.id) if base_uom is not None else import_uom_id_int
                ),
                "base_uom_name": (
                    base_uom.uom_name
                    if base_uom is not None
                    else _clean_text(row.get("import_uom_snapshot"))
                ),
            }
        )

    return out
