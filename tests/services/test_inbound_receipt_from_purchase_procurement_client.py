from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.wms.inventory_adjustment.return_inbound.contracts.receipt_create_from_purchase import (
    InboundReceiptCreateFromPurchaseIn,
)
from app.wms.inventory_adjustment.return_inbound.contracts.receipt_read import (
    InboundReceiptLineReadOut,
    InboundReceiptReadOut,
)
import app.wms.inventory_adjustment.return_inbound.repos.inbound_receipt_write_repo as repo_module


class FakeMappings:
    def __init__(self, *, first_row: dict[str, Any] | None = None, rows: list[dict[str, Any]] | None = None) -> None:
        self._first_row = first_row
        self._rows = rows or []

    def first(self) -> dict[str, Any] | None:
        return self._first_row

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class FakeResult:
    def __init__(self, *, first_row: dict[str, Any] | None = None, rows: list[dict[str, Any]] | None = None) -> None:
        self._mappings = FakeMappings(first_row=first_row, rows=rows)

    def mappings(self) -> FakeMappings:
        return self._mappings


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> FakeResult:
        sql = str(statement)
        bound = dict(params or {})
        self.calls.append((sql, bound))

        if "FROM inbound_receipts" in sql and "status <> 'VOIDED'" in sql:
            return FakeResult(first_row=None)

        if "INSERT INTO inbound_receipts" in sql:
            return FakeResult(first_row={"id": 101})

        if "INSERT INTO inbound_receipt_lines" in sql:
            return FakeResult(first_row=None)

        raise AssertionError(f"unexpected SQL executed: {sql}")


class FakeProcurementReadClient:
    def __init__(self, order: SimpleNamespace) -> None:
        self.order = order
        self.calls: list[int] = []

    async def get_purchase_order(self, po_id: int) -> SimpleNamespace:
        self.calls.append(int(po_id))
        return self.order


def _line(*, line_id: int, line_no: int) -> SimpleNamespace:
    now = datetime.now(UTC)

    return SimpleNamespace(
        id=line_id,
        po_id=7,
        line_no=line_no,
        item_id=3001,
        item_sku_snapshot="SKU-3001",
        item_name_snapshot="测试商品",
        spec_text_snapshot="规格",
        purchase_uom_id_snapshot=11,
        purchase_uom_name_snapshot="箱",
        purchase_ratio_to_base_snapshot=12,
        qty_ordered_input=Decimal("2"),
        qty_ordered_base=24,
        supply_price=Decimal("10.50"),
        discount_amount=None,
        line_amount=Decimal("21.00"),
        remark="采购行备注",
        created_at=now,
        updated_at=now,
    )


def _order(*, status: str = "CREATED", target_warehouse_id: int = 2) -> SimpleNamespace:
    now = datetime.now(UTC)

    return SimpleNamespace(
        id=7,
        po_no="PO-7",
        supplier_id=10,
        supplier_code_snapshot="SUP-10",
        supplier_name_snapshot="供应商快照",
        target_warehouse_id=target_warehouse_id,
        target_warehouse_code_snapshot="WH-2",
        target_warehouse_name_snapshot="二号仓",
        purchaser="Andy",
        purchase_time=now,
        status=status,
        total_amount=Decimal("21.00"),
        remark="采购备注",
        created_at=now,
        updated_at=now,
        closed_at=None,
        canceled_at=None,
        editable=False,
        edit_block_reason=None,
        lines=[_line(line_id=70, line_no=1)],
    )


def _receipt_out() -> InboundReceiptReadOut:
    return InboundReceiptReadOut(
        id=101,
        receipt_no="IR-PO-7-TEST",
        source_type="PURCHASE_ORDER",
        source_doc_id=7,
        source_doc_no_snapshot="PO-7",
        warehouse_id=2,
        warehouse_name_snapshot="二号仓",
        supplier_id=10,
        counterparty_name_snapshot="供应商快照",
        status="DRAFT",
        remark="采购备注",
        created_by=None,
        released_at=None,
        lines=[
            InboundReceiptLineReadOut(
                id=201,
                line_no=1,
                source_line_id=70,
                item_id=3001,
                item_uom_id=11,
                planned_qty=2,
                item_name_snapshot="测试商品",
                item_spec_snapshot="规格",
                uom_name_snapshot="箱",
                ratio_to_base_snapshot=12,
                remark="采购行备注",
            )
        ],
    )


@pytest.mark.asyncio
async def test_from_purchase_uses_procurement_read_client_not_local_purchase_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = FakeSession()
    fake_client = FakeProcurementReadClient(_order())

    monkeypatch.setattr(repo_module, "create_procurement_read_client", lambda: fake_client)

    async def fake_warehouse_name(_session: object, *, warehouse_id: int) -> str:
        assert warehouse_id == 2
        return "二号仓"

    async def fake_get_receipt(_session: object, *, receipt_id: int) -> InboundReceiptReadOut:
        assert receipt_id == 101
        return _receipt_out()

    monkeypatch.setattr(repo_module, "_load_warehouse_name_snapshot", fake_warehouse_name)
    monkeypatch.setattr(repo_module, "get_inbound_receipt_repo", fake_get_receipt)

    result = await repo_module.create_inbound_receipt_from_purchase_repo(
        fake_session,  # type: ignore[arg-type]
        payload=InboundReceiptCreateFromPurchaseIn(
            source_doc_id=7,
            warehouse_id=2,
            remark=None,
        ),
        created_by=None,
    )

    executed_sql = "\n".join(sql for sql, _params in fake_session.calls)

    assert fake_client.calls == [7]
    assert "FROM purchase_orders" not in executed_sql
    assert "FROM purchase_order_lines" not in executed_sql
    assert result.source_doc_id == 7
    assert result.counterparty_name_snapshot == "供应商快照"

    header_params = next(params for sql, params in fake_session.calls if "INSERT INTO inbound_receipts" in sql)
    assert header_params["source_doc_no_snapshot"] == "PO-7"
    assert header_params["supplier_id"] == 10
    assert header_params["counterparty_name_snapshot"] == "供应商快照"

    line_params = next(params for sql, params in fake_session.calls if "INSERT INTO inbound_receipt_lines" in sql)
    assert line_params["source_line_id"] == 70
    assert line_params["item_id"] == 3001
    assert line_params["item_uom_id"] == 11
    assert line_params["planned_qty"] == 2


@pytest.mark.asyncio
async def test_from_purchase_rejects_warehouse_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = FakeSession()
    fake_client = FakeProcurementReadClient(_order(target_warehouse_id=99))
    monkeypatch.setattr(repo_module, "create_procurement_read_client", lambda: fake_client)

    with pytest.raises(HTTPException) as exc:
        await repo_module.create_inbound_receipt_from_purchase_repo(
            fake_session,  # type: ignore[arg-type]
            payload=InboundReceiptCreateFromPurchaseIn(
                source_doc_id=7,
                warehouse_id=2,
                remark=None,
            ),
            created_by=None,
        )

    assert exc.value.status_code == 409
    assert str(exc.value.detail).startswith("purchase_order_warehouse_mismatch:")


@pytest.mark.asyncio
async def test_from_purchase_rejects_non_integer_planned_qty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order = _order()
    order.lines[0].qty_ordered_input = Decimal("2.500")

    fake_session = FakeSession()
    fake_client = FakeProcurementReadClient(order)
    monkeypatch.setattr(repo_module, "create_procurement_read_client", lambda: fake_client)

    async def fake_warehouse_name(_session: object, *, warehouse_id: int) -> str:
        return f"WH-{warehouse_id}"

    monkeypatch.setattr(repo_module, "_load_warehouse_name_snapshot", fake_warehouse_name)

    with pytest.raises(HTTPException) as exc:
        await repo_module.create_inbound_receipt_from_purchase_repo(
            fake_session,  # type: ignore[arg-type]
            payload=InboundReceiptCreateFromPurchaseIn(
                source_doc_id=7,
                warehouse_id=2,
                remark=None,
            ),
            created_by=None,
        )

    assert exc.value.status_code == 409
    assert str(exc.value.detail).startswith("purchase_order_line_qty_ordered_input:")
