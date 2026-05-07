# app/shipping_assist/handoffs/repository.py
#
# 分拆说明：
# - 本文件承载 Shipping Assist / Handoffs（发货交接）只读查询；
# - wms_logistics_export_records 是 WMS 与 Logistics 的交接状态主表；
# - 不读取 shipping_records，避免把交接状态与物流事实台账混在一起。
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


SOURCE_DOC_TYPES = {"ORDER_OUTBOUND", "MANUAL_OUTBOUND"}
EXPORT_STATUSES = {"PENDING", "EXPORTED", "FAILED", "CANCELLED"}
LOGISTICS_STATUSES = {
    "NOT_IMPORTED",
    "IMPORTED",
    "IN_PROGRESS",
    "COMPLETED",
    "FAILED",
}


_SELECT_HANDOFF_BASE = """
SELECT
  id,
  source_doc_type,
  source_doc_id,
  source_doc_no,
  source_ref,
  export_status,
  logistics_status,
  logistics_request_id,
  logistics_request_no,
  exported_at,
  logistics_completed_at,
  last_attempt_at,
  last_error,
  source_snapshot,
  created_at,
  updated_at
FROM wms_logistics_export_records
"""


def _clean_opt_str(value: str | None) -> str | None:
    return (value or "").strip() or None


def _build_where_clause(
    *,
    source_doc_type: str | None,
    export_status: str | None,
    logistics_status: str | None,
    source_ref: str | None,
    source_doc_no: str | None,
    logistics_request_no: str | None,
) -> tuple[str, dict[str, Any]]:
    conditions: list[str] = ["1=1"]
    params: dict[str, Any] = {}

    source_doc_type_clean = _clean_opt_str(source_doc_type)
    if source_doc_type_clean:
        conditions.append("source_doc_type = :source_doc_type")
        params["source_doc_type"] = source_doc_type_clean

    export_status_clean = _clean_opt_str(export_status)
    if export_status_clean:
        conditions.append("export_status = :export_status")
        params["export_status"] = export_status_clean

    logistics_status_clean = _clean_opt_str(logistics_status)
    if logistics_status_clean:
        conditions.append("logistics_status = :logistics_status")
        params["logistics_status"] = logistics_status_clean

    source_ref_clean = _clean_opt_str(source_ref)
    if source_ref_clean:
        conditions.append("source_ref = :source_ref")
        params["source_ref"] = source_ref_clean

    source_doc_no_clean = _clean_opt_str(source_doc_no)
    if source_doc_no_clean:
        conditions.append("source_doc_no ILIKE :source_doc_no_like")
        params["source_doc_no_like"] = f"%{source_doc_no_clean}%"

    logistics_request_no_clean = _clean_opt_str(logistics_request_no)
    if logistics_request_no_clean:
        conditions.append("logistics_request_no = :logistics_request_no")
        params["logistics_request_no"] = logistics_request_no_clean

    return " AND ".join(conditions), params


async def list_shipping_handoffs(
    session: AsyncSession,
    *,
    source_doc_type: str | None,
    export_status: str | None,
    logistics_status: str | None,
    source_ref: str | None,
    source_doc_no: str | None,
    logistics_request_no: str | None,
    limit: int,
    offset: int,
) -> tuple[int, list[dict[str, object]]]:
    where_sql, params = _build_where_clause(
        source_doc_type=source_doc_type,
        export_status=export_status,
        logistics_status=logistics_status,
        source_ref=source_ref,
        source_doc_no=source_doc_no,
        logistics_request_no=logistics_request_no,
    )

    total = int(
        (
            await session.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM wms_logistics_export_records
                    WHERE {where_sql}
                    """
                ),
                params,
            )
        ).scalar()
        or 0
    )

    query_params = dict(params)
    query_params["limit"] = int(limit)
    query_params["offset"] = int(offset)

    rows = (
        await session.execute(
            text(
                f"""
                {_SELECT_HANDOFF_BASE}
                WHERE {where_sql}
                ORDER BY updated_at DESC, id DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            query_params,
        )
    ).mappings().all()

    return total, [dict(row) for row in rows]
