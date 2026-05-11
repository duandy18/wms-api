from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.asyncio


async def _clear_rows(session) -> None:
    await session.execute(text("DELETE FROM platform_code_fsku_mappings"))
    await session.execute(text("DELETE FROM oms_pdd_order_mirror_lines"))
    await session.execute(text("DELETE FROM oms_pdd_order_mirrors"))
    await session.commit()


async def _pick_item_resolution(session) -> dict[str, object]:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  sc.sku_code_id AS item_sku_code_id,
                  sc.item_id AS item_id,
                  sc.sku_code AS sku_code,
                  i.name AS item_name,
                  u.item_uom_id AS item_uom_id,
                  COALESCE(NULLIF(u.display_name, ''), u.uom) AS uom
                FROM wms_pms_sku_code_projection sc
                JOIN wms_pms_item_projection i ON i.item_id = sc.item_id
                JOIN LATERAL (
                  SELECT item_uom_id, uom, display_name
                  FROM wms_pms_uom_projection
                  WHERE item_id = i.item_id
                  ORDER BY
                    is_outbound_default DESC,
                    is_base DESC,
                    item_uom_id ASC
                  LIMIT 1
                ) u ON TRUE
                WHERE sc.is_active = TRUE
                  AND i.enabled = TRUE
                ORDER BY
                  sc.is_primary DESC,
                  sc.sku_code_id ASC
                LIMIT 1
                """
            )
        )
    ).mappings().first()

    assert row is not None, "baseline item with active SKU code and UOM is required"
    return dict(row)


async def _create_published_fsku_with_component(
    session,
    *,
    code: str,
    item_resolution: dict[str, object],
    component_qty: int,
) -> int:
    expr = f"{item_resolution['sku_code']}*{int(component_qty)}*1"

    row = (
        await session.execute(
            text(
                """
                INSERT INTO oms_fskus (
                  code,
                  name,
                  shape,
                  status,
                  fsku_expr,
                  normalized_expr,
                  expr_type,
                  component_count,
                  published_at,
                  created_at,
                  updated_at
                )
                VALUES (
                  CAST(:code AS varchar),
                  CAST(:name AS text),
                  'bundle',
                  'published',
                  CAST(:expr AS text),
                  upper(CAST(:expr AS text)),
                  'DIRECT',
                  1,
                  now(),
                  now(),
                  now()
                )
                RETURNING id
                """
            ),
            {
                "code": code,
                "name": f"{code}-NAME",
                "expr": expr,
            },
        )
    ).mappings().one()

    fsku_id = int(row["id"])

    await session.execute(
        text(
            """
            INSERT INTO oms_fsku_components (
              fsku_id,
              component_sku_code,
              qty_per_fsku,
              alloc_unit_price,
              resolved_item_id,
              resolved_item_sku_code_id,
              resolved_item_uom_id,
              sku_code_snapshot,
              item_name_snapshot,
              uom_snapshot,
              sort_order,
              created_at,
              updated_at
            )
            VALUES (
              :fsku_id,
              :component_sku_code,
              :qty_per_fsku,
              1,
              :resolved_item_id,
              :resolved_item_sku_code_id,
              :resolved_item_uom_id,
              :sku_code_snapshot,
              :item_name_snapshot,
              :uom_snapshot,
              1,
              now(),
              now()
            )
            """
        ),
        {
            "fsku_id": fsku_id,
            "component_sku_code": str(item_resolution["sku_code"]),
            "qty_per_fsku": int(component_qty),
            "resolved_item_id": int(item_resolution["item_id"]),
            "resolved_item_sku_code_id": int(item_resolution["item_sku_code_id"]),
            "resolved_item_uom_id": int(item_resolution["item_uom_id"]),
            "sku_code_snapshot": str(item_resolution["sku_code"]),
            "item_name_snapshot": str(item_resolution["item_name"]),
            "uom_snapshot": str(item_resolution["uom"]),
        },
    )

    return fsku_id


async def _create_pdd_mirror_with_one_line(
    session,
    *,
    store_code: str,
    order_no: str,
    merchant_code: str | None,
    platform_item_id: str,
    platform_sku_id: str,
    quantity: Decimal,
) -> tuple[int, int]:
    collector_order_id = 9000000000 + (uuid4().int % 900000000)
    collector_store_id = 8000000000 + (uuid4().int % 900000000)
    collector_line_id = 7000000000 + (uuid4().int % 900000000)

    mirror = (
        await session.execute(
            text(
                """
                INSERT INTO oms_pdd_order_mirrors (
                  collector_order_id,
                  collector_store_id,
                  collector_store_code,
                  collector_store_name,
                  platform_order_no,
                  platform_status
                )
                VALUES (
                  :collector_order_id,
                  :collector_store_id,
                  :store_code,
                  'PDD SKU 解析测试店铺',
                  :order_no,
                  'WAIT_SELLER_SEND_GOODS'
                )
                RETURNING id
                """
            ),
            {
                "collector_order_id": collector_order_id,
                "collector_store_id": collector_store_id,
                "store_code": store_code,
                "order_no": order_no,
            },
        )
    ).mappings().one()

    mirror_id = int(mirror["id"])

    line = (
        await session.execute(
            text(
                """
                INSERT INTO oms_pdd_order_mirror_lines (
                  mirror_id,
                  collector_line_id,
                  collector_order_id,
                  platform_order_no,
                  merchant_sku,
                  platform_item_id,
                  platform_sku_id,
                  title,
                  quantity,
                  line_amount
                )
                VALUES (
                  :mirror_id,
                  :collector_line_id,
                  :collector_order_id,
                  :order_no,
                  :merchant_code,
                  :platform_item_id,
                  :platform_sku_id,
                  'PDD SKU 解析测试商品',
                  :quantity,
                  99.99
                )
                RETURNING id
                """
            ),
            {
                "mirror_id": mirror_id,
                "collector_line_id": collector_line_id,
                "collector_order_id": collector_order_id,
                "order_no": order_no,
                "merchant_code": merchant_code,
                "platform_item_id": platform_item_id,
                "platform_sku_id": platform_sku_id,
                "quantity": quantity,
            },
        )
    ).mappings().one()

    return mirror_id, int(line["id"])


async def _bind_platform_code(
    session,
    *,
    store_code: str,
    identity_kind: str,
    identity_value: str,
    fsku_id: int,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO platform_code_fsku_mappings (
              platform,
              store_code,
              identity_kind,
              identity_value,
              fsku_id,
              reason,
              created_at,
              updated_at
            )
            VALUES (
              'PDD',
              :store_code,
              :identity_kind,
              :identity_value,
              :fsku_id,
              'order sku resolution test',
              now(),
              now()
            )
            """
        ),
        {
            "store_code": store_code,
            "identity_kind": identity_kind,
            "identity_value": identity_value,
            "fsku_id": int(fsku_id),
        },
    )


async def test_pdd_order_sku_resolution_resolves_by_merchant_code_mapping(client, session) -> None:
    await _clear_rows(session)

    suffix = uuid4().hex[:8]
    item = await _pick_item_resolution(session)
    fsku_id = await _create_published_fsku_with_component(
        session,
        code=f"UT-OSR-FSKU-MAP-{suffix}",
        item_resolution=item,
        component_qty=2,
    )

    store_code = f"PDD-OSR-MAP-{suffix}"
    merchant_code = f"PDD-OSR-MC-{suffix}"
    mirror_id, line_id = await _create_pdd_mirror_with_one_line(
        session,
        store_code=store_code,
        order_no=f"PDD-OSR-MAP-ORDER-{suffix}",
        merchant_code=merchant_code,
        platform_item_id=f"PDD-ITEM-{suffix}",
        platform_sku_id=f"PDD-SKU-{suffix}",
        quantity=Decimal("3"),
    )
    await _bind_platform_code(
        session,
        store_code=store_code,
        identity_kind="merchant_code",
        identity_value=merchant_code,
        fsku_id=fsku_id,
    )
    await session.commit()

    resp = await client.get(f"/oms/pdd/platform-order-mirrors/{mirror_id}/sku-resolution")
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    assert data["status"] == "resolved"
    assert data["mirror_id"] == mirror_id

    assert len(data["lines"]) == 1
    line = data["lines"][0]
    assert line["line_id"] == line_id
    assert line["resolution_status"] == "resolved"
    assert line["resolution_source"] == "code_mapping"
    assert line["resolved_identity_kind"] == "merchant_code"
    assert line["resolved_identity_value"] == merchant_code
    assert line["fsku_id"] == fsku_id
    assert line["merchant_code"] == merchant_code

    assert line["components"] == [
        {
            "item_id": int(item["item_id"]),
            "item_sku_code_id": int(item["item_sku_code_id"]),
            "item_uom_id": int(item["item_uom_id"]),
            "sku_code": str(item["sku_code"]),
            "item_name": str(item["item_name"]),
            "uom": str(item["uom"]),
            "qty": "6",
            "alloc_unit_price": "1",
            "sort_order": 1,
        }
    ]


async def test_pdd_order_sku_resolution_resolves_by_platform_sku_id_mapping(client, session) -> None:
    await _clear_rows(session)

    suffix = uuid4().hex[:8]
    item = await _pick_item_resolution(session)
    fsku_id = await _create_published_fsku_with_component(
        session,
        code=f"UT-OSR-PSKU-{suffix}",
        item_resolution=item,
        component_qty=3,
    )

    store_code = f"PDD-OSR-PSKU-{suffix}"
    platform_sku_id = f"PDD-SKU-ONLY-{suffix}"
    mirror_id, line_id = await _create_pdd_mirror_with_one_line(
        session,
        store_code=store_code,
        order_no=f"PDD-OSR-PSKU-ORDER-{suffix}",
        merchant_code=None,
        platform_item_id=f"PDD-ITEM-{suffix}",
        platform_sku_id=platform_sku_id,
        quantity=Decimal("2"),
    )
    await _bind_platform_code(
        session,
        store_code=store_code,
        identity_kind="platform_sku_id",
        identity_value=platform_sku_id,
        fsku_id=fsku_id,
    )
    await session.commit()

    resp = await client.get(f"/oms/pdd/platform-order-mirrors/{mirror_id}/sku-resolution")
    assert resp.status_code == 200, resp.text

    line = resp.json()["data"]["lines"][0]
    assert line["line_id"] == line_id
    assert line["resolution_status"] == "resolved"
    assert line["resolution_source"] == "code_mapping"
    assert line["resolved_identity_kind"] == "platform_sku_id"
    assert line["resolved_identity_value"] == platform_sku_id
    assert line["fsku_id"] == fsku_id
    assert line["components"][0]["qty"] == "6"


async def test_pdd_order_sku_resolution_resolves_by_direct_fsku_code(client, session) -> None:
    await _clear_rows(session)

    suffix = uuid4().hex[:8]
    item = await _pick_item_resolution(session)
    fsku_code = f"UT-OSR-DIRECT-{suffix}"
    fsku_id = await _create_published_fsku_with_component(
        session,
        code=fsku_code,
        item_resolution=item,
        component_qty=4,
    )

    mirror_id, line_id = await _create_pdd_mirror_with_one_line(
        session,
        store_code=f"PDD-OSR-DIRECT-{suffix}",
        order_no=f"PDD-OSR-DIRECT-ORDER-{suffix}",
        merchant_code=fsku_code,
        platform_item_id=f"PDD-ITEM-{suffix}",
        platform_sku_id=f"PDD-SKU-{suffix}",
        quantity=Decimal("2"),
    )
    await session.commit()

    resp = await client.get(f"/oms/pdd/platform-order-mirrors/{mirror_id}/sku-resolution")
    assert resp.status_code == 200, resp.text

    line = resp.json()["data"]["lines"][0]
    assert line["line_id"] == line_id
    assert line["resolution_status"] == "resolved"
    assert line["resolution_source"] == "direct_fsku_code"
    assert line["resolved_identity_kind"] == "merchant_code"
    assert line["resolved_identity_value"] == fsku_code
    assert line["fsku_id"] == fsku_id
    assert line["fsku_code"] == fsku_code
    assert line["components"][0]["qty"] == "8"


async def test_pdd_order_sku_resolution_returns_mapping_actions_when_unresolved(client, session) -> None:
    await _clear_rows(session)

    suffix = uuid4().hex[:8]
    mirror_id, line_id = await _create_pdd_mirror_with_one_line(
        session,
        store_code=f"PDD-OSR-UNRESOLVED-{suffix}",
        order_no=f"PDD-OSR-UNRESOLVED-ORDER-{suffix}",
        merchant_code=f"PDD-OSR-NOT-MAPPED-{suffix}",
        platform_item_id=f"PDD-ITEM-{suffix}",
        platform_sku_id=f"PDD-SKU-{suffix}",
        quantity=Decimal("1"),
    )
    await session.commit()

    resp = await client.get(f"/oms/pdd/platform-order-mirrors/{mirror_id}/sku-resolution")
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    assert data["status"] == "needs_mapping"
    line = data["lines"][0]
    assert line["line_id"] == line_id
    assert line["resolution_status"] == "needs_mapping"
    assert line["resolution_source"] == "unresolved"
    assert line["unresolved_reason"] == "CODE_NOT_MAPPED"
    assert line["components"] == []

    actions = line["next_actions"]
    assert [a["action"] for a in actions] == ["go_code_mapping", "go_fsku_rules"]
    assert actions[0]["route_path"] == "/oms/pdd/code-mapping"
    assert actions[1]["route_path"] == "/oms/fskus"
