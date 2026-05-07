# app/wms/outbound/repos/manual_doc_repo.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

UTC = timezone.utc


def _gen_doc_no() -> str:
    return f"MOB-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _require_text(value: Any, field_name: str) -> str:
    s = _clean_text(value)
    if not s:
        raise ValueError(f"{field_name}_required")
    return s


async def create_manual_doc(
    session: AsyncSession,
    *,
    warehouse_id: int,
    doc_type: str,
    recipient_name: str,
    receiver_phone: str,
    receiver_province: str,
    receiver_city: str,
    receiver_district: str | None,
    receiver_address: str,
    receiver_postcode: str | None,
    remark: str | None,
    created_by: int | None,
    lines: List[Dict[str, Any]],
) -> int:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO manual_outbound_docs (
                  warehouse_id,
                  doc_no,
                  doc_type,
                  status,
                  recipient_name,
                  receiver_phone,
                  receiver_province,
                  receiver_city,
                  receiver_district,
                  receiver_address,
                  receiver_postcode,
                  remark,
                  created_by,
                  created_at
                )
                VALUES (
                  :warehouse_id,
                  :doc_no,
                  :doc_type,
                  'DRAFT',
                  :recipient_name,
                  :receiver_phone,
                  :receiver_province,
                  :receiver_city,
                  :receiver_district,
                  :receiver_address,
                  :receiver_postcode,
                  :remark,
                  :created_by,
                  now()
                )
                RETURNING id
                """
            ),
            {
                "warehouse_id": int(warehouse_id),
                "doc_no": _gen_doc_no(),
                "doc_type": _require_text(doc_type, "doc_type"),
                "recipient_name": _require_text(recipient_name, "recipient_name"),
                "receiver_phone": _require_text(receiver_phone, "receiver_phone"),
                "receiver_province": _require_text(receiver_province, "receiver_province"),
                "receiver_city": _require_text(receiver_city, "receiver_city"),
                "receiver_district": _clean_text(receiver_district),
                "receiver_address": _require_text(receiver_address, "receiver_address"),
                "receiver_postcode": _clean_text(receiver_postcode),
                "remark": _clean_text(remark),
                "created_by": int(created_by) if created_by is not None else None,
            },
        )
    ).first()
    if not row:
        raise ValueError("create_manual_doc_failed")

    doc_id = int(row[0])

    line_no = 1
    for ln in lines:
        await session.execute(
            text(
                """
                INSERT INTO manual_outbound_lines (
                  doc_id,
                  line_no,
                  item_id,
                  item_uom_id,
                  requested_qty,
                  item_name_snapshot,
                  item_sku_snapshot,
                  item_spec_snapshot,
                  uom_name_snapshot
                )
                VALUES (
                  :doc_id,
                  :line_no,
                  :item_id,
                  :item_uom_id,
                  :requested_qty,
                  :item_name_snapshot,
                  :item_sku_snapshot,
                  :item_spec_snapshot,
                  :uom_name_snapshot
                )
                """
            ),
            {
                "doc_id": doc_id,
                "line_no": int(line_no),
                "item_id": int(ln["item_id"]),
                "item_uom_id": int(ln["item_uom_id"]),
                "requested_qty": int(ln["requested_qty"]),
                "item_name_snapshot": (
                    str(ln["item_name_snapshot"]).strip()
                    if ln.get("item_name_snapshot")
                    else None
                ),
                "item_sku_snapshot": (
                    str(ln["item_sku_snapshot"]).strip()
                    if ln.get("item_sku_snapshot")
                    else None
                ),
                "item_spec_snapshot": (
                    str(ln["item_spec_snapshot"]).strip()
                    if ln.get("item_spec_snapshot")
                    else None
                ),
                "uom_name_snapshot": (
                    str(ln["uom_name_snapshot"]).strip()
                    if ln.get("uom_name_snapshot")
                    else None
                ),
            },
        )
        line_no += 1

    return doc_id


async def list_manual_docs(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT
                      d.id,
                      d.warehouse_id,
                      d.doc_no,
                      d.doc_type,
                      d.status,
                      d.recipient_name,
                      d.recipient_id,
                      d.receiver_phone,
                      d.receiver_province,
                      d.receiver_city,
                      d.receiver_district,
                      d.receiver_address,
                      d.receiver_postcode,
                      d.remark,
                      d.created_by,
                      d.created_at,
                      d.released_by,
                      d.released_at,
                      d.voided_by,
                      d.voided_at
                    FROM manual_outbound_docs d
                    ORDER BY d.created_at DESC, d.id DESC
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {"limit": int(limit), "offset": int(offset)},
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


async def get_manual_doc_head(
    session: AsyncSession,
    *,
    doc_id: int,
) -> Mapping[str, Any]:
    row = (
        (
            await session.execute(
                text(
                    """
                    SELECT
                      d.id,
                      d.warehouse_id,
                      d.doc_no,
                      d.doc_type,
                      d.status,
                      d.recipient_name,
                      d.recipient_id,
                      d.receiver_phone,
                      d.receiver_province,
                      d.receiver_city,
                      d.receiver_district,
                      d.receiver_address,
                      d.receiver_postcode,
                      d.remark,
                      d.created_by,
                      d.created_at,
                      d.released_by,
                      d.released_at,
                      d.voided_by,
                      d.voided_at
                    FROM manual_outbound_docs d
                    WHERE d.id = :doc_id
                    LIMIT 1
                    """
                ),
                {"doc_id": int(doc_id)},
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError(f"manual_doc_not_found: id={doc_id}")
    return row


async def get_manual_doc_lines(
    session: AsyncSession,
    *,
    doc_id: int,
) -> List[Dict[str, Any]]:
    rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT
                      l.id,
                      l.line_no,
                      l.item_id,
                      l.item_uom_id,
                      l.requested_qty,
                      l.item_name_snapshot,
                      l.item_sku_snapshot,
                      l.item_spec_snapshot,
                      l.uom_name_snapshot
                    FROM manual_outbound_lines l
                    WHERE l.doc_id = :doc_id
                    ORDER BY l.line_no ASC, l.id ASC
                    """
                ),
                {"doc_id": int(doc_id)},
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


async def list_manual_doc_progress(
    session: AsyncSession,
    *,
    doc_id: int,
) -> List[Dict[str, Any]]:
    rows = (
        (
            await session.execute(
                text(
                    """
                    SELECT
                      l.id AS manual_doc_line_id,
                      l.line_no,
                      l.requested_qty,
                      COALESCE(SUM(oel.qty_outbound), 0) AS submitted_qty
                    FROM manual_outbound_lines l
                    LEFT JOIN outbound_event_lines oel
                      ON oel.manual_doc_line_id = l.id
                    WHERE l.doc_id = :doc_id
                    GROUP BY l.id, l.line_no, l.requested_qty
                    ORDER BY l.line_no ASC, l.id ASC
                    """
                ),
                {"doc_id": int(doc_id)},
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


async def complete_manual_doc(
    session: AsyncSession,
    *,
    doc_id: int,
) -> None:
    upd = await session.execute(
        text(
            """
            UPDATE manual_outbound_docs
            SET status = 'COMPLETED'
            WHERE id = :doc_id
              AND status = 'RELEASED'
            """
        ),
        {"doc_id": int(doc_id)},
    )
    if upd.rowcount != 1:
        raise ValueError(f"manual_doc_complete_reject: id={doc_id}")


async def release_manual_doc(
    session: AsyncSession,
    *,
    doc_id: int,
    released_by: int | None,
) -> None:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM manual_outbound_lines
                WHERE doc_id = :doc_id
                """
            ),
            {"doc_id": int(doc_id)},
        )
    ).first()
    if not row or int(row[0]) <= 0:
        raise ValueError("manual_doc_has_no_lines")

    head = (
        (
            await session.execute(
                text(
                    """
                    SELECT
                      recipient_name,
                      receiver_phone,
                      receiver_province,
                      receiver_city,
                      receiver_address
                    FROM manual_outbound_docs
                    WHERE id = :doc_id
                    LIMIT 1
                    """
                ),
                {"doc_id": int(doc_id)},
            )
        )
        .mappings()
        .first()
    )
    if head is None:
        raise ValueError(f"manual_doc_not_found: id={doc_id}")

    required_fields = [
        ("recipient_name", head.get("recipient_name")),
        ("receiver_phone", head.get("receiver_phone")),
        ("receiver_province", head.get("receiver_province")),
        ("receiver_city", head.get("receiver_city")),
        ("receiver_address", head.get("receiver_address")),
    ]
    missing = [name for name, value in required_fields if _clean_text(value) is None]
    if missing:
        raise ValueError("manual_doc_receiver_incomplete: missing=" + ",".join(missing))

    upd = await session.execute(
        text(
            """
            UPDATE manual_outbound_docs
            SET
              status = 'RELEASED',
              released_by = :released_by,
              released_at = now()
            WHERE id = :doc_id
              AND status = 'DRAFT'
            """
        ),
        {
            "doc_id": int(doc_id),
            "released_by": int(released_by) if released_by is not None else None,
        },
    )
    if upd.rowcount != 1:
        raise ValueError(f"manual_doc_release_reject: id={doc_id}")


async def void_manual_doc(
    session: AsyncSession,
    *,
    doc_id: int,
    voided_by: int | None,
) -> None:
    upd = await session.execute(
        text(
            """
            UPDATE manual_outbound_docs
            SET
              status = 'VOIDED',
              voided_by = :voided_by,
              voided_at = now()
            WHERE id = :doc_id
              AND status IN ('DRAFT', 'RELEASED')
            """
        ),
        {
            "doc_id": int(doc_id),
            "voided_by": int(voided_by) if voided_by is not None else None,
        },
    )
    if upd.rowcount != 1:
        raise ValueError(f"manual_doc_void_reject: id={doc_id}")
