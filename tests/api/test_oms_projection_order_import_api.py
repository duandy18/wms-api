from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _login_admin_headers(client: AsyncClient) -> dict[str, str]:
    resp = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _seed_projection_order(session: AsyncSession) -> str:
    suffix = uuid4().hex[:10]
    ready_order_id = f"ut-import:{suffix}"
    ready_line_id = f"{ready_order_id}:line:1"

    await session.execute(
        text(
            """
            INSERT INTO wms_oms_fulfillment_order_projection (
              ready_order_id,
              source_order_id,
              platform,
              store_code,
              store_name,
              platform_order_no,
              platform_status,
              receiver_name,
              receiver_phone,
              receiver_province,
              receiver_city,
              receiver_district,
              receiver_address,
              receiver_postcode,
              buyer_remark,
              seller_remark,
              ready_status,
              ready_at,
              source_updated_at,
              line_count,
              component_count,
              total_required_qty,
              source_hash,
              sync_version
            )
            VALUES (
              :ready_order_id,
              900001,
              'pdd',
              :store_code,
              'UT Import Store',
              :platform_order_no,
              'WAIT_SELLER_SEND_GOODS',
              '赵六',
              '13600000000',
              '浙江省',
              '杭州市',
              '西湖区',
              '文三路 100 号',
              '310000',
              'buyer remark',
              'seller remark',
              'READY',
              now(),
              now(),
              1,
              2,
              5,
              :source_hash,
              'ut-sync'
            )
            """
        ),
        {
            "ready_order_id": ready_order_id,
            "store_code": f"UT-IMPORT-STORE-{suffix}",
            "platform_order_no": f"UT-IMPORT-ORDER-{suffix}",
            "source_hash": f"order-hash-{suffix}",
        },
    )

    await session.execute(
        text(
            """
            INSERT INTO wms_oms_fulfillment_line_projection (
              ready_line_id,
              ready_order_id,
              source_line_id,
              platform,
              store_code,
              identity_kind,
              identity_value,
              merchant_sku,
              platform_item_id,
              platform_sku_id,
              platform_goods_name,
              platform_sku_name,
              ordered_qty,
              fsku_id,
              fsku_code,
              fsku_name,
              fsku_status_snapshot,
              source_hash,
              sync_version
            )
            SELECT
              :ready_line_id,
              ready_order_id,
              1,
              platform,
              store_code,
              'merchant_code',
              'UT-MERCHANT',
              'UT-MERCHANT',
              'UT-GOODS',
              'UT-SKU',
              'UT Platform Goods',
              '规格',
              1,
              9900,
              'UT-FSKU',
              'UT FSKU',
              'published',
              :source_hash,
              'ut-sync'
            FROM wms_oms_fulfillment_order_projection
            WHERE ready_order_id = :ready_order_id
            """
        ),
        {
            "ready_order_id": ready_order_id,
            "ready_line_id": ready_line_id,
            "source_hash": f"line-hash-{suffix}",
        },
    )

    for idx, item_id, qty in (
        (1, 880001, Decimal("2")),
        (2, 880002, Decimal("3")),
    ):
        await session.execute(
            text(
                """
                INSERT INTO wms_oms_fulfillment_component_projection (
                  ready_component_id,
                  ready_line_id,
                  ready_order_id,
                  resolved_item_id,
                  resolved_item_sku_code_id,
                  resolved_item_uom_id,
                  component_sku_code,
                  sku_code_snapshot,
                  item_name_snapshot,
                  uom_snapshot,
                  qty_per_fsku,
                  required_qty,
                  alloc_unit_price,
                  sort_order,
                  source_hash,
                  sync_version
                )
                VALUES (
                  :ready_component_id,
                  :ready_line_id,
                  :ready_order_id,
                  :resolved_item_id,
                  :resolved_item_sku_code_id,
                  :resolved_item_uom_id,
                  :component_sku_code,
                  :sku_code_snapshot,
                  :item_name_snapshot,
                  '件',
                  :qty_per_fsku,
                  :required_qty,
                  1,
                  :sort_order,
                  :source_hash,
                  'ut-sync'
                )
                """
            ),
            {
                "ready_component_id": f"{ready_line_id}:component:{idx}",
                "ready_line_id": ready_line_id,
                "ready_order_id": ready_order_id,
                "resolved_item_id": item_id,
                "resolved_item_sku_code_id": item_id + 1000,
                "resolved_item_uom_id": item_id + 2000,
                "component_sku_code": f"UT-SKU-{idx}",
                "sku_code_snapshot": f"UT-SKU-{idx}",
                "item_name_snapshot": f"UT Import Item {idx}",
                "qty_per_fsku": qty,
                "required_qty": qty,
                "sort_order": idx,
                "source_hash": f"component-hash-{suffix}-{idx}",
            },
        )

    await session.commit()
    return ready_order_id


async def test_import_oms_projection_order_creates_wms_execution_order(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)
    ready_order_id = await _seed_projection_order(session)

    dry_run = await client.post(
        "/wms/outbound/orders/import-from-oms-projection",
        headers=headers,
        json={"ready_order_ids": [ready_order_id], "dry_run": True},
    )
    assert dry_run.status_code == 200, dry_run.text
    dry_data = dry_run.json()
    assert dry_data["dry_run"] is True
    assert dry_data["imported"] == 0
    assert dry_data["results"][0]["status"] == "DRY_RUN"

    created_before = (
        await session.execute(
            text(
                """
                SELECT count(*)
                FROM wms_oms_fulfillment_order_imports
                WHERE ready_order_id = :ready_order_id
                """
            ),
            {"ready_order_id": ready_order_id},
        )
    ).scalar_one()
    assert int(created_before) == 0

    resp = await client.post(
        "/wms/outbound/orders/import-from-oms-projection",
        headers=headers,
        json={"ready_order_ids": [ready_order_id], "dry_run": False},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["dry_run"] is False
    assert data["imported"] == 1
    assert data["already_imported"] == 0
    assert data["failed"] == 0

    row = data["results"][0]
    assert row["status"] == "IMPORTED"
    assert row["order_id"]
    assert row["platform"] == "PDD"
    assert row["order_line_count"] == 2
    assert row["component_count"] == 2

    order_id = int(row["order_id"])

    order_row = (
        await session.execute(
            text(
                """
                SELECT platform, store_code, ext_order_no, status
                FROM orders
                WHERE id = :order_id
                """
            ),
            {"order_id": order_id},
        )
    ).mappings().one()
    assert order_row["platform"] == "PDD"
    assert order_row["status"] == "CREATED"

    address_row = (
        await session.execute(
            text(
                """
                SELECT receiver_name, receiver_phone, province, city, district, detail, zipcode
                FROM order_address
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id},
        )
    ).mappings().one()
    assert address_row["receiver_name"] == "赵六"
    assert address_row["city"] == "杭州市"

    line_count = (
        await session.execute(
            text("SELECT count(*) FROM order_lines WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
    ).scalar_one()
    assert int(line_count) == 2

    qty_sum = (
        await session.execute(
            text("SELECT COALESCE(sum(req_qty), 0) FROM order_lines WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
    ).scalar_one()
    assert int(qty_sum) == 5

    item_count = (
        await session.execute(
            text("SELECT count(*) FROM order_items WHERE order_id = :order_id"),
            {"order_id": order_id},
        )
    ).scalar_one()
    assert int(item_count) == 2

    fulfillment_status = (
        await session.execute(
            text(
                """
                SELECT fulfillment_status
                FROM order_fulfillment
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id},
        )
    ).scalar_one()
    assert fulfillment_status == "OMS_IMPORTED"

    component_import_count = (
        await session.execute(
            text(
                """
                SELECT count(*)
                FROM wms_oms_fulfillment_component_imports
                WHERE ready_order_id = :ready_order_id
                """
            ),
            {"ready_order_id": ready_order_id},
        )
    ).scalar_one()
    assert int(component_import_count) == 2

    options = await client.get(
        "/wms/outbound/orders/options",
        headers=headers,
        params={"q": str(order_id)},
    )
    assert options.status_code == 200, options.text
    options_data = options.json()
    assert options_data["total"] == 1
    assert int(options_data["items"][0]["id"]) == order_id

    duplicate = await client.post(
        "/wms/outbound/orders/import-from-oms-projection",
        headers=headers,
        json={"ready_order_ids": [ready_order_id], "dry_run": False},
    )
    assert duplicate.status_code == 200, duplicate.text
    duplicate_data = duplicate.json()
    assert duplicate_data["imported"] == 0
    assert duplicate_data["already_imported"] == 1
    assert duplicate_data["results"][0]["order_id"] == order_id
