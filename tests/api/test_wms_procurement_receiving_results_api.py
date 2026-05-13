from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.wms.inbound.contracts.procurement_receiving_result import (
    ProcurementReceivingResultDetailOut,
    ProcurementReceivingResultLineOut,
    ProcurementReceivingResultsOut,
)
from app.wms.inbound.routers import inbound_events as router_module


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router_module.router)
    return TestClient(app)


def _line(event_id: int = 34) -> ProcurementReceivingResultLineOut:
    return ProcurementReceivingResultLineOut(
        wms_event_id=event_id,
        wms_event_no="IE-20260513144401-FA957E19",
        trace_id="IN-OP-1092a9a1243d4ae6ab40",
        event_kind="COMMIT",
        event_status="COMMITTED",
        occurred_at=datetime.now(UTC),
        receipt_no="IR-PO-1-20260513141447-A864B3",
        procurement_po_id=1,
        procurement_po_no="PO-LINK-0001",
        wms_event_line_no=1,
        procurement_po_line_id=1,
        warehouse_id=2,
        item_id=4002,
        qty_delta_base=3,
        lot_code_input="PO-LINK-LOT-0001",
        production_date=None,
        expiry_date=None,
        lot_id=79,
    )


def test_procurement_receiving_results_route_returns_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_list_results(
        _session: object,
        *,
        after_event_id: int | None = 0,
        limit: int | None = 50,
        procurement_po_id: int | None = None,
        receipt_no: str | None = None,
    ) -> ProcurementReceivingResultsOut:
        captured["after_event_id"] = after_event_id
        captured["limit"] = limit
        captured["procurement_po_id"] = procurement_po_id
        captured["receipt_no"] = receipt_no

        return ProcurementReceivingResultsOut(
            items=[_line()],
            after_event_id=int(after_event_id or 0),
            next_after_event_id=34,
            limit=int(limit or 50),
            has_more=False,
        )

    monkeypatch.setattr(
        router_module,
        "list_procurement_receiving_results",
        fake_list_results,
    )

    response = _client().get(
        "/wms/inbound/procurement-receiving-results",
        params={
            "after_event_id": 10,
            "limit": 20,
            "procurement_po_id": 1,
            "receipt_no": "IR-PO-1-20260513141447-A864B3",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert captured == {
        "after_event_id": 10,
        "limit": 20,
        "procurement_po_id": 1,
        "receipt_no": "IR-PO-1-20260513141447-A864B3",
    }
    assert body["items"][0]["procurement_po_id"] == 1
    assert body["items"][0]["procurement_po_line_id"] == 1
    assert body["items"][0]["qty_delta_base"] == 3
    assert body["next_after_event_id"] == 34


def test_procurement_receiving_result_detail_route_returns_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, int] = {}

    async def fake_get_result_detail(
        _session: object,
        *,
        event_id: int,
    ) -> ProcurementReceivingResultDetailOut:
        captured["event_id"] = event_id
        return ProcurementReceivingResultDetailOut(
            event_id=event_id,
            items=[_line(event_id=event_id)],
        )

    monkeypatch.setattr(
        router_module,
        "get_procurement_receiving_result_detail",
        fake_get_result_detail,
    )

    response = _client().get("/wms/inbound/procurement-receiving-results/34")

    assert response.status_code == 200
    body = response.json()

    assert captured["event_id"] == 34
    assert body["event_id"] == 34
    assert body["items"][0]["receipt_no"] == "IR-PO-1-20260513141447-A864B3"
