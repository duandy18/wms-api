from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.system.service_auth.deps import WMS_SERVICE_CLIENT_HEADER
from tests.services._helpers import ensure_store

pytestmark = pytest.mark.asyncio
UTC = timezone.utc


async def _login_admin_headers(client: AsyncClient) -> dict[str, str]:
    _ = client
    return {WMS_SERVICE_CLIENT_HEADER: "logistics-service"}


async def _ensure_warehouse(session: AsyncSession, warehouse_id: int = 1) -> int:
    await session.execute(
        text(
            """
            INSERT INTO warehouses (id, name, active)
            VALUES (:id, :name, TRUE)
            ON CONFLICT (id) DO UPDATE SET
              name = EXCLUDED.name,
              active = TRUE
            """
        ),
        {"id": int(warehouse_id), "name": f"WH-{warehouse_id}"},
    )
    return int(warehouse_id)


async def _ensure_provider(session: AsyncSession, *, code: str) -> int:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO shipping_providers (
                  name,
                  shipping_provider_code,
                  active,
                  priority,
                  created_at,
                  updated_at
                )
                VALUES (
                  :name,
                  :code,
                  TRUE,
                  10,
                  now(),
                  now()
                )
                ON CONFLICT (shipping_provider_code) DO UPDATE SET
                  name = EXCLUDED.name,
                  active = TRUE,
                  updated_at = now()
                RETURNING id
                """
            ),
            {"name": f"UT Provider {code}", "code": code},
        )
    ).scalar_one()
    return int(row)


async def _seed_order_exported_record(
    session: AsyncSession,
    *,
    source_ref_suffix: str | None = None,
    export_status: str = "EXPORTED",
    logistics_status: str = "IMPORTED",
    logistics_request_id: int = 701,
    logistics_request_no: str = "LSR-UT-0001",
) -> tuple[str, str, str, str]:
    now = datetime.now(UTC)
    uniq = source_ref_suffix or uuid4().hex[:10]
    platform = "PDD"
    store_code = f"SHIPREADY{uniq[:6].upper()}"
    ext_order_no = f"SHIP-ORD-{uniq}"
    warehouse_id = await _ensure_warehouse(session, 1)

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
                      created_at,
                      updated_at
                    )
                    VALUES (
                      'ORDER_OUTBOUND',
                      :source_doc_id,
                      :source_doc_no,
                      :source_ref,
                      :export_status,
                      :logistics_status,
                      :logistics_request_id,
                      :logistics_request_no,
                      :now,
                      :now
                    )
                    RETURNING id
                    """
                ),
                {
                    "source_doc_id": int(order_id),
                    "source_doc_no": ext_order_no,
                    "source_ref": source_ref,
                    "export_status": export_status,
                    "logistics_status": logistics_status,
                    "logistics_request_id": int(logistics_request_id),
                    "logistics_request_no": logistics_request_no,
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
            "shipment_items": "[]",
            "now": now,
        },
    )

    await session.commit()
    return source_ref, platform, store_code, ext_order_no


async def _load_shipping_record(
    session: AsyncSession,
    *,
    platform: str,
    store_code: str,
    order_ref: str,
    package_no: int,
) -> dict[str, object]:
    row = (
        await session.execute(
            text(
                """
                SELECT *
                FROM shipping_records
                WHERE platform = :platform
                  AND store_code = :store_code
                  AND order_ref = :order_ref
                  AND package_no = :package_no
                LIMIT 1
                """
            ),
            {
                "platform": platform,
                "store_code": store_code,
                "order_ref": order_ref,
                "package_no": int(package_no),
            },
        )
    ).mappings().first()
    assert row is not None
    return dict(row)


async def test_logistics_shipping_results_upserts_shipping_record_and_refreshes_finance(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    suffix = uuid4().hex[:8].upper()
    provider_code = f"WMSCB{suffix}"[:32]
    provider_id = await _ensure_provider(session, code=provider_code)
    source_ref, platform, store_code, ext_order_no = await _seed_order_exported_record(
        session,
        source_ref_suffix=suffix,
        logistics_request_id=701,
        logistics_request_no="LSR-UT-0001",
    )

    completed_at = datetime.now(UTC).isoformat()
    resp = await client.post(
        "/shipping-assist/handoffs/shipping-results",
        headers=headers,
        json={
            "source_ref": source_ref,
            "logistics_request_id": 701,
            "logistics_request_no": "LSR-UT-0001",
            "completed_at": completed_at,
            "packages": [
                {
                    "package_no": 1,
                    "tracking_no": f"TRACK-{suffix}",
                    "shipping_provider_code": provider_code,
                    "shipping_provider_name": "REMOTE-PROVIDER-NAME",
                    "gross_weight_kg": "1.250",
                    "freight_estimated": "10.00",
                    "surcharge_estimated": "2.50",
                    "cost_estimated": "12.50",
                    "length_cm": "10.00",
                    "width_cm": "20.00",
                    "height_cm": "30.00",
                    "sender": "联调发件人",
                    "dest_province": "浙江省",
                    "dest_city": "杭州市",
                }
            ],
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["source_ref"] == source_ref
    assert data["logistics_status"] == "COMPLETED"
    assert data["packages_count"] == 1
    assert len(data["shipping_record_ids"]) == 1

    order_ref = f"ORD:{platform}:{store_code}:{ext_order_no}"
    record = await _load_shipping_record(
        session,
        platform=platform,
        store_code=store_code,
        order_ref=order_ref,
        package_no=1,
    )
    assert int(record["shipping_provider_id"]) == provider_id
    assert record["shipping_provider_code"] == provider_code
    assert record["tracking_no"] == f"TRACK-{suffix}"
    assert float(record["cost_estimated"]) == pytest.approx(12.5)
    assert record["dest_province"] == "浙江省"
    assert record["dest_city"] == "杭州市"

    export_row = (
        await session.execute(
            text(
                """
                SELECT logistics_status, logistics_completed_at, last_error
                FROM wms_logistics_export_records
                WHERE source_ref = :source_ref
                LIMIT 1
                """
            ),
            {"source_ref": source_ref},
        )
    ).mappings().first()
    assert export_row is not None
    assert export_row["logistics_status"] == "COMPLETED"
    assert export_row["logistics_completed_at"] is not None
    assert export_row["last_error"] is None

    finance_line = (
        await session.execute(
            text(
                """
                SELECT
                  shipping_record_id,
                  shipping_provider_id,
                  tracking_no,
                  cost_estimated
                FROM finance_shipping_cost_lines
                WHERE shipping_record_id = :shipping_record_id
                LIMIT 1
                """
            ),
            {"shipping_record_id": int(record["id"])},
        )
    ).mappings().first()
    assert finance_line is not None
    assert int(finance_line["shipping_provider_id"]) == provider_id
    assert finance_line["tracking_no"] == f"TRACK-{suffix}"
    assert float(finance_line["cost_estimated"]) == pytest.approx(12.5)


async def test_logistics_shipping_results_is_idempotent_by_package_key(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    suffix = uuid4().hex[:8].upper()
    provider_code = f"WMSID{suffix}"[:32]
    await _ensure_provider(session, code=provider_code)
    source_ref, platform, store_code, ext_order_no = await _seed_order_exported_record(
        session,
        source_ref_suffix=suffix,
    )

    payload = {
        "source_ref": source_ref,
        "packages": [
            {
                "package_no": 1,
                "tracking_no": f"TRACK-{suffix}",
                "shipping_provider_code": provider_code,
                "cost_estimated": "12.50",
            }
        ],
    }

    first = await client.post(
        "/shipping-assist/handoffs/shipping-results",
        headers=headers,
        json=payload,
    )
    assert first.status_code == 200, first.text
    first_id = int(first.json()["shipping_record_ids"][0])

    second_payload = {
        **payload,
        "packages": [
            {
                "package_no": 1,
                "tracking_no": f"TRACK-{suffix}",
                "shipping_provider_code": provider_code,
                "cost_estimated": "18.75",
            }
        ],
    }
    second = await client.post(
        "/shipping-assist/handoffs/shipping-results",
        headers=headers,
        json=second_payload,
    )
    assert second.status_code == 200, second.text
    assert int(second.json()["shipping_record_ids"][0]) == first_id

    record = await _load_shipping_record(
        session,
        platform=platform,
        store_code=store_code,
        order_ref=f"ORD:{platform}:{store_code}:{ext_order_no}",
        package_no=1,
    )
    assert int(record["id"]) == first_id
    assert float(record["cost_estimated"]) == pytest.approx(18.75)


async def test_logistics_shipping_results_rejects_before_imported(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    suffix = uuid4().hex[:8].upper()
    provider_code = f"WMSNI{suffix}"[:32]
    await _ensure_provider(session, code=provider_code)
    source_ref, _platform, _store_code, _ext_order_no = await _seed_order_exported_record(
        session,
        source_ref_suffix=suffix,
        export_status="PENDING",
        logistics_status="NOT_IMPORTED",
    )

    resp = await client.post(
        "/shipping-assist/handoffs/shipping-results",
        headers=headers,
        json={
            "source_ref": source_ref,
            "packages": [
                {
                    "package_no": 1,
                    "tracking_no": f"TRACK-{suffix}",
                    "shipping_provider_code": provider_code,
                }
            ],
        },
    )

    assert resp.status_code == 409, resp.text
    assert "not_exported" in resp.text


async def test_logistics_shipping_results_rejects_missing_provider_mapping(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    suffix = uuid4().hex[:8].upper()
    source_ref, _platform, _store_code, _ext_order_no = await _seed_order_exported_record(
        session,
        source_ref_suffix=suffix,
    )

    resp = await client.post(
        "/shipping-assist/handoffs/shipping-results",
        headers=headers,
        json={
            "source_ref": source_ref,
            "packages": [
                {
                    "package_no": 1,
                    "tracking_no": f"TRACK-{suffix}",
                    "shipping_provider_code": f"MISSING{suffix}"[:32],
                }
            ],
        },
    )

    assert resp.status_code == 409, resp.text
    assert "shipping_provider_mapping_not_found" in resp.text

    row = (
        await session.execute(
            text(
                """
                SELECT logistics_status
                FROM wms_logistics_export_records
                WHERE source_ref = :source_ref
                LIMIT 1
                """
            ),
            {"source_ref": source_ref},
        )
    ).mappings().first()
    assert row is not None
    assert row["logistics_status"] == "IMPORTED"


async def test_logistics_shipping_results_returns_404_for_missing_source_ref(
    client: AsyncClient,
) -> None:
    headers = await _login_admin_headers(client)

    resp = await client.post(
        "/shipping-assist/handoffs/shipping-results",
        headers=headers,
        json={
            "source_ref": "WMS:ORDER_OUTBOUND:NOT_FOUND",
            "packages": [
                {
                    "package_no": 1,
                    "tracking_no": "TRACK-NOT-FOUND",
                    "shipping_provider_code": "NOTFOUND",
                }
            ],
        },
    )

    assert resp.status_code == 404, resp.text


async def test_logistics_shipping_results_validates_unique_package_no(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    suffix = uuid4().hex[:8].upper()
    provider_code = f"WMSPK{suffix}"[:32]
    await _ensure_provider(session, code=provider_code)
    source_ref, _platform, _store_code, _ext_order_no = await _seed_order_exported_record(
        session,
        source_ref_suffix=suffix,
    )

    resp = await client.post(
        "/shipping-assist/handoffs/shipping-results",
        headers=headers,
        json={
            "source_ref": source_ref,
            "packages": [
                {
                    "package_no": 1,
                    "tracking_no": f"TRACK-A-{suffix}",
                    "shipping_provider_code": provider_code,
                },
                {
                    "package_no": 1,
                    "tracking_no": f"TRACK-B-{suffix}",
                    "shipping_provider_code": provider_code,
                },
            ],
        },
    )

    assert resp.status_code == 422, resp.text
