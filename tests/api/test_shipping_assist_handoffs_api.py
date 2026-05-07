from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio
UTC = timezone.utc


async def _login_headers(client: AsyncClient) -> dict[str, str]:
    resp = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _seed_handoff(
    session: AsyncSession,
    *,
    source_doc_type: str = "ORDER_OUTBOUND",
    source_doc_no: str | None = None,
    export_status: str = "PENDING",
    logistics_status: str = "NOT_IMPORTED",
    logistics_request_id: int | None = None,
    logistics_request_no: str | None = None,
    last_error: str | None = None,
) -> str:
    uniq = uuid4().hex[:10].upper()
    source_doc_id = int(uuid4().int % 900_000_000) + 1000
    doc_no = source_doc_no or f"HANDOFF-{uniq}"
    source_ref = f"WMS:{source_doc_type}:{source_doc_id}"
    now = datetime.now(UTC)

    exported_at = now if export_status == "EXPORTED" else None
    logistics_completed_at = now if logistics_status == "COMPLETED" else None

    export_record_id = int(
        (
            await session.execute(
                text(
                    """
                    INSERT INTO wms_logistics_export_records (
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
                      created_at,
                      updated_at
                    )
                    VALUES (
                      :source_doc_type,
                      :source_doc_id,
                      :source_doc_no,
                      :source_ref,
                      :export_status,
                      :logistics_status,
                      :logistics_request_id,
                      :logistics_request_no,
                      :exported_at,
                      :logistics_completed_at,
                      :now,
                      :last_error,
                      :now,
                      :now
                    )
                    RETURNING id
                    """
                ),
                {
                    "source_doc_type": source_doc_type,
                    "source_doc_id": source_doc_id,
                    "source_doc_no": doc_no,
                    "source_ref": source_ref,
                    "export_status": export_status,
                    "logistics_status": logistics_status,
                    "logistics_request_id": logistics_request_id,
                    "logistics_request_no": logistics_request_no,
                    "exported_at": exported_at,
                    "logistics_completed_at": logistics_completed_at,
                    "last_error": last_error,
                    "now": now,
                },
            )
        ).scalar_one()
    )

    await session.execute(
        text(
            """
            INSERT INTO wms_logistics_handoff_payloads (
              export_record_id,
              source_doc_type,
              source_doc_id,
              source_doc_no,
              source_ref,
              platform,
              store_code,
              order_ref,
              ext_order_no,
              warehouse_id,
              warehouse_name_snapshot,
              receiver_name,
              receiver_phone,
              receiver_province,
              receiver_city,
              receiver_district,
              receiver_address,
              outbound_completed_at,
              shipment_items,
              created_at,
              updated_at
            )
            VALUES (
              :export_record_id,
              :source_doc_type,
              :source_doc_id,
              :source_doc_no,
              :source_ref,
              :platform,
              :store_code,
              :order_ref,
              :ext_order_no,
              1,
              'UT-HANDOFF-WH',
              '张三',
              '13800000000',
              '浙江省',
              '杭州市',
              '余杭区',
              '测试路 1 号',
              :now,
              CAST(:shipment_items AS jsonb),
              :now,
              :now
            )
            """
        ),
        {
            "export_record_id": export_record_id,
            "source_doc_type": source_doc_type,
            "source_doc_id": source_doc_id,
            "source_doc_no": doc_no,
            "source_ref": source_ref,
            "platform": "PDD" if source_doc_type == "ORDER_OUTBOUND" else None,
            "store_code": "UT-HANDOFF" if source_doc_type == "ORDER_OUTBOUND" else None,
            "order_ref": f"ORD:PDD:UT-HANDOFF:{doc_no}"
            if source_doc_type == "ORDER_OUTBOUND"
            else None,
            "ext_order_no": doc_no if source_doc_type == "ORDER_OUTBOUND" else None,
            "shipment_items": json.dumps(
                [
                    {
                        "source_line_type": "ORDER_LINE"
                        if source_doc_type == "ORDER_OUTBOUND"
                        else "MANUAL_OUTBOUND_LINE",
                        "source_line_id": 1,
                        "source_line_no": 1,
                        "item_id": 1,
                        "item_sku_snapshot": "SKU-HANDOFF",
                        "item_name_snapshot": "交接测试商品",
                        "item_spec_snapshot": "1kg",
                        "qty_outbound": 1,
                    }
                ],
                ensure_ascii=False,
            ),
            "now": now,
        },
    )
    await session.commit()
    return source_ref


async def test_shipping_assist_handoffs_lists_records(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_headers(client)
    pending_ref = await _seed_handoff(session, export_status="PENDING")
    completed_ref = await _seed_handoff(
        session,
        export_status="EXPORTED",
        logistics_status="COMPLETED",
        logistics_request_id=8801,
        logistics_request_no="LSR-HANDOFF-0001",
    )

    resp = await client.get("/shipping-assist/handoffs", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["total"] == 2

    refs = {row["source_ref"] for row in body["rows"]}
    assert pending_ref in refs
    assert completed_ref in refs

    completed = next(row for row in body["rows"] if row["source_ref"] == completed_ref)
    assert completed["export_status"] == "EXPORTED"
    assert completed["logistics_status"] == "COMPLETED"
    assert completed["logistics_request_no"] == "LSR-HANDOFF-0001"
    assert completed["receiver_city"] == "杭州市"
    assert completed["shipment_items"][0]["item_name_snapshot"] == "交接测试商品"


async def test_shipping_assist_handoffs_filters_by_status_and_source(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_headers(client)
    await _seed_handoff(session, source_doc_type="ORDER_OUTBOUND", export_status="PENDING")
    manual_ref = await _seed_handoff(
        session,
        source_doc_type="MANUAL_OUTBOUND",
        source_doc_no="MANUAL-HANDOFF-FAILED",
        export_status="FAILED",
        logistics_status="FAILED",
        last_error="receiver phone missing",
    )

    resp = await client.get(
        "/shipping-assist/handoffs",
        headers=headers,
        params={
            "source_doc_type": "MANUAL_OUTBOUND",
            "export_status": "FAILED",
            "logistics_status": "FAILED",
            "source_doc_no": "HANDOFF-FAILED",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["rows"][0]["source_ref"] == manual_ref
    assert body["rows"][0]["last_error"] == "receiver phone missing"


async def test_shipping_assist_handoffs_filters_by_request_no(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_headers(client)
    await _seed_handoff(
        session,
        export_status="EXPORTED",
        logistics_status="IMPORTED",
        logistics_request_id=8801,
        logistics_request_no="LSR-HANDOFF-A",
    )
    target_ref = await _seed_handoff(
        session,
        export_status="EXPORTED",
        logistics_status="COMPLETED",
        logistics_request_id=8802,
        logistics_request_no="LSR-HANDOFF-B",
    )

    resp = await client.get(
        "/shipping-assist/handoffs",
        headers=headers,
        params={"logistics_request_no": "LSR-HANDOFF-B"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["rows"][0]["source_ref"] == target_ref
    assert body["rows"][0]["logistics_request_id"] == 8802


async def test_shipping_assist_handoffs_rejects_invalid_filters(
    client: AsyncClient,
) -> None:
    headers = await _login_headers(client)

    bad_source = await client.get(
        "/shipping-assist/handoffs",
        headers=headers,
        params={"source_doc_type": "ERP_OUTBOUND"},
    )
    assert bad_source.status_code == 422

    bad_export = await client.get(
        "/shipping-assist/handoffs",
        headers=headers,
        params={"export_status": "READY"},
    )
    assert bad_export.status_code == 422

    bad_logistics = await client.get(
        "/shipping-assist/handoffs",
        headers=headers,
        params={"logistics_status": "DONE"},
    )
    assert bad_logistics.status_code == 422
