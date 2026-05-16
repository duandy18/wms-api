# tests/services/test_oms_fulfillment_projection_sync.py
from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.oms.projection_sync import (
    SYNC_VERSION,
    OmsFulfillmentProjectionSyncError,
    sync_oms_fulfillment_projection_once,
)
from app.integrations.oms.service_auth import (
    OMS_SERVICE_CLIENT_HEADER,
    WMS_SERVICE_CLIENT_CODE,
)

pytestmark = pytest.mark.asyncio


async def _clear_projection_tables(session: AsyncSession) -> None:
    await session.execute(text("DELETE FROM wms_oms_fulfillment_component_projection"))
    await session.execute(text("DELETE FROM wms_oms_fulfillment_line_projection"))
    await session.execute(text("DELETE FROM wms_oms_fulfillment_order_projection"))


def _component(
    *,
    component_id: str,
    line_id: str,
    item_id: int,
    required_qty: str,
    sort_order: int,
) -> dict[str, Any]:
    return {
        "ready_component_id": component_id,
        "ready_line_id": line_id,
        "resolved_item_id": item_id,
        "resolved_item_sku_code_id": item_id + 1000,
        "resolved_item_uom_id": item_id + 2000,
        "component_sku_code": f"SKU-{item_id}",
        "sku_code_snapshot": f"SKU-{item_id}",
        "item_name_snapshot": f"商品 {item_id}",
        "uom_snapshot": "件",
        "qty_per_fsku": required_qty,
        "required_qty": required_qty,
        "alloc_unit_price": "1.00",
        "sort_order": sort_order,
    }


def _order(
    *,
    ready_order_id: str,
    source_order_id: int,
    platform: str,
    store_code: str,
    platform_order_no: str,
    line_count: int = 1,
) -> dict[str, Any]:
    lines: list[dict[str, Any]] = []
    for index in range(1, line_count + 1):
        line_id = f"{ready_order_id}:line:{index}"
        lines.append(
            {
                "ready_line_id": line_id,
                "source_line_id": source_order_id * 10 + index,
                "identity_kind": "merchant_code",
                "identity_value": f"MERCHANT-{source_order_id}-{index}",
                "merchant_sku": f"MERCHANT-{source_order_id}-{index}",
                "platform_item_id": f"ITEM-{source_order_id}-{index}",
                "platform_sku_id": f"SKU-{source_order_id}-{index}",
                "platform_goods_name": f"平台商品 {source_order_id}-{index}",
                "platform_sku_name": f"规格 {index}",
                "ordered_qty": str(index),
                "fsku_id": source_order_id * 100 + index,
                "fsku_code": f"FSKU-{source_order_id}-{index}",
                "fsku_name": f"履约商品 {source_order_id}-{index}",
                "fsku_status_snapshot": "published",
                "components": [
                    _component(
                        component_id=f"{line_id}:component:1",
                        line_id=line_id,
                        item_id=source_order_id * 1000 + index,
                        required_qty=str(index * 2),
                        sort_order=1,
                    )
                ],
            }
        )

    return {
        "ready_order_id": ready_order_id,
        "source_order_id": source_order_id,
        "platform": platform,
        "store_code": store_code,
        "store_name": f"{platform.upper()} 测试店",
        "platform_order_no": platform_order_no,
        "platform_status": "WAIT_SELLER_SEND_GOODS",
        "receiver_name": "张三",
        "receiver_phone": "13800000000",
        "receiver_province": "浙江省",
        "receiver_city": "杭州市",
        "receiver_district": "西湖区",
        "receiver_address": "文三路 1 号",
        "receiver_postcode": None,
        "buyer_remark": "买家备注",
        "seller_remark": "卖家备注",
        "ready_status": "READY",
        "ready_at": "2026-05-13T00:00:00Z",
        "source_updated_at": "2026-05-13T00:00:00Z",
        "lines": lines,
    }


def _transport(
    rows: list[dict[str, Any]],
    calls: list[dict[str, Any]],
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        limit = int(request.url.params.get("limit", 200))
        offset = int(request.url.params.get("offset", 0))
        page = rows[offset : offset + limit]
        calls.append(
            {
                "path": request.url.path,
                "params": dict(request.url.params),
                "authorization": request.headers.get("authorization"),
                "service_client": request.headers.get(OMS_SERVICE_CLIENT_HEADER),
            }
        )
        return httpx.Response(
            200,
            json={
                "ok": True,
                "data": {
                    "items": page,
                    "total": len(rows),
                    "limit": limit,
                    "offset": offset,
                },
            },
        )

    return httpx.MockTransport(handler)


async def test_sync_oms_fulfillment_projection_upserts_ready_orders(session: AsyncSession) -> None:
    await _clear_projection_tables(session)

    rows = [
        _order(
            ready_order_id="pdd:9001",
            source_order_id=9001,
            platform="pdd",
            store_code="UT-PDD",
            platform_order_no="PDD-9001",
            line_count=2,
        ),
        _order(
            ready_order_id="taobao:9002",
            source_order_id=9002,
            platform="taobao",
            store_code="UT-TB",
            platform_order_no="TB-9002",
            line_count=1,
        ),
    ]
    calls: list[dict[str, Any]] = []

    result = await sync_oms_fulfillment_projection_once(
        session,
        oms_api_base_url="http://oms-api.test",
        oms_api_token="oms-token-001",
        limit=1,
        transport=_transport(rows, calls),
    )
    await session.flush()

    assert result.fetched == 2
    assert result.upserted_orders == 2
    assert result.upserted_lines == 3
    assert result.upserted_components == 3
    assert result.pages == 2
    assert result.total == 2

    order_row = (
        await session.execute(
            text(
                """
                SELECT
                    ready_order_id,
                    platform,
                    store_code,
                    platform_order_no,
                    line_count,
                    component_count,
                    total_required_qty,
                    source_hash,
                    sync_version
                FROM wms_oms_fulfillment_order_projection
                WHERE ready_order_id = 'pdd:9001'
                """
            )
        )
    ).mappings().one()

    assert order_row["platform"] == "pdd"
    assert order_row["store_code"] == "UT-PDD"
    assert order_row["platform_order_no"] == "PDD-9001"
    assert order_row["line_count"] == 2
    assert order_row["component_count"] == 2
    assert Decimal(str(order_row["total_required_qty"])) == Decimal("6.000000")
    assert order_row["source_hash"]
    assert order_row["sync_version"] == SYNC_VERSION

    line_count = int(
        (
            await session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM wms_oms_fulfillment_line_projection
                    WHERE ready_order_id = 'pdd:9001'
                    """
                )
            )
        ).scalar_one()
    )
    assert line_count == 2

    component_row = (
        await session.execute(
            text(
                """
                SELECT
                    ready_component_id,
                    ready_order_id,
                    resolved_item_id,
                    required_qty,
                    source_hash,
                    sync_version
                FROM wms_oms_fulfillment_component_projection
                WHERE ready_order_id = 'pdd:9001'
                ORDER BY ready_component_id ASC
                LIMIT 1
                """
            )
        )
    ).mappings().one()

    assert component_row["resolved_item_id"] == 9001001
    assert Decimal(str(component_row["required_qty"])) == Decimal("2.000000")
    assert component_row["source_hash"]
    assert component_row["sync_version"] == SYNC_VERSION

    assert [call["path"] for call in calls] == [
        "/oms/read/v1/fulfillment-ready-orders",
        "/oms/read/v1/fulfillment-ready-orders",
    ]
    assert [call["params"]["offset"] for call in calls] == ["0", "1"]
    assert all(call["authorization"] == "Bearer oms-token-001" for call in calls)
    assert {call["service_client"] for call in calls} == {WMS_SERVICE_CLIENT_CODE}


async def test_sync_oms_fulfillment_projection_replaces_stale_children(session: AsyncSession) -> None:
    await _clear_projection_tables(session)

    first_rows = [
        _order(
            ready_order_id="jd:9101",
            source_order_id=9101,
            platform="jd",
            store_code="UT-JD",
            platform_order_no="JD-9101",
            line_count=2,
        )
    ]
    await sync_oms_fulfillment_projection_once(
        session,
        oms_api_base_url="http://oms-api.test",
        oms_api_token="oms-token-001",
        limit=200,
        transport=_transport(first_rows, []),
    )
    await session.flush()

    second_rows = [
        _order(
            ready_order_id="jd:9101",
            source_order_id=9101,
            platform="jd",
            store_code="UT-JD",
            platform_order_no="JD-9101",
            line_count=1,
        )
    ]
    await sync_oms_fulfillment_projection_once(
        session,
        oms_api_base_url="http://oms-api.test",
        oms_api_token="oms-token-001",
        limit=200,
        transport=_transport(second_rows, []),
    )
    await session.flush()

    line_count = int(
        (
            await session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM wms_oms_fulfillment_line_projection
                    WHERE ready_order_id = 'jd:9101'
                    """
                )
            )
        ).scalar_one()
    )
    component_count = int(
        (
            await session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM wms_oms_fulfillment_component_projection
                    WHERE ready_order_id = 'jd:9101'
                    """
                )
            )
        ).scalar_one()
    )

    assert line_count == 1
    assert component_count == 1


async def test_sync_oms_fulfillment_projection_requires_token(session: AsyncSession) -> None:
    await _clear_projection_tables(session)

    with pytest.raises(RuntimeError, match="OMS_API_TOKEN is required"):
        await sync_oms_fulfillment_projection_once(
            session,
            oms_api_base_url="http://oms-api.test",
            oms_api_token="",
            transport=_transport([], []),
        )


async def test_sync_oms_fulfillment_projection_reports_auth_failure(session: AsyncSession) -> None:
    await _clear_projection_tables(session)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "Not authorized."})

    with pytest.raises(OmsFulfillmentProjectionSyncError, match="auth failed"):
        await sync_oms_fulfillment_projection_once(
            session,
            oms_api_base_url="http://oms-api.test",
            oms_api_token="bad-token",
            transport=httpx.MockTransport(handler),
        )
