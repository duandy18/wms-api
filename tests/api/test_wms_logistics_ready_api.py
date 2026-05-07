from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.services._helpers import ensure_store

pytestmark = pytest.mark.asyncio
UTC = timezone.utc


async def _login_admin_headers(client: AsyncClient) -> dict[str, str]:
    r = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _pick_any_item_id(session: AsyncSession) -> int:
    row = await session.execute(text("SELECT id FROM items ORDER BY id ASC LIMIT 1"))
    item_id = row.scalar_one_or_none()
    assert item_id is not None
    return int(item_id)


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
    return int(warehouse_id)


async def _insert_export_record(
    session: AsyncSession,
    *,
    source_doc_type: str,
    source_doc_id: int,
    source_doc_no: str,
    source_ref: str,
    export_status: str,
    logistics_status: str = "NOT_IMPORTED",
) -> int:
    now = datetime.now(UTC)
    return int(
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
                      :now,
                      :now
                    )
                    RETURNING id
                    """
                ),
                {
                    "source_doc_type": source_doc_type,
                    "source_doc_id": int(source_doc_id),
                    "source_doc_no": source_doc_no,
                    "source_ref": source_ref,
                    "export_status": export_status,
                    "logistics_status": logistics_status,
                    "now": now,
                },
            )
        ).scalar_one()
    )


async def _seed_order_ready_record(
    session: AsyncSession,
    *,
    export_status: str = "PENDING",
) -> tuple[int, str]:
    now = datetime.now(UTC)
    uniq = uuid4().hex[:10]
    platform = "PDD"
    store_code = "UT-READY"
    ext_order_no = f"READY-ORD-{uniq}"
    warehouse_id = await _ensure_warehouse(session, 1)
    item_id = await _pick_any_item_id(session)

    store_id = await ensure_store(
        session,
        platform=platform,
        store_code=store_code,
        name=f"UT-{platform}-{store_code}",
    )

    order_id = int(
        (
            await session.execute(
                text(
                    """
                    INSERT INTO orders (
                      platform,
                      store_code,
                      store_id,
                      ext_order_no,
                      status,
                      created_at,
                      updated_at
                    )
                    VALUES (
                      :platform,
                      :store_code,
                      :store_id,
                      :ext_order_no,
                      'CREATED',
                      :now,
                      :now
                    )
                    RETURNING id
                    """
                ),
                {
                    "platform": platform,
                    "store_code": store_code,
                    "store_id": int(store_id),
                    "ext_order_no": ext_order_no,
                    "now": now,
                },
            )
        ).scalar_one()
    )

    await session.execute(
        text(
            """
            INSERT INTO order_address (
              order_id,
              receiver_name,
              receiver_phone,
              province,
              city,
              district,
              detail,
              created_at
            )
            VALUES (
              :order_id,
              '张三',
              '13800000000',
              '浙江省',
              '杭州市',
              '余杭区',
              '测试路 1 号',
              :now
            )
            """
        ),
        {"order_id": int(order_id), "now": now},
    )

    await session.execute(
        text(
            """
            INSERT INTO order_fulfillment (
              order_id,
              actual_warehouse_id,
              execution_stage,
              outbound_committed_at,
              outbound_completed_at,
              updated_at
            )
            VALUES (
              :order_id,
              :warehouse_id,
              'SHIP',
              :now,
              :now,
              :now
            )
            """
        ),
        {"order_id": int(order_id), "warehouse_id": int(warehouse_id), "now": now},
    )

    source_ref = f"WMS:ORDER_OUTBOUND:{order_id}"
    export_record_id = await _insert_export_record(
        session,
        source_doc_type="ORDER_OUTBOUND",
        source_doc_id=int(order_id),
        source_doc_no=ext_order_no,
        source_ref=source_ref,
        export_status=export_status,
    )

    shipment_items = [
        {
            "source_line_type": "ORDER_LINE",
            "source_line_id": 9001,
            "source_line_no": 1,
            "item_id": item_id,
            "item_sku_snapshot": "SKU-READY",
            "item_name_snapshot": "测试商品",
            "item_spec_snapshot": "1kg",
            "qty_outbound": 2,
        }
    ]

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
              outbound_event_id,
              outbound_source_ref,
              outbound_completed_at,
              shipment_items,
              created_at,
              updated_at
            )
            VALUES (
              :export_record_id,
              'ORDER_OUTBOUND',
              :source_doc_id,
              :source_doc_no,
              :source_ref,
              :platform,
              :store_code,
              :order_ref,
              :ext_order_no,
              :warehouse_id,
              :warehouse_name_snapshot,
              '张三',
              '13800000000',
              '浙江省',
              '杭州市',
              '余杭区',
              '测试路 1 号',
              9001,
              :outbound_source_ref,
              :now,
              CAST(:shipment_items AS jsonb),
              :now,
              :now
            )
            """
        ),
        {
            "export_record_id": export_record_id,
            "source_doc_id": int(order_id),
            "source_doc_no": ext_order_no,
            "source_ref": source_ref,
            "platform": platform,
            "store_code": store_code,
            "order_ref": f"ORD:{platform}:{store_code}:{ext_order_no}",
            "ext_order_no": ext_order_no,
            "warehouse_id": int(warehouse_id),
            "warehouse_name_snapshot": f"WH-{warehouse_id}",
            "outbound_source_ref": f"ORD:{platform}:{store_code}:{ext_order_no}",
            "shipment_items": json.dumps(shipment_items, ensure_ascii=False),
            "now": now,
        },
    )

    await session.commit()
    return order_id, source_ref


async def _seed_manual_ready_record(
    session: AsyncSession,
    *,
    export_status: str = "FAILED",
) -> tuple[int, str]:
    now = datetime.now(UTC)
    uniq = uuid4().hex[:10]
    warehouse_id = await _ensure_warehouse(session, 1)
    item_id = await _pick_any_item_id(session)
    doc_no = f"MOB-READY-{uniq}"

    doc_id = int(
        (
            await session.execute(
                text(
                    """
                    INSERT INTO manual_outbound_docs (
                      warehouse_id,
                      doc_no,
                      doc_type,
                      status,
                      recipient_name,
                      remark,
                      created_at
                    )
                    VALUES (
                      :warehouse_id,
                      :doc_no,
                      'MANUAL_OUTBOUND',
                      'COMPLETED',
                      '李四',
                      'ready api test',
                      :now
                    )
                    RETURNING id
                    """
                ),
                {"warehouse_id": int(warehouse_id), "doc_no": doc_no, "now": now},
            )
        ).scalar_one()
    )

    source_ref = f"WMS:MANUAL_OUTBOUND:{doc_id}"
    export_record_id = await _insert_export_record(
        session,
        source_doc_type="MANUAL_OUTBOUND",
        source_doc_id=int(doc_id),
        source_doc_no=doc_no,
        source_ref=source_ref,
        export_status=export_status,
    )

    shipment_items = [
        {
            "source_line_type": "MANUAL_OUTBOUND_LINE",
            "source_line_id": 9002,
            "source_line_no": 1,
            "item_id": item_id,
            "item_sku_snapshot": "SKU-MAN",
            "item_name_snapshot": "手工商品",
            "item_spec_snapshot": "500g",
            "qty_outbound": 1,
        }
    ]

    await session.execute(
        text(
            """
            INSERT INTO wms_logistics_handoff_payloads (
              export_record_id,
              source_doc_type,
              source_doc_id,
              source_doc_no,
              source_ref,
              warehouse_id,
              warehouse_name_snapshot,
              receiver_name,
              receiver_phone,
              receiver_province,
              receiver_city,
              receiver_district,
              receiver_address,
              receiver_postcode,
              outbound_event_id,
              outbound_source_ref,
              outbound_completed_at,
              shipment_items,
              created_at,
              updated_at
            )
            VALUES (
              :export_record_id,
              'MANUAL_OUTBOUND',
              :source_doc_id,
              :source_doc_no,
              :source_ref,
              :warehouse_id,
              :warehouse_name_snapshot,
              '李四',
              '13900000000',
              '浙江省',
              '杭州市',
              '西湖区',
              '手工测试路 2 号',
              '310000',
              9002,
              :outbound_source_ref,
              :now,
              CAST(:shipment_items AS jsonb),
              :now,
              :now
            )
            """
        ),
        {
            "export_record_id": export_record_id,
            "source_doc_id": int(doc_id),
            "source_doc_no": doc_no,
            "source_ref": source_ref,
            "warehouse_id": int(warehouse_id),
            "warehouse_name_snapshot": f"WH-{warehouse_id}",
            "outbound_source_ref": doc_no,
            "shipment_items": json.dumps(shipment_items, ensure_ascii=False),
            "now": now,
        },
    )

    await session.commit()
    return doc_id, source_ref


async def _seed_exported_record(session: AsyncSession) -> str:
    now = datetime.now(UTC)
    uniq = uuid4().hex[:10]
    source_ref = f"WMS:ORDER_OUTBOUND:EXPORTED:{uniq}"
    source_doc_no = f"EXPORTED-{uniq}"

    export_record_id = await _insert_export_record(
        session,
        source_doc_type="ORDER_OUTBOUND",
        source_doc_id=900000000,
        source_doc_no=source_doc_no,
        source_ref=source_ref,
        export_status="EXPORTED",
        logistics_status="IMPORTED",
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
              outbound_event_id,
              shipment_items,
              created_at,
              updated_at
            )
            VALUES (
              :export_record_id,
              'ORDER_OUTBOUND',
              900000000,
              :source_doc_no,
              :source_ref,
              9003,
              '[]'::jsonb,
              :now,
              :now
            )
            """
        ),
        {
            "export_record_id": export_record_id,
            "source_doc_no": source_doc_no,
            "source_ref": source_ref,
            "now": now,
        },
    )

    await session.commit()
    return source_ref


async def _seed_unimportable_ready_record(session: AsyncSession) -> str:
    now = datetime.now(UTC)
    uniq = uuid4().hex[:10]
    source_ref = f"WMS:ORDER_OUTBOUND:DIRTY:{uniq}"
    source_doc_id = int(int(uuid4().int % 900000000) + 1000)
    source_doc_no = f"DIRTY-READY-{uniq}"

    export_record_id = await _insert_export_record(
        session,
        source_doc_type="ORDER_OUTBOUND",
        source_doc_id=source_doc_id,
        source_doc_no=source_doc_no,
        source_ref=source_ref,
        export_status="PENDING",
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
              shipment_items,
              created_at,
              updated_at
            )
            VALUES (
              :export_record_id,
              'ORDER_OUTBOUND',
              :source_doc_id,
              :source_doc_no,
              :source_ref,
              '[]'::jsonb,
              :now,
              :now
            )
            """
        ),
        {
            "export_record_id": export_record_id,
            "source_doc_id": source_doc_id,
            "source_doc_no": source_doc_no,
            "source_ref": source_ref,
            "now": now,
        },
    )

    await session.commit()
    return source_ref


async def test_logistics_ready_returns_pending_and_failed_records(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    _order_id, order_ref = await _seed_order_ready_record(session, export_status="PENDING")
    _doc_id, manual_ref = await _seed_manual_ready_record(session, export_status="FAILED")
    exported_ref = await _seed_exported_record(session)
    dirty_ref = await _seed_unimportable_ready_record(session)

    resp = await client.get("/wms/outbound/logistics-ready", headers=headers)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["total"] == 2

    refs = {row["source_ref"] for row in data["rows"]}
    assert order_ref in refs
    assert manual_ref in refs
    assert exported_ref not in refs
    assert dirty_ref not in refs

    order_row = next(row for row in data["rows"] if row["source_ref"] == order_ref)
    assert order_row["source_system"] == "WMS"
    assert order_row["request_source"] == "API_IMPORT"
    assert order_row["source_doc_type"] == "ORDER_OUTBOUND"
    assert order_row["platform"] == "PDD"
    assert order_row["store_code"] == "UT-READY"
    assert order_row["receiver_name"] == "张三"
    assert order_row["receiver_phone"] == "13800000000"
    assert order_row["receiver_province"] == "浙江省"
    assert order_row["receiver_city"] == "杭州市"
    assert order_row["receiver_district"] == "余杭区"
    assert order_row["receiver_address"] == "测试路 1 号"
    assert order_row["outbound_event_id"] == 9001
    assert order_row["shipment_items"][0]["qty_outbound"] == 2
    forbidden_response_keys = {"packages", "source_" + "snapshot"}
    assert set(order_row).isdisjoint(forbidden_response_keys)

    manual_row = next(row for row in data["rows"] if row["source_ref"] == manual_ref)
    assert manual_row["source_doc_type"] == "MANUAL_OUTBOUND"
    assert manual_row["export_status"] == "FAILED"
    assert manual_row["receiver_name"] == "李四"
    assert manual_row["receiver_phone"] == "13900000000"
    assert manual_row["receiver_province"] == "浙江省"
    assert manual_row["receiver_city"] == "杭州市"
    assert manual_row["receiver_district"] == "西湖区"
    assert manual_row["receiver_address"] == "手工测试路 2 号"
    assert manual_row["receiver_postcode"] == "310000"
    assert manual_row["platform"] is None
    assert manual_row["outbound_event_id"] == 9002
    assert manual_row["shipment_items"][0]["qty_outbound"] == 1


async def test_logistics_ready_filters_source_doc_type_and_export_status(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    await _seed_order_ready_record(session, export_status="PENDING")
    _doc_id, manual_ref = await _seed_manual_ready_record(session, export_status="FAILED")

    resp = await client.get(
        "/wms/outbound/logistics-ready",
        headers=headers,
        params={
            "source_doc_type": "MANUAL_OUTBOUND",
            "export_status": "FAILED",
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert len(data["rows"]) == 1
    assert data["rows"][0]["source_ref"] == manual_ref
    assert data["rows"][0]["source_doc_type"] == "MANUAL_OUTBOUND"
    assert data["rows"][0]["export_status"] == "FAILED"


async def test_logistics_ready_rejects_invalid_filters(
    client: AsyncClient,
) -> None:
    headers = await _login_admin_headers(client)

    bad_type = await client.get(
        "/wms/outbound/logistics-ready",
        headers=headers,
        params={"source_doc_type": "ERP_OUTBOUND"},
    )
    assert bad_type.status_code == 422

    bad_status = await client.get(
        "/wms/outbound/logistics-ready",
        headers=headers,
        params={"export_status": "EXPORTED"},
    )
    assert bad_status.status_code == 422
