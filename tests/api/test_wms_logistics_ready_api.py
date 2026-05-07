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
    source_snapshot = {
        "warehouse_id": warehouse_id,
        "occurred_at": now.isoformat(),
        "wms_event_id": 9001,
        "wms_source_ref": f"ORD:{platform}:{store_code}:{ext_order_no}",
        "lines": [
            {
                "ref_line": 1,
                "item_id": item_id,
                "qty_outbound": 2,
                "lot_id": 1,
                "lot_code_snapshot": "UT-LOT",
                "item_name_snapshot": "测试商品",
                "item_sku_snapshot": "SKU-READY",
                "item_spec_snapshot": "1kg",
            }
        ],
    }

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
              source_snapshot,
              created_at,
              updated_at
            )
            VALUES (
              'ORDER_OUTBOUND',
              :source_doc_id,
              :source_doc_no,
              :source_ref,
              :export_status,
              'NOT_IMPORTED',
              CAST(:source_snapshot AS jsonb),
              :now,
              :now
            )
            """
        ),
        {
            "source_doc_id": int(order_id),
            "source_doc_no": ext_order_no,
            "source_ref": source_ref,
            "export_status": export_status,
            "source_snapshot": json.dumps(source_snapshot, ensure_ascii=False),
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
    source_snapshot = {
        "warehouse_id": warehouse_id,
        "occurred_at": now.isoformat(),
        "wms_event_id": 9002,
        "wms_source_ref": doc_no,
        "lines": [
            {
                "ref_line": 1,
                "item_id": item_id,
                "qty_outbound": 1,
                "lot_id": 1,
                "lot_code_snapshot": "UT-MAN-LOT",
                "item_name_snapshot": "手工商品",
                "item_sku_snapshot": "SKU-MAN",
                "item_spec_snapshot": "500g",
            }
        ],
    }

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
              source_snapshot,
              created_at,
              updated_at
            )
            VALUES (
              'MANUAL_OUTBOUND',
              :source_doc_id,
              :source_doc_no,
              :source_ref,
              :export_status,
              'NOT_IMPORTED',
              CAST(:source_snapshot AS jsonb),
              :now,
              :now
            )
            """
        ),
        {
            "source_doc_id": int(doc_id),
            "source_doc_no": doc_no,
            "source_ref": source_ref,
            "export_status": export_status,
            "source_snapshot": json.dumps(source_snapshot, ensure_ascii=False),
            "now": now,
        },
    )

    await session.commit()
    return doc_id, source_ref


async def _seed_exported_record(session: AsyncSession) -> str:
    now = datetime.now(UTC)
    uniq = uuid4().hex[:10]
    source_ref = f"WMS:ORDER_OUTBOUND:EXPORTED:{uniq}"

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
              source_snapshot,
              created_at,
              updated_at
            )
            VALUES (
              'ORDER_OUTBOUND',
              :source_doc_id,
              :source_doc_no,
              :source_ref,
              'EXPORTED',
              'IMPORTED',
              CAST(:source_snapshot AS jsonb),
              :now,
              :now
            )
            """
        ),
        {
            "source_doc_id": 900000000,
            "source_doc_no": f"EXPORTED-{uniq}",
            "source_ref": source_ref,
            "source_snapshot": "{}",
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

    resp = await client.get("/wms/outbound/logistics-ready", headers=headers)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["total"] == 2

    refs = {row["source_ref"] for row in data["rows"]}
    assert order_ref in refs
    assert manual_ref in refs
    assert exported_ref not in refs

    order_row = next(row for row in data["rows"] if row["source_ref"] == order_ref)
    assert order_row["source_system"] == "WMS"
    assert order_row["source_doc_type"] == "ORDER_OUTBOUND"
    assert order_row["platform"] == "PDD"
    assert order_row["store_code"] == "UT-READY"
    assert order_row["receiver_name"] == "张三"
    assert order_row["receiver_phone"] == "13800000000"
    assert order_row["province"] == "浙江省"
    assert order_row["city"] == "杭州市"
    assert order_row["district"] == "余杭区"
    assert order_row["address_detail"] == "测试路 1 号"
    assert order_row["packages"][0]["source_package_ref"] == f"{order_ref}:PACKAGE:1"
    assert order_row["packages"][0]["items"][0]["qty"] == 2

    manual_row = next(row for row in data["rows"] if row["source_ref"] == manual_ref)
    assert manual_row["source_doc_type"] == "MANUAL_OUTBOUND"
    assert manual_row["export_status"] == "FAILED"
    assert manual_row["receiver_name"] == "李四"
    assert manual_row["platform"] is None
    assert manual_row["packages"][0]["items"][0]["qty"] == 1


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
