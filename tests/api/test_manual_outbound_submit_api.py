from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.stock.services.lots import ensure_internal_lot_singleton, ensure_lot_full
from app.wms.stock.services.stock_adjust import adjust_lot_impl
from tests.helpers.procurement_pms_projection import install_procurement_pms_projection_fake


pytestmark = pytest.mark.asyncio
UTC = timezone.utc


async def _login_admin_headers(client: AsyncClient) -> dict[str, str]:
    r = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _pick_any_item_and_uom(session: AsyncSession) -> tuple[int, int, str, str | None, bool]:
    install_procurement_pms_projection_fake(session)

    row = (
        await session.execute(
            text(
                """
                SELECT
                  i.item_id AS item_id,
                  iu.item_uom_id AS item_uom_id,
                  COALESCE(iu.display_name, iu.uom) AS uom_name,
                  i.spec AS item_spec,
                  i.expiry_policy AS expiry_policy
                FROM wms_pms_item_projection i
                JOIN wms_pms_uom_projection iu
                  ON iu.item_id = i.item_id
                ORDER BY
                  CASE WHEN COALESCE(i.expiry_policy, 'NONE') = 'NONE' THEN 0 ELSE 1 END,
                  iu.is_outbound_default DESC,
                  iu.is_base DESC,
                  i.item_id ASC,
                  iu.item_uom_id ASC
                LIMIT 1
                """
            )
        )
    ).mappings().first()
    assert row is not None
    return (
        int(row["item_id"]),
        int(row["item_uom_id"]),
        str(row["uom_name"]),
        row["item_spec"],
        str(row["expiry_policy"]).strip().upper() == "REQUIRED",
    )


async def _ensure_warehouse(session: AsyncSession, warehouse_id: int = 1) -> int:
    await session.execute(
        text(
            """
            INSERT INTO warehouses (id, name)
            VALUES (:id, :name)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": int(warehouse_id), "name": f"WH-{warehouse_id}"},
    )
    await session.commit()
    return int(warehouse_id)


async def _seed_manual_doc_and_stock(
    session: AsyncSession,
    *,
    requested_qty: int = 2,
) -> tuple[int, int, int, int, int]:
    install_procurement_pms_projection_fake(session)

    warehouse_id = await _ensure_warehouse(session, 1)
    item_id, item_uom_id, uom_name, item_spec, requires_expiry = await _pick_any_item_and_uom(session)
    uniq = uuid4().hex[:10]

    row = await session.execute(
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
              created_at
            )
            VALUES (
              :warehouse_id,
              :doc_no,
              'MANUAL_OUTBOUND',
              'RELEASED',
              :recipient_name,
              :receiver_phone,
              :receiver_province,
              :receiver_city,
              :receiver_district,
              :receiver_address,
              :receiver_postcode,
              '整单备注',
              now()
            )
            RETURNING id
            """
        ),
        {
            "warehouse_id": int(warehouse_id),
            "doc_no": f"MOB-UT-{uniq}",
            "recipient_name": f"张三-{uniq}",
            "receiver_phone": "13800000000",
            "receiver_province": "浙江省",
            "receiver_city": "杭州市",
            "receiver_district": "余杭区",
            "receiver_address": "测试路 1 号",
            "receiver_postcode": "310000",
        },
    )
    doc_id = int(row.scalar_one())

    row2 = await session.execute(
        text(
            """
            INSERT INTO manual_outbound_lines (
              doc_id,
              line_no,
              item_id,
              item_uom_id,
              requested_qty,
              item_name_snapshot,
              item_spec_snapshot,
              uom_name_snapshot
            )
            VALUES (
              :doc_id,
              1,
              :item_id,
              :item_uom_id,
              :requested_qty,
              '测试商品',
              :item_spec_snapshot,
              :uom_name_snapshot
            )
            RETURNING id
            """
        ),
        {
            "doc_id": int(doc_id),
            "item_id": int(item_id),
            "item_uom_id": int(item_uom_id),
            "requested_qty": int(requested_qty),
            "item_spec_snapshot": item_spec,
            "uom_name_snapshot": uom_name,
        },
    )
    doc_line_id = int(row2.scalar_one())

    batch_code: str | None = None
    production_date: date | None = None
    expiry_date: date | None = None

    if requires_expiry:
        batch_code = f"UT-MAN-{warehouse_id}-{item_id}-{uniq}"
        production_date = date(2030, 1, 1)
        expiry_date = production_date + timedelta(days=365)
        lot_id = await ensure_lot_full(
            session,
            item_id=int(item_id),
            warehouse_id=int(warehouse_id),
            lot_code=batch_code,
            production_date=production_date,
            expiry_date=expiry_date,
        )
    else:
        lot_id = await ensure_internal_lot_singleton(
            session,
            item_id=int(item_id),
            warehouse_id=int(warehouse_id),
            source_receipt_id=None,
            source_line_no=None,
        )

    await adjust_lot_impl(
        session=session,
        item_id=int(item_id),
        warehouse_id=int(warehouse_id),
        lot_id=int(lot_id),
        delta=10,
        reason="UT_MANUAL_OUTBOUND_API_SEED",
        ref=f"ut:manual_outbound_api_seed:{uniq}",
        ref_line=1,
        occurred_at=datetime.now(UTC),
        meta=None,
        lot_code=batch_code,
        production_date=production_date,
        expiry_date=expiry_date,
        trace_id=None,
        utc_now=lambda: datetime.now(UTC),
    )

    await session.commit()
    return doc_id, doc_line_id, warehouse_id, int(lot_id), int(item_id)


async def test_manual_outbound_submit_writes_event_and_ledger(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    doc_id, doc_line_id, warehouse_id, lot_id, item_id = await _seed_manual_doc_and_stock(session)

    resp = await client.post(
        f"/wms/outbound/manual/{doc_id}/submit",
        headers=headers,
        json={
            "remark": "UT manual outbound submit",
            "lines": [
                {
                    "manual_doc_line_id": doc_line_id,
                    "item_id": item_id,
                    "qty_outbound": 2,
                    "lot_id": lot_id,
                    "remark": "line remark",
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["status"] == "OK"
    assert data["event_type"] == "OUTBOUND"
    assert data["source_type"] == "MANUAL"
    assert data["warehouse_id"] == warehouse_id
    assert data["lines_count"] == 1
    event_id = int(data["event_id"])

    ev = (
        await session.execute(
            text(
                """
                SELECT event_type, source_type, warehouse_id
                FROM wms_events
                WHERE id = :id
                LIMIT 1
                """
            ),
            {"id": event_id},
        )
    ).first()
    assert ev is not None
    assert ev[0] == "OUTBOUND"
    assert ev[1] == "MANUAL"
    assert int(ev[2]) == warehouse_id

    line = (
        await session.execute(
            text(
                """
                SELECT manual_doc_line_id, item_id, qty_outbound, lot_id, lot_code_snapshot
                FROM outbound_event_lines
                WHERE event_id = :event_id
                ORDER BY ref_line ASC
                LIMIT 1
                """
            ),
            {"event_id": event_id},
        )
    ).first()
    assert line is not None
    assert int(line[0]) == doc_line_id
    assert int(line[1]) == item_id
    assert int(line[2]) == 2
    assert int(line[3]) == lot_id
    expected_lot_code = (
        await session.execute(
            text("SELECT lot_code FROM lots WHERE id = :lot_id"),
            {"lot_id": int(lot_id)},
        )
    ).scalar_one()
    assert line[4] == expected_lot_code

    led = (
        await session.execute(
            text(
                """
                SELECT reason, delta, warehouse_id, item_id, lot_id, event_id
                FROM stock_ledger
                WHERE event_id = :event_id
                ORDER BY id ASC
                LIMIT 1
                """
            ),
            {"event_id": event_id},
        )
    ).first()
    assert led is not None
    assert led[0] == "OUTBOUND_SHIP"
    assert int(led[1]) == -2
    assert int(led[2]) == warehouse_id
    assert int(led[3]) == item_id
    assert int(led[4]) == lot_id
    assert int(led[5]) == event_id

    qty_now = (
        await session.execute(
            text(
                """
                SELECT qty
                FROM stocks_lot
                WHERE warehouse_id = :w
                  AND item_id = :i
                  AND lot_id = :l
                LIMIT 1
                """
            ),
            {"w": warehouse_id, "i": item_id, "l": lot_id},
        )
    ).scalar_one()
    assert int(qty_now) == 8

    doc_status = (
        await session.execute(
            text(
                """
                SELECT status
                FROM manual_outbound_docs
                WHERE id = :doc_id
                LIMIT 1
                """
            ),
            {"doc_id": doc_id},
        )
    ).scalar_one()
    assert str(doc_status) == "COMPLETED"

    export_record = (
        await session.execute(
            text(
                """
                SELECT
                  r.source_doc_type,
                  r.source_doc_id,
                  r.source_doc_no,
                  r.source_ref,
                  r.export_status,
                  r.logistics_status,
                  p.outbound_event_id,
                  p.outbound_source_ref,
                  p.warehouse_id AS payload_warehouse_id,
                  p.receiver_phone,
                  p.receiver_province,
                  p.receiver_city,
                  p.receiver_district,
                  p.receiver_address,
                  p.receiver_postcode,
                  p.shipment_items
                FROM wms_logistics_export_records r
                JOIN wms_logistics_handoff_payloads p
                  ON p.export_record_id = r.id
                WHERE r.source_ref = :source_ref
                LIMIT 1
                """
            ),
            {"source_ref": f"WMS:MANUAL_OUTBOUND:{doc_id}"},
        )
    ).mappings().first()

    assert export_record is not None
    assert export_record["source_doc_type"] == "MANUAL_OUTBOUND"
    assert int(export_record["source_doc_id"]) == int(doc_id)
    assert str(export_record["source_doc_no"]).startswith("MOB-UT-")
    assert export_record["source_ref"] == f"WMS:MANUAL_OUTBOUND:{doc_id}"
    assert export_record["export_status"] == "PENDING"
    assert export_record["logistics_status"] == "NOT_IMPORTED"
    assert int(export_record["outbound_event_id"]) == event_id
    assert export_record["outbound_source_ref"] == data["source_ref"]
    assert int(export_record["payload_warehouse_id"]) == warehouse_id
    assert export_record["receiver_phone"] == "13800000000"
    assert export_record["receiver_province"] == "浙江省"
    assert export_record["receiver_city"] == "杭州市"
    assert export_record["receiver_district"] == "余杭区"
    assert export_record["receiver_address"] == "测试路 1 号"
    assert export_record["receiver_postcode"] == "310000"

    shipment_items = export_record["shipment_items"]
    assert isinstance(shipment_items, list)
    assert len(shipment_items) == 1
    assert shipment_items[0]["source_line_type"] == "MANUAL_OUTBOUND_LINE"
    assert int(shipment_items[0]["source_line_id"]) == doc_line_id
    assert int(shipment_items[0]["item_id"]) == item_id
    assert int(shipment_items[0]["qty_outbound"]) == 2


async def test_manual_outbound_submit_keeps_doc_released_when_partially_submitted(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    doc_id, doc_line_id, warehouse_id, lot_id, item_id = await _seed_manual_doc_and_stock(
        session,
        requested_qty=5,
    )

    resp = await client.post(
        f"/wms/outbound/manual/{doc_id}/submit",
        headers=headers,
        json={
            "remark": "UT manual outbound partial submit",
            "lines": [
                {
                    "manual_doc_line_id": doc_line_id,
                    "item_id": item_id,
                    "qty_outbound": 2,
                    "lot_id": lot_id,
                    "remark": "partial line remark",
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["status"] == "OK"
    assert data["source_type"] == "MANUAL"
    assert data["warehouse_id"] == warehouse_id
    assert data["lines_count"] == 1

    doc_status = (
        await session.execute(
            text(
                """
                SELECT status
                FROM manual_outbound_docs
                WHERE id = :doc_id
                LIMIT 1
                """
            ),
            {"doc_id": doc_id},
        )
    ).scalar_one()
    assert str(doc_status) == "RELEASED"

    export_count = (
        await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM wms_logistics_export_records
                WHERE source_ref = :source_ref
                """
            ),
            {"source_ref": f"WMS:MANUAL_OUTBOUND:{doc_id}"},
        )
    ).scalar_one()
    assert int(export_count) == 0


async def test_manual_outbound_submit_rejects_lot_code_and_batch_code_extras(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    doc_id, doc_line_id, _warehouse_id, lot_id, item_id = await _seed_manual_doc_and_stock(session)

    resp = await client.post(
        f"/wms/outbound/manual/{doc_id}/submit",
        headers=headers,
        json={
            "remark": "UT manual outbound submit rejects extras",
            "lines": [
                {
                    "manual_doc_line_id": doc_line_id,
                    "item_id": item_id,
                    "qty_outbound": 1,
                    "lot_id": lot_id,
                    "lot_code": "SHOULD-NOT-BE-ACCEPTED",
                    "batch_code": "SHOULD-NOT-BE-ACCEPTED",
                    "remark": "line remark",
                }
            ],
        },
    )

    assert resp.status_code == 422, resp.text
    body = resp.text
    assert "Extra inputs are not permitted" in body
