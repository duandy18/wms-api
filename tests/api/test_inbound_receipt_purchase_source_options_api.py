from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.integrations.procurement.http_client import ProcurementReadClientError
from app.wms.inventory_adjustment.return_inbound.contracts.purchase_source_options import (
    InboundReceiptPurchaseSourceOptionOut,
    InboundReceiptPurchaseSourceOptionsOut,
)
from app.wms.inventory_adjustment.return_inbound.routers import inbound_receipts as router_module


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router_module.router)
    return TestClient(app)


def _source_options() -> InboundReceiptPurchaseSourceOptionsOut:
    now = datetime.now(UTC)

    return InboundReceiptPurchaseSourceOptionsOut(
        items=[
            InboundReceiptPurchaseSourceOptionOut(
                po_id=1,
                po_no="PO-1",
                target_warehouse_id=2,
                target_warehouse_code_snapshot="WH-2",
                target_warehouse_name_snapshot="二号仓",
                supplier_id=10,
                supplier_code_snapshot="SUP-10",
                supplier_name_snapshot="供应商快照",
                purchase_time=now,
                order_status="CREATED",
                completion_status="PARTIAL",
                last_received_at=now,
            )
        ]
    )


def test_purchase_source_options_route_returns_bff_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_list_source_options(
        *,
        target_warehouse_id: int | None = None,
        q: str | None = None,
        limit: int = 200,
    ) -> InboundReceiptPurchaseSourceOptionsOut:
        captured["target_warehouse_id"] = target_warehouse_id
        captured["q"] = q
        captured["limit"] = limit
        return _source_options()

    monkeypatch.setattr(
        router_module,
        "list_inbound_receipt_purchase_source_options",
        fake_list_source_options,
    )

    response = _client().get(
        "/inbound-receipts/purchase-source-options",
        params={
            "target_warehouse_id": 2,
            "q": "SUP",
            "limit": 20,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert captured == {
        "target_warehouse_id": 2,
        "q": "SUP",
        "limit": 20,
    }
    assert body["items"][0]["po_id"] == 1
    assert body["items"][0]["supplier_name_snapshot"] == "供应商快照"


def test_purchase_source_options_route_is_not_captured_by_receipt_id_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_source_options(
        *,
        target_warehouse_id: int | None = None,
        q: str | None = None,
        limit: int = 200,
    ) -> InboundReceiptPurchaseSourceOptionsOut:
        return InboundReceiptPurchaseSourceOptionsOut(items=[])

    monkeypatch.setattr(
        router_module,
        "list_inbound_receipt_purchase_source_options",
        fake_list_source_options,
    )

    response = _client().get("/inbound-receipts/purchase-source-options")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_purchase_source_options_route_maps_procurement_error_to_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_source_options(
        *,
        target_warehouse_id: int | None = None,
        q: str | None = None,
        limit: int = 200,
    ) -> InboundReceiptPurchaseSourceOptionsOut:
        raise ProcurementReadClientError("upstream failed")

    monkeypatch.setattr(
        router_module,
        "list_inbound_receipt_purchase_source_options",
        fake_list_source_options,
    )

    response = _client().get("/inbound-receipts/purchase-source-options")

    assert response.status_code == 502
    assert response.json() == {"detail": "upstream failed"}
