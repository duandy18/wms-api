# app/wms/outbound/repos/logistics_ready_repo.py
from __future__ import annotations

import json
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

READY_EXPORT_STATUSES = ("PENDING", "FAILED")
READY_SOURCE_DOC_TYPES = ("ORDER_OUTBOUND", "MANUAL_OUTBOUND")


def _snapshot_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _build_items(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_lines = snapshot.get("lines")
    if not isinstance(raw_lines, list):
        return []

    items: list[dict[str, Any]] = []
    for idx, raw in enumerate(raw_lines, start=1):
        if not isinstance(raw, Mapping):
            continue

        qty = raw.get("qty_outbound", raw.get("qty", 0))
        items.append(
            {
                "line_no": int(raw.get("ref_line") or idx),
                "item_id": _int_or_none(raw.get("item_id")),
                "qty": int(qty or 0),
                "lot_id": _int_or_none(raw.get("lot_id")),
                "lot_code_snapshot": _clean_text(raw.get("lot_code_snapshot")),
                "item_name_snapshot": _clean_text(raw.get("item_name_snapshot")),
                "item_sku_snapshot": _clean_text(raw.get("item_sku_snapshot")),
                "item_spec_snapshot": _clean_text(raw.get("item_spec_snapshot")),
            }
        )

    return items


def _warehouse_id_from_row(row: Mapping[str, Any], snapshot: Mapping[str, Any]) -> int | None:
    if str(row["source_doc_type"]) == "ORDER_OUTBOUND":
        value = row.get("order_actual_warehouse_id")
        return _int_or_none(value) or _int_or_none(snapshot.get("warehouse_id"))
    value = row.get("manual_warehouse_id")
    return _int_or_none(value) or _int_or_none(snapshot.get("warehouse_id"))


def _row_to_ready_record(row: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = _snapshot_dict(row.get("source_snapshot"))
    warehouse_id = _warehouse_id_from_row(row, snapshot)

    if str(row["source_doc_type"]) == "ORDER_OUTBOUND":
        receiver_name = _clean_text(row.get("receiver_name"))
        receiver_phone = _clean_text(row.get("receiver_phone"))
        province = _clean_text(row.get("province"))
        city = _clean_text(row.get("city"))
        district = _clean_text(row.get("district"))
        address_detail = _clean_text(row.get("address_detail"))
        platform = _clean_text(row.get("platform"))
        store_code = _clean_text(row.get("store_code"))
        platform_order_no = _clean_text(row.get("platform_order_no"))
        outbound_completed_at = row.get("outbound_completed_at")
    else:
        receiver_name = _clean_text(row.get("manual_recipient_name"))
        receiver_phone = None
        province = None
        city = None
        district = None
        address_detail = None
        platform = None
        store_code = None
        platform_order_no = None
        outbound_completed_at = snapshot.get("occurred_at")

    source_ref = str(row["source_ref"])
    packages = [
        {
            "source_package_ref": f"{source_ref}:PACKAGE:1",
            "package_no": 1,
            "warehouse_id": warehouse_id,
            "weight_kg": None,
            "items": _build_items(snapshot),
        }
    ]

    return {
        "source_system": "WMS",
        "source_doc_type": str(row["source_doc_type"]),
        "source_doc_id": int(row["source_doc_id"]),
        "source_doc_no": str(row["source_doc_no"]),
        "source_ref": source_ref,
        "export_status": str(row["export_status"]),
        "logistics_status": str(row["logistics_status"]),
        "platform": platform,
        "store_code": store_code,
        "platform_order_no": platform_order_no,
        "warehouse_id": warehouse_id,
        "receiver_name": receiver_name,
        "receiver_phone": receiver_phone,
        "province": province,
        "city": city,
        "district": district,
        "address_detail": address_detail,
        "outbound_completed_at": outbound_completed_at,
        "handoff_created_at": row["handoff_created_at"],
        "handoff_updated_at": row["handoff_updated_at"],
        "packages": packages,
        "source_snapshot": snapshot,
    }


def _build_ready_where(
    *,
    source_doc_type: str | None,
    export_status: str | None,
) -> tuple[str, dict[str, object]]:
    params: dict[str, object] = {}
    clauses = ["1 = 1"]

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
                      r.source_doc_type,
                      r.source_doc_id,
                      r.source_doc_no,
                      r.source_ref,
                      r.export_status,
                      r.logistics_status,
                      r.source_snapshot,
                      r.created_at AS handoff_created_at,
                      r.updated_at AS handoff_updated_at,

                      o.platform,
                      o.store_code,
                      o.ext_order_no AS platform_order_no,
                      f.actual_warehouse_id AS order_actual_warehouse_id,
                      f.outbound_completed_at AS outbound_completed_at,
                      a.receiver_name,
                      a.receiver_phone,
                      a.province,
                      a.city,
                      a.district,
                      a.detail AS address_detail,

                      md.warehouse_id AS manual_warehouse_id,
                      md.recipient_name AS manual_recipient_name
                    FROM wms_logistics_export_records r
                    LEFT JOIN orders o
                      ON r.source_doc_type = 'ORDER_OUTBOUND'
                     AND o.id = r.source_doc_id
                    LEFT JOIN order_fulfillment f
                      ON f.order_id = o.id
                    LEFT JOIN order_address a
                      ON a.order_id = o.id
                    LEFT JOIN manual_outbound_docs md
                      ON r.source_doc_type = 'MANUAL_OUTBOUND'
                     AND md.id = r.source_doc_id
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
