from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.inbound.contracts.procurement_receiving_result import (
    ProcurementReceivingResultDetailOut,
    ProcurementReceivingResultLineOut,
    ProcurementReceivingResultsOut,
)


def _normalize_limit(value: int | None) -> int:
    if value is None:
        return 50

    return min(max(int(value), 1), 200)


def _normalize_after_event_id(value: int | None) -> int:
    if value is None:
        return 0

    return max(int(value), 0)


def _map_row(row: dict[str, Any]) -> ProcurementReceivingResultLineOut:
    return ProcurementReceivingResultLineOut.model_validate(
        {
            "wms_event_id": row["wms_event_id"],
            "wms_event_no": row["wms_event_no"],
            "trace_id": row["trace_id"],
            "event_kind": row["event_kind"],
            "event_status": row["event_status"],
            "occurred_at": row["occurred_at"],
            "receipt_no": row["receipt_no"],
            "procurement_po_id": row["procurement_po_id"],
            "procurement_po_no": row["procurement_po_no"],
            "wms_event_line_no": row["wms_event_line_no"],
            "procurement_po_line_id": row["procurement_po_line_id"],
            "warehouse_id": row["warehouse_id"],
            "item_id": row["item_id"],
            "qty_delta_base": row["qty_delta_base"],
            "lot_code_input": row["lot_code_input"],
            "production_date": row["production_date"],
            "expiry_date": row["expiry_date"],
            "lot_id": row["lot_id"],
        }
    )


async def list_procurement_receiving_results(
    session: AsyncSession,
    *,
    after_event_id: int | None = 0,
    limit: int | None = 50,
    procurement_po_id: int | None = None,
    receipt_no: str | None = None,
) -> ProcurementReceivingResultsOut:
    """List WMS inbound commit results for procurement consumption.

    边界说明：
    - 只读 WMS 入库事件事实。
    - 不更新采购完成情况。
    - 不暴露 WMS 本地旧 purchase_order_lines 语义。
    - procurement_po_line_id 来自 inbound_event_lines.source_line_id。
    """

    limit_n = _normalize_limit(limit)
    after_event_id_n = _normalize_after_event_id(after_event_id)

    where_clauses = [
        "e.event_type = 'INBOUND'",
        "e.source_type = 'PURCHASE_ORDER'",
        "e.event_kind = 'COMMIT'",
        "e.status = 'COMMITTED'",
        "e.id > :after_event_id",
        "iel.source_line_id IS NOT NULL",
        "r.source_doc_id IS NOT NULL",
        "r.source_doc_no_snapshot IS NOT NULL",
    ]
    params: dict[str, Any] = {
        "after_event_id": after_event_id_n,
        "limit": limit_n,
    }

    if procurement_po_id is not None:
        where_clauses.append("r.source_doc_id = :procurement_po_id")
        params["procurement_po_id"] = int(procurement_po_id)

    normalized_receipt_no = str(receipt_no or "").strip()
    if normalized_receipt_no:
        where_clauses.append("r.receipt_no = :receipt_no")
        params["receipt_no"] = normalized_receipt_no

    where_sql = " AND ".join(where_clauses)

    sql = text(
        f"""
        WITH event_page AS (
          SELECT e.id
          FROM wms_events e
          JOIN inbound_receipts r
            ON r.receipt_no = e.source_ref
           AND r.source_type = 'PURCHASE_ORDER'
          JOIN inbound_event_lines iel
            ON iel.event_id = e.id
          WHERE {where_sql}
          GROUP BY e.id
          ORDER BY e.id ASC
          LIMIT :limit
        )
        SELECT
          e.id AS wms_event_id,
          e.event_no AS wms_event_no,
          e.trace_id AS trace_id,
          e.event_kind AS event_kind,
          e.status AS event_status,
          e.occurred_at AS occurred_at,

          r.receipt_no AS receipt_no,
          r.source_doc_id AS procurement_po_id,
          r.source_doc_no_snapshot AS procurement_po_no,

          iel.line_no AS wms_event_line_no,
          iel.source_line_id AS procurement_po_line_id,
          e.warehouse_id AS warehouse_id,
          iel.item_id AS item_id,
          iel.qty_base AS qty_delta_base,
          iel.lot_code_input AS lot_code_input,
          iel.production_date AS production_date,
          iel.expiry_date AS expiry_date,
          iel.lot_id AS lot_id
        FROM event_page ep
        JOIN wms_events e
          ON e.id = ep.id
        JOIN inbound_receipts r
          ON r.receipt_no = e.source_ref
         AND r.source_type = 'PURCHASE_ORDER'
        JOIN inbound_event_lines iel
          ON iel.event_id = e.id
        WHERE iel.source_line_id IS NOT NULL
        ORDER BY e.id ASC, iel.line_no ASC, iel.id ASC
        """
    )

    rows = [dict(row) for row in (await session.execute(sql, params)).mappings().all()]
    items = [_map_row(row) for row in rows]
    next_after_event_id = max((item.wms_event_id for item in items), default=after_event_id_n)

    return ProcurementReceivingResultsOut(
        items=items,
        after_event_id=after_event_id_n,
        next_after_event_id=next_after_event_id,
        limit=limit_n,
        has_more=len({item.wms_event_id for item in items}) >= limit_n,
    )


async def get_procurement_receiving_result_detail(
    session: AsyncSession,
    *,
    event_id: int,
) -> ProcurementReceivingResultDetailOut:
    result = await list_procurement_receiving_results(
        session,
        after_event_id=int(event_id) - 1,
        limit=1,
    )

    items = [item for item in result.items if item.wms_event_id == int(event_id)]

    if not items:
        raise HTTPException(
            status_code=404,
            detail=f"procurement_receiving_result_not_found:{int(event_id)}",
        )

    return ProcurementReceivingResultDetailOut(
        event_id=int(event_id),
        items=items,
    )


__all__ = [
    "get_procurement_receiving_result_detail",
    "list_procurement_receiving_results",
]
