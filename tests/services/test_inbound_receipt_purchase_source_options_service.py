from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.integrations.procurement.contracts import (
    ProcurementPurchaseOrderSourceOptionOut,
    ProcurementPurchaseOrderSourceOptionsOut,
)
import app.wms.inventory_adjustment.return_inbound.services.purchase_source_options_service as service_module


class FakeProcurementReadClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def list_purchase_order_source_options(
        self,
        *,
        target_warehouse_id: int | None = None,
        q: str | None = None,
        limit: int = 200,
    ) -> ProcurementPurchaseOrderSourceOptionsOut:
        self.calls.append(
            {
                "target_warehouse_id": target_warehouse_id,
                "q": q,
                "limit": limit,
            }
        )
        now = datetime.now(UTC)

        return ProcurementPurchaseOrderSourceOptionsOut(
            items=[
                ProcurementPurchaseOrderSourceOptionOut(
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


@pytest.mark.asyncio
async def test_list_purchase_source_options_maps_procurement_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeProcurementReadClient()
    monkeypatch.setattr(
        service_module,
        "create_procurement_read_client",
        lambda: fake_client,
    )

    result = await service_module.list_inbound_receipt_purchase_source_options(
        target_warehouse_id=2,
        q="SUP",
        limit=20,
    )

    assert fake_client.calls == [
        {
            "target_warehouse_id": 2,
            "q": "SUP",
            "limit": 20,
        }
    ]
    assert len(result.items) == 1
    assert result.items[0].po_id == 1
    assert result.items[0].target_warehouse_id == 2
    assert result.items[0].supplier_code_snapshot == "SUP-10"
    assert result.items[0].supplier_name_snapshot == "供应商快照"
    assert result.items[0].completion_status == "PARTIAL"
