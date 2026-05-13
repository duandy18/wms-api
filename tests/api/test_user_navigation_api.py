# tests/api/test_user_navigation_api.py
from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(autouse=True)
async def _reset_navigation_registry_state(session: AsyncSession) -> None:
    """
    仅恢复本文件测试会临时修改的导航状态，不破坏静态 seed 真相。

    当前主线要求：
    - 发货辅助页在相关测试前恢复为可见
    - wms.inventory_adjustment 下子页保持可见
    - wms.inbound 只保留 atomic / purchase / manual 可见
    - wms.inbound.operations / wms.inbound.returns 保持隐藏
    - inbound 只保留 summary / purchase / manual 可见
    """
    await session.execute(
        text(
            """
            UPDATE page_registry
               SET is_active = CASE
                 WHEN code IN (
                   'shipping_assist',
                   'shipping_assist.handoffs',
                   'shipping_assist.handoffs.status',
                   'shipping_assist.handoffs.payload',
                   'shipping_assist.records'
                 )
                 THEN TRUE
                 ELSE FALSE
               END
             WHERE code = 'shipping_assist'
                OR code LIKE 'shipping_assist.%'
            """
        )
    )

    await session.execute(
        text(
            """
            UPDATE page_registry
               SET is_active = TRUE
             WHERE parent_code = 'wms.inventory_adjustment'
            """
        )
    )

    await session.execute(
        text(
            """
            UPDATE page_registry
               SET is_active = TRUE
             WHERE code IN (
               'wms.inbound.atomic',
               'wms.inbound.purchase',
               'wms.inbound.manual',
               'inbound.summary',
               'inbound.purchase',
               'inbound.manual'
             )
            """
        )
    )

    await session.execute(
        text(
            """
            UPDATE page_registry
               SET is_active = FALSE
             WHERE code IN (
               'wms.inbound.operations',
               'wms.inbound.returns',
               'inbound.returns'
             )
            """
        )
    )

    await session.execute(
        text(
            """
            UPDATE page_route_prefixes
               SET is_active = FALSE
             WHERE route_prefix = '/shipping-assist/reports'
            """
        )
    )

    await session.execute(
        text(
            """
            UPDATE page_route_prefixes
               SET is_active = CASE
                 WHEN route_prefix IN (
                   '/shipping-assist/handoffs',
                   '/shipping-assist/handoffs/status',
                   '/shipping-assist/handoffs/payload',
                   '/shipping-assist/records'
                 )
                   OR route_prefix LIKE '/inventory-adjustment%'
                 THEN TRUE
                 ELSE FALSE
               END
             WHERE route_prefix LIKE '/shipping-assist/%'
                OR route_prefix LIKE '/inventory-adjustment%'
            """
        )
    )

    await session.commit()


async def _login_admin_headers(client: AsyncClient) -> dict[str, str]:
    r = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _walk_pages(pages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}

    def walk(node: dict[str, Any]) -> None:
        out[node["code"]] = node
        for child in node.get("children") or []:
            walk(child)

    for page in pages:
        walk(page)

    return out


def _index_route_prefixes(route_prefixes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["route_prefix"]: item for item in route_prefixes}


def _child_codes(node: dict[str, Any]) -> list[str]:
    return [child["code"] for child in (node.get("children") or [])]


async def _set_user_permissions_by_names(
    session: AsyncSession,
    *,
    username: str,
    permission_names: list[str],
) -> None:
    await session.execute(
        text(
            """
            DELETE FROM user_permissions
             WHERE user_id = (
                SELECT id
                  FROM users
                 WHERE username = :username
                 LIMIT 1
             )
            """
        ),
        {"username": username},
    )

    if permission_names:
        await session.execute(
            text(
                """
                INSERT INTO user_permissions (user_id, permission_id)
                SELECT u.id, p.id
                  FROM users u
                  JOIN permissions p
                    ON p.name = ANY(CAST(:permission_names AS text[]))
                 WHERE u.username = :username
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "username": username,
                "permission_names": permission_names,
            },
        )

    await session.commit()


@pytest.mark.asyncio
async def test_my_me_shape_unchanged(client: AsyncClient) -> None:
    headers = await _login_admin_headers(client)

    r = await client.get("/users/me", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    assert isinstance(data, dict)

    assert {"id", "username", "permissions"} <= set(data.keys())
    assert isinstance(data["id"], int)
    assert isinstance(data["username"], str)
    assert isinstance(data["permissions"], list)
    assert "page.admin.read" in data["permissions"]
    assert "page.admin.write" in data["permissions"]


@pytest.mark.asyncio
async def test_my_navigation_returns_pages_and_route_prefixes(client: AsyncClient) -> None:
    headers = await _login_admin_headers(client)

    r = await client.get("/users/me/navigation", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    assert isinstance(data, dict)

    pages = data.get("pages")
    route_prefixes = data.get("route_prefixes")

    assert isinstance(pages, list)
    assert isinstance(route_prefixes, list)
    assert pages, "pages should not be empty for admin"
    assert route_prefixes, "route_prefixes should not be empty for admin"


@pytest.mark.asyncio
async def test_my_navigation_admin_contains_new_wms_tree_and_filters_legacy_shells(
    client: AsyncClient,
) -> None:
    headers = await _login_admin_headers(client)

    r = await client.get("/users/me/navigation", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    pages = data["pages"]
    nodes = _walk_pages(pages)

    root_codes = [page["code"] for page in pages]
    assert "wms" in root_codes
    assert "inbound" in root_codes

    wms = nodes["wms"]
    assert _child_codes(wms) == [
        "wms.inventory",
        "wms.inbound",
        "wms.outbound",
        "wms.inventory_adjustment",
        "wms.warehouses",
    ]

    assert _child_codes(nodes["wms.inventory"]) == [
        "wms.inventory.main",
        "wms.inventory.ledger",
    ]
    assert _child_codes(nodes["wms.inbound"]) == [
        "wms.inbound.atomic",
        "wms.inbound.purchase",
        "wms.inbound.manual",
    ]
    assert _child_codes(nodes["wms.outbound"]) == [
        "wms.outbound.summary",
        "wms.outbound.order",
        "wms.outbound.manual_docs",
        "wms.outbound.manual",
    ]
    assert _child_codes(nodes["wms.inventory_adjustment"]) == [
        "wms.inventory_adjustment.summary",
        "wms.inventory_adjustment.count",
        "wms.inventory_adjustment.inbound_reversal",
        "wms.inventory_adjustment.outbound_reversal",
    ]
    assert _child_codes(nodes["wms.warehouses"]) == []

    assert _child_codes(nodes["inbound"]) == [
        "inbound.summary",
        "inbound.purchase",
        "inbound.manual",
    ]

    assert "wms.count" not in nodes
    assert "wms.count.tasks" not in nodes
    assert "wms.count.adjustments" not in nodes
    assert "wms.inbound.returns" not in nodes
    assert "inbound.returns" not in nodes

    assert "wms.order_outbound" not in nodes
    assert "wms.order_management" not in nodes
    assert "wms.logistics" not in nodes
    assert "wms.logistics.shipment_prepare" not in nodes
    assert "wms.logistics.dispatch" not in nodes
    assert "wms.logistics.providers" not in nodes
    assert "wms.logistics.waybill_configs" not in nodes
    assert "wms.logistics.pricing" not in nodes
    assert "wms.logistics.templates" not in nodes
    assert "wms.logistics.records" not in nodes
    assert "wms.logistics.billing_items" not in nodes
    assert "wms.logistics.reconciliation" not in nodes
    assert "wms.logistics.reports" not in nodes
    assert "wms.analytics" not in nodes
    assert "wms.masterdata" not in nodes
    assert "wms.internal_ops" not in nodes
    assert "wms.inbound.receiving" not in nodes
    assert "wms.internal_ops.count" not in nodes
    assert "wms.internal_ops.internal_outbound" not in nodes
    assert "wms.order_outbound.pick_tasks" not in nodes
    assert "wms.order_outbound.dashboard" not in nodes
    assert "wms.masterdata.warehouses" not in nodes


@pytest.mark.asyncio
async def test_my_navigation_retired_partners_supplier_owner_is_absent(client: AsyncClient) -> None:
    headers = await _login_admin_headers(client)

    r = await client.get("/users/me/navigation", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    nodes = _walk_pages(data["pages"])
    route_map = _index_route_prefixes(data["route_prefixes"])

    assert "partners" not in nodes
    assert "partners.suppliers" not in nodes
    assert "pms.suppliers" not in nodes
    assert "/partners/suppliers" not in route_map
    assert "/suppliers" not in route_map


@pytest.mark.asyncio
async def test_my_navigation_pms_projection_tree_lives_under_product_management(
    client: AsyncClient,
) -> None:
    headers = await _login_admin_headers(client)

    r = await client.get("/users/me/navigation", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    nodes = _walk_pages(data["pages"])
    route_map = _index_route_prefixes(data["route_prefixes"])

    old_pms_owner_page_codes = [
        "pms.items",
        "pms.brands",
        "pms.categories",
        "pms.item_attributes",
        "pms.sku_coding",
        "pms.item_barcodes",
        "pms.item_uoms",
        "pms.projections",
        "pms.projections.items",
        "pms.projections.suppliers",
        "pms.projections.uoms",
        "pms.projections.sku_codes",
        "pms.projections.barcodes",
    ]
    for code in old_pms_owner_page_codes:
        assert code not in nodes

    for code in [
        "admin.pms_integration",
        "admin.pms_integration.items",
        "admin.pms_integration.suppliers",
        "admin.pms_integration.uoms",
        "admin.pms_integration.sku_codes",
        "admin.pms_integration.barcodes",
    ]:
        assert code not in nodes

    old_route_prefixes = [
        "/items",
        "/item-barcodes",
        "/item-uoms",
        "/items/sku-coding",
        "/pms/brands",
        "/pms/categories",
        "/pms/item-attribute-defs",
        "/pms/projections",
        "/pms/projections/items",
        "/pms/projections/suppliers",
        "/pms/projections/uoms",
        "/pms/projections/sku-codes",
        "/pms/projections/barcodes",
        "/admin/pms-integration",
        "/admin/pms-integration/items",
        "/admin/pms-integration/suppliers",
        "/admin/pms-integration/uoms",
        "/admin/pms-integration/sku-codes",
        "/admin/pms-integration/barcodes",
    ]
    for route_prefix in old_route_prefixes:
        assert route_prefix not in route_map

    pms = nodes["pms"]
    assert pms["name"] == "商品管理"
    assert pms["parent_code"] is None
    assert pms["domain_code"] == "pms"
    assert pms["effective_read_permission"] == "page.pms.read"
    assert pms["effective_write_permission"] == "page.pms.write"

    assert _child_codes(pms) == [
        "pms.item_projection",
        "pms.supplier_projection",
        "pms.uom_projection",
        "pms.sku_code_projection",
        "pms.barcode_projection",
    ]

    expected_names = {
        "pms.item_projection": "商品投影",
        "pms.supplier_projection": "供应商投影",
        "pms.uom_projection": "包装单位投影",
        "pms.sku_code_projection": "SKU 编码投影",
        "pms.barcode_projection": "条码投影",
    }
    for code, name in expected_names.items():
        node = nodes[code]
        assert node["name"] == name
        assert node["parent_code"] == "pms"
        assert node["domain_code"] == "pms"
        assert node["level"] == 2
        assert node["effective_read_permission"] == "page.pms.read"
        assert node["effective_write_permission"] == "page.pms.write"

    expected_route_map = {
        "/pms/item-projection": "pms.item_projection",
        "/pms/supplier-projection": "pms.supplier_projection",
        "/pms/uom-projection": "pms.uom_projection",
        "/pms/sku-code-projection": "pms.sku_code_projection",
        "/pms/barcode-projection": "pms.barcode_projection",
    }
    for route_prefix, page_code in expected_route_map.items():
        route = route_map.get(route_prefix)
        assert route is not None, f"{route_prefix} should exist in route_prefixes"
        assert route["page_code"] == page_code
        assert route["effective_read_permission"] == "page.pms.read"
        assert route["effective_write_permission"] == "page.pms.write"

    assert "/admin/pms-integration/connection" not in route_map
    assert "admin.pms_integration.connection" not in nodes


@pytest.mark.asyncio
async def test_my_navigation_route_prefix_mapping_and_effective_permissions(client: AsyncClient) -> None:
    headers = await _login_admin_headers(client)

    r = await client.get("/users/me/navigation", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    nodes = _walk_pages(data["pages"])
    route_map = _index_route_prefixes(data["route_prefixes"])

    shipping_handoffs_page = nodes["shipping_assist.handoffs"]
    shipping_records_page = nodes["shipping_assist.records"]
    pms_items_projection_page = nodes["pms.item_projection"]

    assert shipping_handoffs_page["effective_read_permission"]
    assert shipping_handoffs_page["effective_write_permission"]
    assert shipping_records_page["effective_read_permission"]
    assert shipping_records_page["effective_write_permission"]
    assert pms_items_projection_page["effective_read_permission"] == "page.pms.read"
    assert pms_items_projection_page["effective_write_permission"] == "page.pms.write"

    assert "/shipping-assist/handoffs" in route_map
    assert "/shipping-assist/records" in route_map
    assert "/pms/item-projection" in route_map

    assert route_map["/shipping-assist/handoffs"]["page_code"] == "shipping_assist.handoffs"
    assert route_map["/shipping-assist/records"]["page_code"] == "shipping_assist.records"
    assert route_map["/pms/item-projection"]["page_code"] == "pms.item_projection"

    assert "/items" not in route_map
    assert "/item-barcodes" not in route_map
    assert "/partners/suppliers" not in route_map
    assert "/admin/pms-integration" not in route_map
    assert "/admin/pms-integration/items" not in route_map
    assert "pms.items" not in nodes
    assert "pms.item_barcodes" not in nodes
    assert "partners.suppliers" not in nodes
    assert "admin.pms_integration" not in nodes


@pytest.mark.asyncio
async def test_my_navigation_pms_barcode_projection_route_prefix_mapping_and_permissions(
    client: AsyncClient,
) -> None:
    headers = await _login_admin_headers(client)

    r = await client.get("/users/me/navigation", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    route_map = _index_route_prefixes(data["route_prefixes"])

    barcode_projection_route = route_map.get("/pms/barcode-projection")
    assert barcode_projection_route is not None

    assert barcode_projection_route["page_code"] == "pms.barcode_projection"
    assert barcode_projection_route["effective_read_permission"] == "page.pms.read"
    assert barcode_projection_route["effective_write_permission"] == "page.pms.write"

    assert "/item-barcodes" not in route_map
    assert "/admin/pms-integration/barcodes" not in route_map


@pytest.mark.asyncio
async def test_my_navigation_filters_to_only_directly_visible_parent_tree(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _set_user_permissions_by_names(
        session,
        username="admin",
        permission_names=["page.shipping_assist.read"],
    )

    headers = await _login_admin_headers(client)

    r = await client.get("/users/me/navigation", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    pages = data["pages"]
    route_prefixes = data["route_prefixes"]

    assert [page["code"] for page in pages] == ["shipping_assist"]

    parent = pages[0]
    assert parent["name"] == "发货辅助"

    child_codes = [child["code"] for child in parent["children"]]
    assert child_codes == [
        "shipping_assist.handoffs",
        "shipping_assist.records",
    ]

    nodes = _walk_pages(pages)
    assert "shipping_assist.shipping" not in nodes
    assert "shipping_assist.pricing" not in nodes
    assert "shipping_assist.billing" not in nodes
    assert "admin.pms_integration" not in nodes

    assert all(item["page_code"].startswith("shipping_assist.") for item in route_prefixes)
    assert [item["route_prefix"] for item in route_prefixes] == [
        "/shipping-assist/handoffs",
        "/shipping-assist/handoffs/status",
        "/shipping-assist/handoffs/payload",
        "/shipping-assist/records",
    ]


@pytest.mark.asyncio
async def test_my_navigation_keeps_parent_visible_when_no_visible_children(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await _set_user_permissions_by_names(
        session,
        username="admin",
        permission_names=["page.shipping_assist.read"],
    )

    await session.execute(
        text(
            """
            UPDATE page_registry
               SET is_active = FALSE
             WHERE code LIKE 'shipping_assist.%'
            """
        )
    )
    await session.commit()

    headers = await _login_admin_headers(client)

    r = await client.get("/users/me/navigation", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    assert [page["code"] for page in data["pages"]] == ["shipping_assist"]
    assert data["pages"][0]["name"] == "发货辅助"
    assert data["pages"][0]["children"] == []
    assert data["route_prefixes"] == []


@pytest.mark.asyncio
async def test_my_navigation_contains_shipping_assist_two_level_tree(client: AsyncClient) -> None:
    headers = await _login_admin_headers(client)

    r = await client.get("/users/me/navigation", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    nodes = _walk_pages(data["pages"])
    route_map = _index_route_prefixes(data["route_prefixes"])

    root = nodes["shipping_assist"]
    assert root["name"] == "发货辅助"
    assert root["effective_read_permission"] == "page.shipping_assist.read"
    assert root["effective_write_permission"] == "page.shipping_assist.write"

    assert _child_codes(root) == [
        "shipping_assist.handoffs",
        "shipping_assist.records",
    ]

    assert "shipping_assist.shipping" not in nodes
    assert "shipping_assist.pricing" not in nodes
    assert "shipping_assist.billing" not in nodes

    expected_route_map = {
        "/shipping-assist/handoffs": "shipping_assist.handoffs",
        "/shipping-assist/handoffs/status": "shipping_assist.handoffs.status",
        "/shipping-assist/handoffs/payload": "shipping_assist.handoffs.payload",
        "/shipping-assist/records": "shipping_assist.records",
    }

    for route_prefix, page_code in expected_route_map.items():
        route = route_map.get(route_prefix)
        assert route is not None, f"{route_prefix} should exist in route_prefixes"
        assert route["page_code"] == page_code
        assert route["effective_read_permission"] == "page.shipping_assist.read"
        assert route["effective_write_permission"] == "page.shipping_assist.write"

    assert "/shipping-assist/reports" not in route_map
    assert "/shipping-assist/shipping/quote" not in route_map
    assert "/shipping-assist/settings/waybill" not in route_map
    assert "/shipping-assist/shipping/records" not in route_map
    assert "/shipping-assist/pricing/providers" not in route_map
    assert "/shipping-assist/pricing/bindings" not in route_map
    assert "/shipping-assist/pricing/templates" not in route_map
    assert "/shipping-assist/billing/items" not in route_map
    assert "/shipping-assist/billing/reconciliation" not in route_map
    assert "shipping_assist.shipping.quote" not in nodes
    assert "shipping_assist.settings" not in nodes
    assert "shipping_assist.settings.waybill" not in nodes
    assert "shipping_assist.pricing" not in nodes
    assert "shipping_assist.billing" not in nodes


@pytest.mark.asyncio
async def test_my_navigation_oms_keeps_only_projection_level_two_pages(
    client: AsyncClient,
) -> None:
    headers = await _login_admin_headers(client)

    r = await client.get("/users/me/navigation", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    nodes = _walk_pages(data["pages"])
    route_map = _index_route_prefixes(data["route_prefixes"])

    oms = nodes["oms"]
    assert oms["name"] == "订单管理"
    assert oms["parent_code"] is None
    assert oms["domain_code"] == "oms"
    assert oms["effective_read_permission"] == "page.oms.read"
    assert oms["effective_write_permission"] == "page.oms.write"

    assert _child_codes(oms) == [
        "oms.order_projection",
        "oms.line_projection",
        "oms.component_projection",
    ]

    expected_names = {
        "oms.order_projection": "订单投影",
        "oms.line_projection": "订单行投影",
        "oms.component_projection": "履约组件投影",
    }
    for code, name in expected_names.items():
        node = nodes[code]
        assert node["name"] == name
        assert node["parent_code"] == "oms"
        assert node["level"] == 2
        assert node["domain_code"] == "oms"
        assert node["effective_read_permission"] == "page.oms.read"
        assert node["effective_write_permission"] == "page.oms.write"

    expected_route_map = {
        "/oms/order-projection": "oms.order_projection",
        "/oms/line-projection": "oms.line_projection",
        "/oms/component-projection": "oms.component_projection",
    }
    for route_prefix, page_code in expected_route_map.items():
        route = route_map.get(route_prefix)
        assert route is not None, f"{route_prefix} should exist in route_prefixes"
        assert route["page_code"] == page_code
        assert route["effective_read_permission"] == "page.oms.read"
        assert route["effective_write_permission"] == "page.oms.write"

    retired_codes = [
        "oms.fsku_rules",
        "oms.pdd",
        "oms.pdd.platform_order_mirror",
        "oms.pdd.fsku_mapping",
        "oms.taobao",
        "oms.taobao.platform_order_mirror",
        "oms.taobao.fsku_mapping",
        "oms.jd",
        "oms.jd.platform_order_mirror",
        "oms.jd.fsku_mapping",
        "oms.fulfillment_projection",
        "oms.fulfillment_projection.orders",
        "oms.fulfillment_projection.lines",
        "oms.fulfillment_projection.components",
    ]
    for code in retired_codes:
        assert code not in nodes

    retired_routes = [
        "/oms/fskus",
        "/oms/pdd",
        "/oms/pdd/platform-order-mirror",
        "/oms/pdd/fsku-mapping",
        "/oms/taobao",
        "/oms/taobao/platform-order-mirror",
        "/oms/taobao/fsku-mapping",
        "/oms/jd",
        "/oms/jd/platform-order-mirror",
        "/oms/jd/fsku-mapping",
        "/oms/fulfillment-projection",
        "/oms/fulfillment-projection/orders",
        "/oms/fulfillment-projection/lines",
        "/oms/fulfillment-projection/components",
    ]
    for route_prefix in retired_routes:
        assert route_prefix not in route_map
