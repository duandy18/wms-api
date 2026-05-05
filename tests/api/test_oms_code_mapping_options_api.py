from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.asyncio


async def _clear_rows(session) -> None:
    await session.execute(text("DELETE FROM platform_code_fsku_mappings"))
    await session.execute(text("DELETE FROM oms_pdd_order_mirror_lines"))
    await session.execute(text("DELETE FROM oms_taobao_order_mirror_lines"))
    await session.execute(text("DELETE FROM oms_jd_order_mirror_lines"))
    await session.execute(text("DELETE FROM oms_pdd_order_mirrors"))
    await session.execute(text("DELETE FROM oms_taobao_order_mirrors"))
    await session.execute(text("DELETE FROM oms_jd_order_mirrors"))
    await session.commit()


async def _create_published_fsku(session, *, code: str, name: str) -> int:
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
                  'single',
                  'published',
                  CAST(:expr AS text),
                  upper(CAST(:expr AS text)),
                  'DIRECT',
                  0,
                  now(),
                  now(),
                  now()
                )
                RETURNING id
                """
            ),
            {"code": code, "name": name, "expr": code},
        )
    ).mappings().one()
    return int(row["id"])


async def _create_pdd_mirror_with_lines(
    session,
    *,
    store_code: str,
    order_no: str,
    bound_code: str,
    unbound_code: str,
) -> None:
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
                  platform_status,
                  last_synced_at
                )
                VALUES (
                  :collector_order_id,
                  :collector_store_id,
                  :store_code,
                  'PDD 编码映射测试店铺',
                  :order_no,
                  'WAIT_SELLER_SEND_GOODS',
                  now()
                )
                RETURNING id
                """
            ),
            {
                "collector_order_id": 810000000 + (uuid4().int % 1000000),
                "collector_store_id": 820000000 + (uuid4().int % 1000000),
                "store_code": store_code,
                "order_no": order_no,
            },
        )
    ).mappings().one()

    mirror_id = int(mirror["id"])

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
            VALUES
              (:mirror_id, :line1, :order_id, :order_no, :bound_code, 'PDD-ITEM-1', 'PDD-SKU-1', '已映射商品', 2, 86.00),
              (:mirror_id, :line2, :order_id, :order_no, :unbound_code, 'PDD-ITEM-2', 'PDD-SKU-2', '未映射商品', 1, 43.00),
              (:mirror_id, :line3, :order_id, :order_no, NULL, 'PDD-ITEM-3', 'PDD-SKU-3', '缺少商家编码商品', 1, 12.00)
            """
        ),
        {
            "mirror_id": mirror_id,
            "line1": 910000000 + (uuid4().int % 1000000),
            "line2": 920000000 + (uuid4().int % 1000000),
            "line3": 930000000 + (uuid4().int % 1000000),
            "order_id": 810000000 + (uuid4().int % 1000000),
            "order_no": order_no,
            "bound_code": bound_code,
            "unbound_code": unbound_code,
        },
    )

    await session.commit()


async def test_pdd_code_mapping_options_return_distinct_platform_codes(client, session) -> None:
    await _clear_rows(session)

    suffix = uuid4().hex[:8]
    store_code = f"PDD-CODE-MAP-{suffix}"
    bound_code = f"PDD-CODE-BOUND-{suffix}"
    unbound_code = f"PDD-CODE-UNBOUND-{suffix}"

    fsku_id = await _create_published_fsku(
        session,
        code=f"FSKU-CODE-MAP-{suffix}",
        name="编码映射测试 FSKU",
    )
    await _create_pdd_mirror_with_lines(
        session,
        store_code=store_code,
        order_no=f"PDD-CODE-MAP-ORDER-{suffix}",
        bound_code=bound_code,
        unbound_code=unbound_code,
    )

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
              'merchant_code',
              :merchant_code,
              :fsku_id,
              'code mapping option test',
              now(),
              now()
            )
            """
        ),
        {
            "store_code": store_code,
            "merchant_code": bound_code,
            "fsku_id": fsku_id,
        },
    )
    await session.commit()

    resp = await client.get(
        "/oms/pdd/code-mapping/code-options",
        params={"store_code": store_code},
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["total"] == 2

    by_code = {row["merchant_code"]: row for row in data["items"]}

    bound = by_code[bound_code]
    assert bound["platform"] == "PDD"
    assert bound["store_code"] == store_code
    assert bound["is_bound"] is True
    assert bound["fsku_id"] == fsku_id
    assert bound["fsku_code"] == f"FSKU-CODE-MAP-{suffix}"
    assert bound["fsku_name"] == "编码映射测试 FSKU"
    assert bound["orders_count"] == 1

    unbound = by_code[unbound_code]
    assert unbound["is_bound"] is False
    assert unbound["fsku_id"] is None


async def test_pdd_code_mapping_options_filter_only_unbound(client, session) -> None:
    await _clear_rows(session)

    suffix = uuid4().hex[:8]
    store_code = f"PDD-CODE-MAP-FILTER-{suffix}"
    bound_code = f"PDD-CODE-BOUND-FILTER-{suffix}"
    unbound_code = f"PDD-CODE-UNBOUND-FILTER-{suffix}"

    fsku_id = await _create_published_fsku(
        session,
        code=f"FSKU-CODE-MAP-FILTER-{suffix}",
        name="编码映射过滤 FSKU",
    )
    await _create_pdd_mirror_with_lines(
        session,
        store_code=store_code,
        order_no=f"PDD-CODE-MAP-FILTER-ORDER-{suffix}",
        bound_code=bound_code,
        unbound_code=unbound_code,
    )

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
            VALUES ('PDD', :store_code, 'merchant_code', :merchant_code, :fsku_id, 'code mapping option test', now(), now())
            """
        ),
        {
            "store_code": store_code,
            "merchant_code": bound_code,
            "fsku_id": fsku_id,
        },
    )
    await session.commit()

    resp = await client.get(
        "/oms/pdd/code-mapping/code-options",
        params={"store_code": store_code, "only_unbound": "true"},
    )
    assert resp.status_code == 200, resp.text

    items = resp.json()["data"]["items"]
    assert [row["merchant_code"] for row in items] == [unbound_code]
    assert items[0]["is_bound"] is False


async def test_code_mapping_options_are_platform_separated(client, session) -> None:
    await _clear_rows(session)

    suffix = uuid4().hex[:8]
    store_code = f"PDD-CODE-MAP-ISO-{suffix}"
    await _create_pdd_mirror_with_lines(
        session,
        store_code=store_code,
        order_no=f"PDD-CODE-MAP-ISO-ORDER-{suffix}",
        bound_code=f"PDD-CODE-BOUND-ISO-{suffix}",
        unbound_code=f"PDD-CODE-UNBOUND-ISO-{suffix}",
    )

    pdd_resp = await client.get(
        "/oms/pdd/code-mapping/code-options",
        params={"store_code": store_code},
    )
    assert pdd_resp.status_code == 200, pdd_resp.text
    assert pdd_resp.json()["data"]["total"] == 2

    taobao_resp = await client.get(
        "/oms/taobao/code-mapping/code-options",
        params={"store_code": store_code},
    )
    assert taobao_resp.status_code == 200, taobao_resp.text
    assert taobao_resp.json()["data"]["total"] == 0
