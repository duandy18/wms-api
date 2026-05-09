from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text

from app.wms.inbound.contracts.inbound_commit import InboundCommitIn
from app.wms.inbound.services.inbound_commit_service import commit_inbound
from app.wms.inbound.services.inbound_event_read_service import get_inbound_event_detail


async def _pick_seed_item_uom(session):
    wh_row = await session.execute(
        text(
            """
            SELECT id
            FROM warehouses
            ORDER BY id ASC
            LIMIT 1
            """
        )
    )
    warehouse_id = wh_row.scalar_one()

    row = await session.execute(
        text(
            """
            SELECT
              i.id AS item_id,
              u.id AS uom_id,
              i.lot_source_policy::text AS lot_source_policy,
              i.expiry_policy::text AS expiry_policy
            FROM item_uoms u
            JOIN items i
              ON i.id = u.item_id
            ORDER BY
              CASE
                WHEN i.lot_source_policy::text IN ('SUPPLIER_ONLY', 'SUPPLIER') THEN 0
                ELSE 1
              END,
              u.id ASC
            LIMIT 1
            """
        )
    )
    picked = row.mappings().first()
    assert picked is not None, "expected seeded item_uoms to exist"

    return {
        "warehouse_id": int(warehouse_id),
        "item_id": int(picked["item_id"]),
        "uom_id": int(picked["uom_id"]),
        "lot_source_policy": str(picked["lot_source_policy"] or "INTERNAL_ONLY"),
        "expiry_policy": str(picked["expiry_policy"] or "NONE"),
    }


async def _load_event(session, *, event_id: int):
    row = await session.execute(
        text(
            """
            SELECT
              id,
              event_no,
              event_type,
              warehouse_id,
              source_type,
              source_ref,
              trace_id
            FROM wms_events
            WHERE id = :event_id
            """
        ),
        {"event_id": int(event_id)},
    )
    m = row.mappings().first()
    return dict(m) if m else None


async def _load_event_line(session, *, event_id: int):
    row = await session.execute(
        text(
            """
            SELECT
              id,
              event_id,
              line_no,
              item_id,
              actual_uom_id,
              actual_qty_input,
              actual_ratio_to_base_snapshot,
              qty_base,
              lot_id,
              lot_code_input
            FROM inbound_event_lines
            WHERE event_id = :event_id
            ORDER BY line_no ASC
            LIMIT 1
            """
        ),
        {"event_id": int(event_id)},
    )
    m = row.mappings().first()
    return dict(m) if m else None


async def _load_event_line_snapshots(session, *, event_id: int):
    row = await session.execute(
        text(
            """
            SELECT
              item_id,
              actual_uom_id,
              item_name_snapshot,
              item_spec_snapshot,
              actual_uom_name_snapshot
            FROM inbound_event_lines
            WHERE event_id = :event_id
            ORDER BY line_no ASC
            LIMIT 1
            """
        ),
        {"event_id": int(event_id)},
    )
    m = row.mappings().first()
    return dict(m) if m else None



async def _load_ledger_by_event(session, *, event_id: int):
    row = await session.execute(
        text(
            """
            SELECT
              id,
              event_id,
              trace_id,
              ref,
              ref_line,
              warehouse_id,
              item_id,
              lot_id,
              delta,
              reason,
              reason_canon
            FROM stock_ledger
            WHERE event_id = :event_id
            ORDER BY id ASC
            LIMIT 1
            """
        ),
        {"event_id": int(event_id)},
    )
    m = row.mappings().first()
    return dict(m) if m else None


async def test_inbound_commit_links_wms_event_and_stock_ledger(session):
    picked = await _pick_seed_item_uom(session)

    warehouse_id = int(picked["warehouse_id"])
    item_id = int(picked["item_id"])
    uom_id = int(picked["uom_id"])
    lot_source_policy = str(picked["lot_source_policy"])

    qty_input = 3
    production_date = date.today()
    expiry_date = production_date + timedelta(days=30)

    lot_code_input = None
    if lot_source_policy in {"SUPPLIER_ONLY", "SUPPLIER"}:
        lot_code_input = f"UT-IN-COMMIT-{item_id}-{uom_id}"

    payload = InboundCommitIn.model_validate(
        {
            "warehouse_id": warehouse_id,
            "source_type": "MANUAL",
            "source_ref": None,
            "occurred_at": production_date.isoformat() + "T00:00:00Z",
            "remark": "ut inbound commit event link",
            "lines": [
                {
                    "item_id": item_id,
                    "uom_id": uom_id,
                    "qty_input": qty_input,
                    "lot_code_input": lot_code_input,
                    "production_date": production_date.isoformat(),
                    "expiry_date": expiry_date.isoformat(),
                    "remark": "ut line",
                }
            ],
        }
    )

    out = await commit_inbound(session, payload=payload, user_id=None)

    assert out.ok is True
    assert int(out.event_id) > 0
    assert str(out.event_no).startswith("IE-")
    assert str(out.trace_id).startswith("IN-COMMIT-")
    assert len(out.rows) == 1

    out_row = out.rows[0]
    assert int(out_row.item_id) == item_id
    assert int(out_row.uom_id) == uom_id
    assert int(out_row.qty_input) == qty_input
    assert int(out_row.qty_base) > 0
    assert out_row.lot_id is not None

    event = await _load_event(session, event_id=int(out.event_id))
    assert event is not None
    assert int(event["id"]) == int(out.event_id)
    assert str(event["event_no"]) == str(out.event_no)
    assert str(event["event_type"]) == "INBOUND"
    assert int(event["warehouse_id"]) == warehouse_id
    assert str(event["source_type"]) == "MANUAL"
    assert event["source_ref"] is None
    assert str(event["trace_id"]) == str(out.trace_id)

    event_line = await _load_event_line(session, event_id=int(out.event_id))
    assert event_line is not None
    assert int(event_line["event_id"]) == int(out.event_id)
    assert int(event_line["line_no"]) == 1
    assert int(event_line["item_id"]) == item_id
    assert int(event_line["actual_uom_id"]) == uom_id
    assert int(event_line["actual_qty_input"]) == qty_input
    assert int(event_line["qty_base"]) == int(out_row.qty_base)
    assert int(event_line["lot_id"]) == int(out_row.lot_id)

    ledger = await _load_ledger_by_event(session, event_id=int(out.event_id))
    assert ledger is not None
    assert int(ledger["event_id"]) == int(out.event_id)
    assert str(ledger["trace_id"]) == str(out.trace_id)
    assert str(ledger["ref"]) == str(out.event_no)
    assert int(ledger["ref_line"]) == 1
    assert int(ledger["warehouse_id"]) == warehouse_id
    assert int(ledger["item_id"]) == item_id
    assert int(ledger["lot_id"]) == int(out_row.lot_id)
    assert int(ledger["delta"]) == int(out_row.qty_base)
    assert str(ledger["reason_canon"]) == "RECEIPT"

async def test_inbound_event_detail_reads_line_snapshots_not_pms_current_state(session):
    picked = await _pick_seed_item_uom(session)

    warehouse_id = int(picked["warehouse_id"])
    item_id = int(picked["item_id"])
    uom_id = int(picked["uom_id"])
    lot_source_policy = str(picked["lot_source_policy"])

    production_date = date.today()
    expiry_date = production_date + timedelta(days=30)

    lot_code_input = None
    if lot_source_policy in {"SUPPLIER_ONLY", "SUPPLIER"}:
        lot_code_input = f"UT-IN-EVENT-READ-{item_id}-{uom_id}"

    payload = InboundCommitIn.model_validate(
        {
            "warehouse_id": warehouse_id,
            "source_type": "MANUAL",
            "source_ref": None,
            "occurred_at": production_date.isoformat() + "T00:00:00Z",
            "remark": "ut inbound event snapshot read",
            "lines": [
                {
                    "item_id": item_id,
                    "uom_id": uom_id,
                    "qty_input": 2,
                    "lot_code_input": lot_code_input,
                    "production_date": production_date.isoformat(),
                    "expiry_date": expiry_date.isoformat(),
                    "remark": "snapshot line",
                }
            ],
        }
    )

    out = await commit_inbound(session, payload=payload, user_id=None)
    snap = await _load_event_line_snapshots(session, event_id=int(out.event_id))
    assert snap is not None
    assert snap["item_name_snapshot"]
    assert snap["actual_uom_name_snapshot"]

    await session.execute(
        text("UPDATE items SET name = 'MUTATED-CURRENT-NAME', sku = 'MUTATED-CURRENT-SKU' WHERE id = :item_id"),
        {"item_id": int(item_id)},
    )
    await session.execute(
        text("UPDATE item_uoms SET display_name = 'MUTATED-CURRENT-UOM' WHERE id = :uom_id"),
        {"uom_id": int(uom_id)},
    )
    await session.flush()

    detail = await get_inbound_event_detail(session, event_id=int(out.event_id))
    assert len(detail.lines) == 1

    line = detail.lines[0]
    assert line.item_id == item_id
    assert line.actual_uom_id == uom_id
    assert line.item_name == snap["item_name_snapshot"]
    assert line.actual_uom_name == snap["actual_uom_name_snapshot"]
    assert line.item_name != "MUTATED-CURRENT-NAME"
    assert line.actual_uom_name != "MUTATED-CURRENT-UOM"
    assert line.item_sku is None

async def test_inbound_commit_rejects_uom_that_belongs_to_other_item(session):
    picked = await _pick_seed_item_uom(session)

    other_row = (
        await session.execute(
            text(
                """
                SELECT u.id AS uom_id
                  FROM item_uoms u
                 WHERE u.item_id <> :item_id
                 ORDER BY u.id ASC
                 LIMIT 1
                """
            ),
            {"item_id": int(picked["item_id"])},
        )
    ).mappings().first()
    assert other_row is not None, "expected another seeded item_uom"

    payload = InboundCommitIn.model_validate(
        {
            "warehouse_id": int(picked["warehouse_id"]),
            "source_type": "MANUAL",
            "source_ref": None,
            "occurred_at": date.today().isoformat() + "T00:00:00Z",
            "remark": "ut inbound commit uom mismatch",
            "lines": [
                {
                    "item_id": int(picked["item_id"]),
                    "uom_id": int(other_row["uom_id"]),
                    "qty_input": 1,
                    "lot_code_input": None,
                    "production_date": None,
                    "expiry_date": None,
                    "remark": "uom mismatch",
                }
            ],
        }
    )

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await commit_inbound(session, payload=payload, user_id=None)

    assert exc_info.value.status_code == 400
    assert "uom_id 不存在或不属于该商品" in str(exc_info.value.detail)
