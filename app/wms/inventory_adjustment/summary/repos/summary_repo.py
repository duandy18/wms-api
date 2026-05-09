from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.pms.export.items.services.item_read_service import ItemReadService
from app.pms.export.uoms.services.uom_read_service import PmsExportUomReadService


SUMMARY_CTE = """
WITH ledger_stats AS (
  SELECT
    event_id,
    COUNT(*)::int AS ledger_row_count,
    COALESCE(SUM(delta), 0)::int AS delta_total,
    COALESCE(SUM(ABS(delta)), 0)::int AS abs_delta_total,
    MIN(reason)::text AS ledger_reason,
    MIN(reason_canon)::text AS ledger_reason_canon,
    CASE
      WHEN COUNT(DISTINCT sub_reason) = 1 THEN MIN(sub_reason)::text
      WHEN COUNT(DISTINCT sub_reason) > 1 THEN 'MIXED'
      ELSE NULL::text
    END AS ledger_sub_reason,
    COUNT(*) FILTER (WHERE sub_reason = 'COUNT_ADJUST')::int AS count_adjust_count,
    COUNT(*) FILTER (WHERE sub_reason = 'COUNT_CONFIRM')::int AS count_confirm_count
  FROM stock_ledger
  WHERE event_id IS NOT NULL
  GROUP BY event_id
),
count_stats AS (
  SELECT
    doc_id,
    COUNT(*)::int AS line_count,
    COALESCE(SUM(COALESCE(diff_qty_base, 0)), 0)::int AS doc_diff_total
  FROM count_doc_lines
  GROUP BY doc_id
),
count_rows AS (
  SELECT
    'COUNT'::text AS adjustment_type,
    d.id::int AS object_id,
    d.count_no::text AS object_no,
    d.warehouse_id::int AS warehouse_id,
    d.status::text AS status,
    COALESCE(e.source_type, 'MANUAL_COUNT')::text AS source_type,
    d.count_no::text AS source_ref,
    e.event_type::text AS event_type,
    e.event_kind::text AS event_kind,
    e.target_event_id::int AS target_event_id,
    COALESCE(e.occurred_at, d.snapshot_at) AS occurred_at,
    COALESCE(e.committed_at, d.posted_at) AS committed_at,
    d.created_at AS created_at,
    COALESCE(cs.line_count, 0)::int AS line_count,
    COALESCE(ls.delta_total, cs.doc_diff_total, 0)::int AS qty_total,
    COALESCE(ls.ledger_row_count, 0)::int AS ledger_row_count,
    ls.ledger_reason::text AS ledger_reason,
    ls.ledger_reason_canon::text AS ledger_reason_canon,
    ls.ledger_sub_reason::text AS ledger_sub_reason,
    COALESCE(ls.delta_total, 0)::int AS delta_total,
    COALESCE(ls.abs_delta_total, ABS(COALESCE(cs.doc_diff_total, 0)))::int AS abs_delta_total,
    CASE
      WHEN d.status <> 'POSTED' THEN 'PENDING'
      WHEN COALESCE(ls.delta_total, 0) > 0 THEN 'INCREASE'
      WHEN COALESCE(ls.delta_total, 0) < 0 THEN 'DECREASE'
      ELSE 'CONFIRM'
    END::text AS direction,
    CASE
      WHEN d.status <> 'POSTED' THEN '盘点单'
      WHEN COALESCE(ls.count_adjust_count, 0) > 0 THEN '盘点调整'
      ELSE '盘点确认'
    END::text AS action_title,
    CASE
      WHEN d.status = 'VOIDED' THEN '盘点单，已作废，' || COALESCE(cs.line_count, 0)::text || ' 行'
      WHEN d.status = 'FROZEN' THEN '盘点单，已冻结，' || COALESCE(cs.line_count, 0)::text || ' 行'
      WHEN d.status = 'COUNTED' THEN '盘点单，已盘点，' || COALESCE(cs.line_count, 0)::text || ' 行'
      WHEN d.status <> 'POSTED' THEN '盘点单，未过账，' || COALESCE(cs.line_count, 0)::text || ' 行'
      WHEN COALESCE(ls.count_adjust_count, 0) > 0 AND COALESCE(ls.delta_total, 0) > 0
        THEN '盘点调整，库存增加 ' || COALESCE(ls.abs_delta_total, 0)::text
      WHEN COALESCE(ls.count_adjust_count, 0) > 0 AND COALESCE(ls.delta_total, 0) < 0
        THEN '盘点调整，库存减少 ' || COALESCE(ls.abs_delta_total, 0)::text
      WHEN COALESCE(ls.count_adjust_count, 0) > 0
        THEN '盘点调整，净变动 0'
      ELSE '盘点确认，无差异'
    END::text AS action_summary,
    d.remark::text AS remark,
    '/inventory-adjustment/count'::text AS detail_route,
    COALESCE(e.committed_at, d.posted_at, d.counted_at, d.snapshot_at, d.created_at) AS sort_at
  FROM count_docs d
  LEFT JOIN wms_events e
    ON e.id = d.posted_event_id
  LEFT JOIN ledger_stats ls
    ON ls.event_id = e.id
  LEFT JOIN count_stats cs
    ON cs.doc_id = d.id
),
inbound_reversal_rows AS (
  SELECT
    'INBOUND_REVERSAL'::text AS adjustment_type,
    e.id::int AS object_id,
    e.event_no::text AS object_no,
    e.warehouse_id::int AS warehouse_id,
    e.status::text AS status,
    e.source_type::text AS source_type,
    e.source_ref::text AS source_ref,
    e.event_type::text AS event_type,
    e.event_kind::text AS event_kind,
    e.target_event_id::int AS target_event_id,
    e.occurred_at AS occurred_at,
    e.committed_at AS committed_at,
    e.created_at AS created_at,
    COALESCE(COUNT(l.id), 0)::int AS line_count,
    COALESCE(ls.delta_total, -COALESCE(SUM(l.qty_base), 0), 0)::int AS qty_total,
    COALESCE(ls.ledger_row_count, 0)::int AS ledger_row_count,
    ls.ledger_reason::text AS ledger_reason,
    ls.ledger_reason_canon::text AS ledger_reason_canon,
    ls.ledger_sub_reason::text AS ledger_sub_reason,
    COALESCE(ls.delta_total, -COALESCE(SUM(l.qty_base), 0), 0)::int AS delta_total,
    COALESCE(ls.abs_delta_total, COALESCE(SUM(l.qty_base), 0), 0)::int AS abs_delta_total,
    'DECREASE'::text AS direction,
    '入库冲回'::text AS action_title,
    (
      CASE e.source_type
        WHEN 'PURCHASE_ORDER' THEN '采购入库'
        WHEN 'MANUAL' THEN '手动入库'
        WHEN 'RETURN' THEN '退货入库'
        ELSE COALESCE(e.source_type, '入库')
      END
      || '，冲回 '
      || COALESCE(ls.abs_delta_total, COALESCE(SUM(l.qty_base), 0), 0)::text
    )::text AS action_summary,
    e.remark::text AS remark,
    ('/inventory-adjustment/inbound-reversal?event_id=' || e.id::text)::text AS detail_route,
    COALESCE(e.committed_at, e.occurred_at, e.created_at) AS sort_at
  FROM wms_events e
  LEFT JOIN inbound_event_lines l
    ON l.event_id = e.id
  LEFT JOIN ledger_stats ls
    ON ls.event_id = e.id
  WHERE e.event_type = 'INBOUND'
    AND e.event_kind = 'REVERSAL'
  GROUP BY
    e.id,
    e.event_no,
    e.warehouse_id,
    e.status,
    e.source_type,
    e.source_ref,
    e.event_type,
    e.event_kind,
    e.target_event_id,
    e.occurred_at,
    e.committed_at,
    e.created_at,
    e.remark,
    ls.ledger_row_count,
    ls.ledger_reason,
    ls.ledger_reason_canon,
    ls.ledger_sub_reason,
    ls.delta_total,
    ls.abs_delta_total
),
outbound_reversal_rows AS (
  SELECT
    'OUTBOUND_REVERSAL'::text AS adjustment_type,
    e.id::int AS object_id,
    e.event_no::text AS object_no,
    e.warehouse_id::int AS warehouse_id,
    e.status::text AS status,
    e.source_type::text AS source_type,
    e.source_ref::text AS source_ref,
    e.event_type::text AS event_type,
    e.event_kind::text AS event_kind,
    e.target_event_id::int AS target_event_id,
    e.occurred_at AS occurred_at,
    e.committed_at AS committed_at,
    e.created_at AS created_at,
    COALESCE(COUNT(l.id), 0)::int AS line_count,
    COALESCE(ls.delta_total, COALESCE(SUM(l.qty_outbound), 0), 0)::int AS qty_total,
    COALESCE(ls.ledger_row_count, 0)::int AS ledger_row_count,
    ls.ledger_reason::text AS ledger_reason,
    ls.ledger_reason_canon::text AS ledger_reason_canon,
    ls.ledger_sub_reason::text AS ledger_sub_reason,
    COALESCE(ls.delta_total, COALESCE(SUM(l.qty_outbound), 0), 0)::int AS delta_total,
    COALESCE(ls.abs_delta_total, COALESCE(SUM(l.qty_outbound), 0), 0)::int AS abs_delta_total,
    'INCREASE'::text AS direction,
    '出库冲回'::text AS action_title,
    (
      CASE e.source_type
        WHEN 'ORDER' THEN '订单出库'
        WHEN 'MANUAL' THEN '手动出库'
        ELSE COALESCE(e.source_type, '出库')
      END
      || '，补回 '
      || COALESCE(ls.abs_delta_total, COALESCE(SUM(l.qty_outbound), 0), 0)::text
    )::text AS action_summary,
    e.remark::text AS remark,
    ('/inventory-adjustment/outbound-reversal?event_id=' || e.id::text)::text AS detail_route,
    COALESCE(e.committed_at, e.occurred_at, e.created_at) AS sort_at
  FROM wms_events e
  LEFT JOIN outbound_event_lines l
    ON l.event_id = e.id
  LEFT JOIN ledger_stats ls
    ON ls.event_id = e.id
  WHERE e.event_type = 'OUTBOUND'
    AND e.event_kind = 'REVERSAL'
  GROUP BY
    e.id,
    e.event_no,
    e.warehouse_id,
    e.status,
    e.source_type,
    e.source_ref,
    e.event_type,
    e.event_kind,
    e.target_event_id,
    e.occurred_at,
    e.committed_at,
    e.created_at,
    e.remark,
    ls.ledger_row_count,
    ls.ledger_reason,
    ls.ledger_reason_canon,
    ls.ledger_sub_reason,
    ls.delta_total,
    ls.abs_delta_total
),
unioned AS (
  SELECT * FROM count_rows
  UNION ALL
  SELECT * FROM inbound_reversal_rows
  UNION ALL
  SELECT * FROM outbound_reversal_rows
)
"""


def _build_where(
    *,
    adjustment_type: str | None,
    warehouse_id: int | None,
) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}

    if adjustment_type is not None:
        clauses.append("adjustment_type = :adjustment_type")
        params["adjustment_type"] = str(adjustment_type).strip().upper()

    if warehouse_id is not None:
        clauses.append("warehouse_id = :warehouse_id")
        params["warehouse_id"] = int(warehouse_id)

    if not clauses:
        return "", params

    return "WHERE " + " AND ".join(clauses), params


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


async def _enrich_summary_ledger_rows(
    session: AsyncSession,
    *,
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    为库存调节汇总详情的 ledger_rows 补齐商品展示字段。

    WMS 事实仍来自 stock_ledger / lots；
    商品名和基础单位展示通过 PMS export read service 获取，
    不在 WMS summary repo 里直接读取 PMS owner items / item_uoms。
    """
    out = [dict(row) for row in rows]
    item_ids = _clean_item_ids(row.get("item_id") for row in out)

    if not item_ids:
        return out

    item_map = await ItemReadService(session).aget_basics_by_item_ids(item_ids=item_ids)

    base_uom_map: dict[int, dict[str, object | None]] = {
        item_id: {"base_item_uom_id": None, "base_uom_name": None}
        for item_id in item_ids
    }
    uoms = await PmsExportUomReadService(session).alist_uoms(item_ids=item_ids)
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

    for row in out:
        item_id = int(row["item_id"])
        item = item_map.get(item_id)
        base_uom = base_uom_map.get(item_id, {})

        row["item_name"] = str(item.name).strip() if item is not None and str(item.name or "").strip() else None
        row["base_item_uom_id"] = base_uom.get("base_item_uom_id")
        row["base_uom_name"] = base_uom.get("base_uom_name")

    return out


async def list_inventory_adjustment_summary_rows(
    session: AsyncSession,
    *,
    adjustment_type: str | None,
    warehouse_id: int | None,
    limit: int,
    offset: int,
) -> tuple[int, list[dict[str, Any]]]:
    where_sql, params = _build_where(
        adjustment_type=adjustment_type,
        warehouse_id=warehouse_id,
    )

    count_sql = text(
        f"""
        {SUMMARY_CTE}
        SELECT COUNT(*)
        FROM unioned
        {where_sql}
        """
    )
    total = int((await session.execute(count_sql, params)).scalar_one() or 0)

    list_params = {
        **params,
        "limit": int(limit),
        "offset": int(offset),
    }
    list_sql = text(
        f"""
        {SUMMARY_CTE}
        SELECT
          adjustment_type,
          object_id,
          object_no,
          warehouse_id,
          status,
          source_type,
          source_ref,
          event_type,
          event_kind,
          target_event_id,
          occurred_at,
          committed_at,
          created_at,
          line_count,
          qty_total,
          ledger_row_count,
          ledger_reason,
          ledger_reason_canon,
          ledger_sub_reason,
          delta_total,
          abs_delta_total,
          direction,
          action_title,
          action_summary,
          remark,
          detail_route
        FROM unioned
        {where_sql}
        ORDER BY sort_at DESC NULLS LAST, created_at DESC, object_id DESC
        LIMIT :limit OFFSET :offset
        """
    )
    rows = (await session.execute(list_sql, list_params)).mappings().all()
    return total, [dict(r) for r in rows]



async def get_inventory_adjustment_summary_row(
    session: AsyncSession,
    *,
    adjustment_type: str,
    object_id: int,
) -> dict[str, Any] | None:
    sql = text(
        f"""
        {SUMMARY_CTE}
        SELECT
          adjustment_type,
          object_id,
          object_no,
          warehouse_id,
          status,
          source_type,
          source_ref,
          event_type,
          event_kind,
          target_event_id,
          occurred_at,
          committed_at,
          created_at,
          line_count,
          qty_total,
          ledger_row_count,
          ledger_reason,
          ledger_reason_canon,
          ledger_sub_reason,
          delta_total,
          abs_delta_total,
          direction,
          action_title,
          action_summary,
          remark,
          detail_route
        FROM unioned
        WHERE adjustment_type = :adjustment_type
          AND object_id = :object_id
        LIMIT 1
        """
    )
    row = (
        await session.execute(
            sql,
            {
                "adjustment_type": str(adjustment_type).strip().upper(),
                "object_id": int(object_id),
            },
        )
    ).mappings().first()
    return dict(row) if row is not None else None


async def list_inventory_adjustment_summary_ledger_rows(
    session: AsyncSession,
    *,
    adjustment_type: str,
    object_id: int,
) -> list[dict[str, Any]]:
    sql = text(
        """
        WITH target_event AS (
          SELECT
            CASE
              WHEN :adjustment_type = 'COUNT' THEN (
                SELECT posted_event_id
                FROM count_docs
                WHERE id = :object_id
                LIMIT 1
              )
              ELSE :object_id
            END::int AS event_id
        )
        SELECT
          l.id,
          l.event_id,
          l.ref,
          l.ref_line,
          l.trace_id,
          l.warehouse_id,
          l.item_id,
          l.lot_id,
          lo.lot_code,
          l.reason,
          l.reason_canon,
          l.sub_reason,
          l.delta,
          l.after_qty,
          l.occurred_at,
          l.created_at
        FROM target_event t
        JOIN stock_ledger l
          ON l.event_id = t.event_id
        LEFT JOIN lots lo
          ON lo.id = l.lot_id
        ORDER BY l.ref_line ASC, l.id ASC
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "adjustment_type": str(adjustment_type).strip().upper(),
                "object_id": int(object_id),
            },
        )
    ).mappings().all()
    return await _enrich_summary_ledger_rows(
        session,
        rows=[dict(r) for r in rows],
    )


__all__ = [
    "list_inventory_adjustment_summary_rows",
    "get_inventory_adjustment_summary_row",
    "list_inventory_adjustment_summary_ledger_rows",
]
