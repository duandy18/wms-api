from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.helpers.procurement_pms_projection import install_procurement_pms_projection_fake


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _pick_item_resolution(async_session_maker) -> dict[str, object]:
    async with async_session_maker() as session:
        install_procurement_pms_projection_fake(session)

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


async def _create_published_fsku_with_component(async_session_maker) -> int:
    item = await _pick_item_resolution(async_session_maker)
    code = f"UT-INGEST-FSKU-{uuid4().hex[:10]}"
    expr = f"{item['sku_code']}*1*1"

    async with async_session_maker() as session:
        install_procurement_pms_projection_fake(session)

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
                  1,
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
                "component_sku_code": str(item["sku_code"]),
                "resolved_item_id": int(item["item_id"]),
                "resolved_item_sku_code_id": int(item["item_sku_code_id"]),
                "resolved_item_uom_id": int(item["item_uom_id"]),
                "sku_code_snapshot": str(item["sku_code"]),
                "item_name_snapshot": str(item["item_name"]),
                "uom_snapshot": str(item["uom"]),
            },
        )

        await session.commit()

    return fsku_id


@pytest.mark.asyncio
async def test_platform_orders_ingest_code_not_mapped_returns_next_actions(client):
    filled_code = _uniq("MC-UT-NOT-MAPPED")

    ingest_payload = {
        "platform": "DEMO",
        "store_code": "1",
        "ext_order_no": _uniq("EXT-MC-NOT-MAPPED"),
        "receiver_name": "张三",
        "receiver_phone": "13800000000",
        "province": "上海市",
        "city": "上海市",
        "district": "浦东新区",
        "detail": "测试路 1 号",
        "lines": [{"filled_code": filled_code, "qty": 1}],
    }

    r = await client.post("/oms/platform-orders/ingest", json=ingest_payload)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body.get("status") == "UNRESOLVED"
    store_id = int(body.get("store_id") or 0)
    assert store_id > 0

    unresolved = body.get("unresolved") or []
    assert len(unresolved) == 1

    u0 = unresolved[0]
    assert u0.get("filled_code") == filled_code
    assert u0.get("reason") in {"CODE_NOT_BOUND", "CODE_NOT_MAPPED"}

    next_actions = u0.get("next_actions") or []
    assert isinstance(next_actions, list) and len(next_actions) >= 1

    a0 = next_actions[0]
    assert a0.get("action") == "go_code_mapping"
    assert str(a0.get("route_path") or "").endswith("/code-mapping")

    payload = a0.get("payload") or {}
    assert payload.get("platform") == "DEMO"
    assert int(payload.get("store_id") or 0) == store_id

    assert (
        payload.get("identity_value")
        or payload.get("merchant_code")
        or payload.get("filled_code")
    ) == filled_code


@pytest.mark.asyncio
async def test_platform_code_mapping_persists_and_ingest_can_resolve(client, async_session_maker):
    filled_code = _uniq("MC-UT-MAP")

    seed_payload = {
        "platform": "DEMO",
        "store_code": "1",
        "ext_order_no": _uniq("EXT-MC-SEED"),
        "receiver_name": "张三",
        "receiver_phone": "13800000000",
        "province": "上海市",
        "city": "上海市",
        "district": "浦东新区",
        "detail": "测试路 1 号",
        "lines": [{"filled_code": filled_code, "qty": 1}],
    }

    r0 = await client.post("/oms/platform-orders/ingest", json=seed_payload)
    assert r0.status_code == 200, r0.text
    b0 = r0.json()

    store_id = int(b0.get("store_id") or 0)
    assert store_id > 0

    fsku_id = await _create_published_fsku_with_component(async_session_maker)

    mapping_payload = {
        "platform": "DEMO",
        "store_code": "1",
        "identity_kind": "merchant_code",
        "identity_value": filled_code,
        "fsku_id": fsku_id,
        "reason": "ut mapping",
    }

    r1 = await client.post("/oms/platform-code-mappings/bind", json=mapping_payload)
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1.get("ok") is True
    assert b1["data"]["identity_kind"] == "merchant_code"
    assert b1["data"]["identity_value"] == filled_code
    assert int(b1["data"]["fsku_id"]) == int(fsku_id)

    async with async_session_maker() as session:
        install_procurement_pms_projection_fake(session)

        row = (
            await session.execute(
                text(
                    """
                    SELECT id, fsku_id
                      FROM platform_code_fsku_mappings
                     WHERE platform = 'DEMO'
                       AND store_code = '1'
                       AND identity_kind = 'merchant_code'
                       AND identity_value = :code
                     LIMIT 1
                    """
                ),
                {"code": filled_code},
            )
        ).mappings().first()

        assert row is not None
        assert int(row["fsku_id"]) == int(fsku_id)

    resolved_payload = {
        "platform": "DEMO",
        "store_code": "1",
        "ext_order_no": _uniq("EXT-MC-RESOLVED"),
        "receiver_name": "李四",
        "receiver_phone": "13800000001",
        "province": "上海市",
        "city": "上海市",
        "district": "浦东新区",
        "detail": "测试路 2 号",
        "lines": [{"filled_code": filled_code, "qty": 2}],
    }

    r2 = await client.post("/oms/platform-orders/ingest", json=resolved_payload)
    assert r2.status_code == 200, r2.text
    b2 = r2.json()

    # 这里只验证“平台编码映射已被 ingest 解析链路消费”。
    # 后续履约可能因为服务省份等下游条件被阻断，不能把 NO_SERVICE_PROVINCE 当成 SKU 映射失败。
    assert b2.get("status") in {"OK", "RESOLVED", "CREATED", "FULFILLMENT_BLOCKED"}
    assert b2.get("unresolved") in ([], None)
    assert int(b2.get("facts_written") or 0) >= 1
    if b2.get("status") == "FULFILLMENT_BLOCKED":
        assert "NO_SERVICE_PROVINCE" in (b2.get("blocked_reasons") or [])
