# tests/api/test_oms_fulfillment_projection_ops_api.py
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _login_admin_headers(client: AsyncClient) -> dict[str, str]:
    r = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _clear_oms_projection(session: AsyncSession) -> None:
    await session.execute(text("DELETE FROM wms_oms_fulfillment_component_projection"))
    await session.execute(text("DELETE FROM wms_oms_fulfillment_line_projection"))
    await session.execute(text("DELETE FROM wms_oms_fulfillment_order_projection"))
    await session.execute(text("DELETE FROM wms_oms_fulfillment_projection_sync_runs"))
    await session.commit()


async def _insert_ready_order(session: AsyncSession) -> None:
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
                receiver_name,
                receiver_phone,
                receiver_province,
                receiver_city,
                receiver_address,
                ready_status,
                ready_at,
                source_updated_at,
                line_count,
                component_count,
                total_required_qty,
                synced_at
            )
            VALUES (
                'pdd:8801',
                8801,
                'pdd',
                'UT-PDD-STORE',
                'PDD 测试店',
                'PDD-8801',
                '张三',
                '13800000000',
                '浙江省',
                '杭州市',
                '文三路 1 号',
                'READY',
                now(),
                now(),
                1,
                1,
                2,
                now()
            )
            ON CONFLICT (ready_order_id) DO UPDATE
            SET store_code = EXCLUDED.store_code,
                store_name = EXCLUDED.store_name,
                platform_order_no = EXCLUDED.platform_order_no,
                line_count = EXCLUDED.line_count,
                component_count = EXCLUDED.component_count,
                total_required_qty = EXCLUDED.total_required_qty,
                synced_at = now()
            """
        )
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
                ordered_qty,
                fsku_id,
                fsku_code,
                fsku_name,
                fsku_status_snapshot,
                synced_at
            )
            VALUES (
                'pdd:8801:line:1',
                'pdd:8801',
                88011,
                'pdd',
                'UT-PDD-STORE',
                'merchant_code',
                'MERCHANT-8801',
                1,
                18801,
                'FSKU-8801',
                '履约商品8801',
                'published',
                now()
            )
            ON CONFLICT (ready_line_id) DO NOTHING
            """
        )
    )
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
                synced_at
            )
            VALUES (
                'pdd:8801:line:1:component:1',
                'pdd:8801:line:1',
                'pdd:8801',
                28801,
                38801,
                48801,
                'SKU-8801',
                'SKU-8801',
                '商品8801',
                '件',
                2,
                2,
                1,
                1,
                now()
            )
            ON CONFLICT (ready_component_id) DO NOTHING
            """
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_oms_fulfillment_projection_status_lists_resources(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _clear_oms_projection(session)
    headers = await _login_admin_headers(client)

    r = await client.get("/oms/fulfillment-projection/status", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["oms_api_base_url_configured"] in {True, False}

    resources = {row["resource"]: row for row in data["resources"]}
    assert list(resources.keys()) == ["orders", "lines", "components"]

    assert resources["orders"]["table_name"] == "wms_oms_fulfillment_order_projection"
    assert resources["lines"]["table_name"] == "wms_oms_fulfillment_line_projection"
    assert resources["components"]["table_name"] == "wms_oms_fulfillment_component_projection"


@pytest.mark.asyncio
async def test_oms_fulfillment_projection_can_list_rows(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _clear_oms_projection(session)
    await _insert_ready_order(session)
    headers = await _login_admin_headers(client)

    r = await client.get(
        "/oms/fulfillment-projection/projections/orders?limit=5&offset=0&q=PDD-8801",
        headers=headers,
    )
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["resource"] == "orders"
    assert data["table_name"] == "wms_oms_fulfillment_order_projection"
    assert data["limit"] == 5
    assert data["offset"] == 0
    assert data["total"] >= 1
    assert "ready_order_id" in data["columns"]
    assert "platform_order_no" in data["columns"]

    matched = [row for row in data["rows"] if row.get("ready_order_id") == "pdd:8801"]
    assert matched
    assert matched[0]["platform_order_no"] == "PDD-8801"


@pytest.mark.asyncio
async def test_oms_fulfillment_projection_can_check_projection(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _clear_oms_projection(session)
    await _insert_ready_order(session)
    headers = await _login_admin_headers(client)

    r = await client.post(
        "/oms/fulfillment-projection/projections/orders/check",
        headers=headers,
    )
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["resource"] == "orders"
    assert data["ok"] is True
    assert data["issue_count"] == 0
    assert data["issues"] == []


@pytest.mark.asyncio
async def test_oms_fulfillment_projection_status_does_not_expose_legacy_token_config(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _clear_oms_projection(session)
    monkeypatch.setenv("OMS_API_BASE_URL", "http://oms-api.test")
    monkeypatch.delenv("OMS_API_TOKEN", raising=False)

    headers = await _login_admin_headers(client)

    r = await client.get("/oms/fulfillment-projection/status", headers=headers)

    assert r.status_code == 200, r.text
    assert "oms_api_base_url_configured" in r.json()
    assert "oms_api_token_configured" not in r.json()


@pytest.mark.asyncio
async def test_oms_fulfillment_projection_sync_runs_can_be_listed(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _clear_oms_projection(session)
    await session.execute(
        text(
            """
            INSERT INTO wms_oms_fulfillment_projection_sync_runs (
                resource,
                platform,
                store_code,
                status,
                fetched,
                upserted_orders,
                upserted_lines,
                upserted_components,
                pages,
                started_at,
                finished_at,
                duration_ms,
                sync_version
            )
            VALUES (
                'fulfillment-ready-orders',
                'taobao',
                'UT-TB',
                'SUCCESS',
                2,
                2,
                3,
                4,
                1,
                now(),
                now(),
                10,
                'ut-sync-run'
            )
            """
        )
    )
    await session.commit()

    headers = await _login_admin_headers(client)
    r = await client.get(
        "/oms/fulfillment-projection/sync-runs?platform=taobao&limit=5",
        headers=headers,
    )
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["resource"] == "fulfillment-ready-orders"
    assert data["platform"] == "taobao"
    assert data["limit"] == 5
    assert data["runs"]
    assert data["runs"][0]["resource"] == "fulfillment-ready-orders"
    assert data["runs"][0]["platform"] == "taobao"
