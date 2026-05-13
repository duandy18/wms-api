from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from app.integrations.procurement.factory import create_procurement_read_client
from app.integrations.procurement.http_client import (
    HttpProcurementReadClient,
    ProcurementReadClientError,
)


def _json_response(payload: object, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        headers={"content-type": "application/json"},
        content=json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
    )


@pytest.mark.asyncio
async def test_list_purchase_order_source_options_calls_procurement_read_api() -> None:
    captured: dict[str, object] = {}
    now = datetime.now(UTC).isoformat()

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["params"] = dict(request.url.params)

        return _json_response(
            {
                "items": [
                    {
                        "po_id": 1,
                        "po_no": "PO-1",
                        "target_warehouse_id": 2,
                        "target_warehouse_code_snapshot": "WH-2",
                        "target_warehouse_name_snapshot": "二号仓",
                        "supplier_id": 10,
                        "supplier_code_snapshot": "SUP-10",
                        "supplier_name_snapshot": "供应商快照",
                        "purchase_time": now,
                        "order_status": "CREATED",
                        "completion_status": "PARTIAL",
                        "last_received_at": now,
                    }
                ]
            }
        )

    client = HttpProcurementReadClient(
        base_url="http://procurement.test",
        transport=httpx.MockTransport(handler),
    )

    result = await client.list_purchase_order_source_options(
        target_warehouse_id=2,
        q="SUP",
        limit=20,
    )

    assert captured["url"] == (
        "http://procurement.test/procurement/read/v1/purchase-orders/"
        "source-options?limit=20&target_warehouse_id=2&q=SUP"
    )
    assert captured["params"] == {
        "limit": "20",
        "target_warehouse_id": "2",
        "q": "SUP",
    }
    assert result.items[0].po_id == 1
    assert result.items[0].supplier_name_snapshot == "供应商快照"
    assert result.items[0].completion_status == "PARTIAL"


@pytest.mark.asyncio
async def test_get_purchase_order_calls_procurement_read_api_and_parses_lines() -> None:
    captured: dict[str, str] = {}
    now = datetime.now(UTC).isoformat()

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)

        return _json_response(
            {
                "id": 7,
                "po_no": "PO-7",
                "supplier_id": 10,
                "supplier_code_snapshot": "SUP-10",
                "supplier_name_snapshot": "供应商快照",
                "target_warehouse_id": 2,
                "target_warehouse_code_snapshot": "WH-2",
                "target_warehouse_name_snapshot": "二号仓",
                "purchaser": "Andy",
                "purchase_time": now,
                "status": "CREATED",
                "total_amount": "20.00",
                "remark": None,
                "created_at": now,
                "updated_at": now,
                "closed_at": None,
                "canceled_at": None,
                "editable": False,
                "edit_block_reason": None,
                "lines": [
                    {
                        "id": 70,
                        "po_id": 7,
                        "line_no": 1,
                        "item_id": 3001,
                        "item_sku_snapshot": "SKU-3001",
                        "item_name_snapshot": "测试商品",
                        "spec_text_snapshot": "规格",
                        "purchase_uom_id_snapshot": 11,
                        "purchase_uom_name_snapshot": "箱",
                        "purchase_ratio_to_base_snapshot": 12,
                        "qty_ordered_input": "2.000",
                        "qty_ordered_base": 24,
                        "supply_price": "10.50",
                        "discount_amount": "1.00",
                        "line_amount": "20.00",
                        "remark": None,
                        "created_at": now,
                        "updated_at": now,
                    }
                ],
            }
        )

    client = HttpProcurementReadClient(
        base_url="http://procurement.test/",
        transport=httpx.MockTransport(handler),
    )

    result = await client.get_purchase_order(7)

    assert captured["url"] == "http://procurement.test/procurement/read/v1/purchase-orders/7"
    assert result.id == 7
    assert result.total_amount == Decimal("20.00")
    assert result.lines[0].qty_ordered_base == 24


@pytest.mark.asyncio
async def test_procurement_read_client_raises_on_error_status() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response({"detail": "not found"}, status_code=404)

    client = HttpProcurementReadClient(
        base_url="http://procurement.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProcurementReadClientError):
        await client.get_purchase_order(404)


def test_factory_uses_explicit_base_url() -> None:
    client = create_procurement_read_client(base_url="http://procurement.example")

    assert isinstance(client, HttpProcurementReadClient)
