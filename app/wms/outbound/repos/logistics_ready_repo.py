# app/wms/outbound/repos/logistics_ready_repo.py
from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

READY_EXPORT_STATUSES = ("PENDING", "FAILED")
READY_SOURCE_DOC_TYPES = ("ORDER_OUTBOUND", "MANUAL_OUTBOUND")


def _json_array(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(x) for x in value if isinstance(x, Mapping)]
    return []


def _row_to_ready_record(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_system": str(row["source_system"]),
        "request_source": str(row["request_source"]),
        "source_doc_type": str(row["source_doc_type"]),
        "source_doc_id": int(row["source_doc_id"]),
        "source_doc_no": str(row["source_doc_no"]),
        "source_ref": str(row["source_ref"]),
        "export_status": str(row["export_status"]),
        "logistics_status": str(row["logistics_status"]),
        "platform": row.get("platform"),
        "store_code": row.get("store_code"),
        "order_ref": row.get("order_ref"),
        "ext_order_no": row.get("ext_order_no"),
        "warehouse_id": int(row["warehouse_id"]) if row.get("warehouse_id") is not None else None,
        "warehouse_name_snapshot": row.get("warehouse_name_snapshot"),
        "receiver_name": row.get("receiver_name"),
        "receiver_phone": row.get("receiver_phone"),
        "receiver_province": row.get("receiver_province"),
        "receiver_city": row.get("receiver_city"),
        "receiver_district": row.get("receiver_district"),
        "receiver_address": row.get("receiver_address"),
        "receiver_postcode": row.get("receiver_postcode"),
        "outbound_event_id": int(row["outbound_event_id"]) if row.get("outbound_event_id") is not None else None,
        "outbound_source_ref": row.get("outbound_source_ref"),
        "outbound_completed_at": row.get("outbound_completed_at"),
        "shipment_items": _json_array(row.get("shipment_items")),
        "handoff_created_at": row["handoff_created_at"],
        "handoff_updated_at": row["handoff_updated_at"],
    }


def _build_ready_where(
    *,
    source_doc_type: str | None,
    export_status: str | None,
) -> tuple[str, dict[str, object]]:
    params: dict[str, object] = {}
    clauses = [
        "1 = 1",
        "p.outbound_event_id IS NOT NULL",
        "jsonb_array_length(p.shipment_items) > 0",
        "NULLIF(BTRIM(COALESCE(p.receiver_name, '')), '') IS NOT NULL",
        "NULLIF(BTRIM(COALESCE(p.receiver_phone, '')), '') IS NOT NULL",
        "NULLIF(BTRIM(COALESCE(p.receiver_province, '')), '') IS NOT NULL",
        "NULLIF(BTRIM(COALESCE(p.receiver_city, '')), '') IS NOT NULL",
        "NULLIF(BTRIM(COALESCE(p.receiver_address, '')), '') IS NOT NULL",
    ]

    if source_doc_type is not None:
        clauses.append("r.source_doc_type = :source_doc_type")
        params["source_doc_type"] = source_doc_type

    if export_status is not None:
        clauses.append("r.export_status = :export_status")
        params["export_status"] = export_status
    else:
        clauses.append("r.export_status = ANY(:ready_statuses)")
        params["ready_statuses"] = list(READY_EXPORT_STATUSES)

    return " AND ".join(clauses), params


async def count_logistics_ready_records(
    session: AsyncSession,
    *,
    source_doc_type: str | None = None,
    export_status: str | None = None,
) -> int:
    where_sql, params = _build_ready_where(
        source_doc_type=source_doc_type,
        export_status=export_status,
    )

    row = (
        await session.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM wms_logistics_export_records r
                JOIN wms_logistics_handoff_payloads p
                  ON p.export_record_id = r.id
                WHERE {where_sql}
                """
            ),
            params,
        )
    ).scalar_one()

    return int(row)


async def list_logistics_ready_records(
    session: AsyncSession,
    *,
    source_doc_type: str | None = None,
    export_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    where_sql, params = _build_ready_where(
        source_doc_type=source_doc_type,
        export_status=export_status,
    )
    params["limit"] = int(limit)
    params["offset"] = int(offset)

    rows = (
        (
            await session.execute(
                text(
                    f"""
                    SELECT
                      p.source_system,
                      p.request_source,
                      r.source_doc_type,
                      r.source_doc_id,
                      r.source_doc_no,
                      r.source_ref,
                      r.export_status,
                      r.logistics_status,

                      p.platform,
                      p.store_code,
                      p.order_ref,
                      p.ext_order_no,
                      p.warehouse_id,
                      p.warehouse_name_snapshot,

                      p.receiver_name,
                      p.receiver_phone,
                      p.receiver_province,
                      p.receiver_city,
                      p.receiver_district,
                      p.receiver_address,
                      p.receiver_postcode,

                      p.outbound_event_id,
                      p.outbound_source_ref,
                      p.outbound_completed_at,
                      p.shipment_items,

                      r.created_at AS handoff_created_at,
                      r.updated_at AS handoff_updated_at
                    FROM wms_logistics_export_records r
                    JOIN wms_logistics_handoff_payloads p
                      ON p.export_record_id = r.id
                    WHERE {where_sql}
                    ORDER BY r.created_at ASC, r.id ASC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                params,
            )
        )
        .mappings()
        .all()
    )

    return [_row_to_ready_record(row) for row in rows]
