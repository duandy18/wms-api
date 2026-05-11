from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
import pytest
from pytest import MonkeyPatch
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import ItemBasic, PmsExportUom


async def _headers(client: httpx.AsyncClient) -> dict[str, str]:
    login = await client.post(
        "/users/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _pick_supplier_item(session: AsyncSession) -> int:
    row = (
        await session.execute(
            text(
                """
                SELECT i.id
                  FROM items i
                  JOIN item_uoms u
                    ON u.item_id = i.id
                   AND (u.is_purchase_default IS TRUE OR u.is_base IS TRUE)
                 WHERE i.supplier_id = 1
                   AND i.enabled IS TRUE
                 ORDER BY i.id ASC
                 LIMIT 1
                """
            )
        )
    ).first()
    assert row is not None, "expected seeded enabled supplier item with purchase/base uom"
    return int(row[0])


async def _pick_purchase_uom(session: AsyncSession, *, item_id: int) -> tuple[int, int]:
    row = (
        await session.execute(
            text(
                """
                SELECT id, ratio_to_base
                  FROM item_uoms
                 WHERE item_id = :item_id
                 ORDER BY is_purchase_default DESC, is_base DESC, id ASC
                 LIMIT 1
                """
            ),
            {"item_id": int(item_id)},
        )
    ).mappings().first()
    assert row is not None
    return int(row["id"]), int(row["ratio_to_base"])


async def _load_item_basic(session: AsyncSession, *, item_id: int) -> ItemBasic:
    row = (
        await session.execute(
            text(
                """
                SELECT
                    i.id,
                    i.sku,
                    i.name,
                    i.spec,
                    i.enabled,
                    i.supplier_id,
                    b.name_cn AS brand,
                    c.category_name AS category
                  FROM items i
             LEFT JOIN pms_brands b
                    ON b.id = i.brand_id
             LEFT JOIN pms_business_categories c
                    ON c.id = i.category_id
                 WHERE i.id = :item_id
                 LIMIT 1
                """
            ),
            {"item_id": int(item_id)},
        )
    ).mappings().first()
    assert row is not None

    return ItemBasic(
        id=int(row["id"]),
        sku=str(row["sku"]),
        name=str(row["name"]),
        spec=(str(row["spec"]) if row["spec"] is not None else None),
        enabled=bool(row["enabled"]),
        supplier_id=(int(row["supplier_id"]) if row["supplier_id"] is not None else None),
        brand=(str(row["brand"]) if row["brand"] is not None else None),
        category=(str(row["category"]) if row["category"] is not None else None),
    )


async def _load_uom(session: AsyncSession, *, item_uom_id: int) -> PmsExportUom:
    row = (
        await session.execute(
            text(
                """
                SELECT
                    id,
                    item_id,
                    uom,
                    display_name,
                    COALESCE(NULLIF(display_name, ''), uom) AS uom_name,
                    ratio_to_base,
                    net_weight_kg,
                    is_base,
                    is_purchase_default,
                    is_inbound_default,
                    is_outbound_default
                  FROM item_uoms
                 WHERE id = :item_uom_id
                 LIMIT 1
                """
            ),
            {"item_uom_id": int(item_uom_id)},
        )
    ).mappings().first()
    assert row is not None

    return PmsExportUom(
        id=int(row["id"]),
        item_id=int(row["item_id"]),
        uom=str(row["uom"]),
        display_name=(str(row["display_name"]) if row["display_name"] is not None else None),
        uom_name=str(row["uom_name"]),
        ratio_to_base=int(row["ratio_to_base"]),
        net_weight_kg=(
            float(row["net_weight_kg"]) if row["net_weight_kg"] is not None else None
        ),
        is_base=bool(row["is_base"]),
        is_purchase_default=bool(row["is_purchase_default"]),
        is_inbound_default=bool(row["is_inbound_default"]),
        is_outbound_default=bool(row["is_outbound_default"]),
    )


class _FakePmsReadClient:
    def __init__(
        self,
        *,
        items_by_id: dict[int, ItemBasic],
        uoms_by_id: dict[int, PmsExportUom],
    ) -> None:
        self._items_by_id = items_by_id
        self._uoms_by_id = uoms_by_id

    async def get_item_basics(self, *, item_ids: list[int]) -> dict[int, ItemBasic]:
        return {
            int(item_id): self._items_by_id[int(item_id)]
            for item_id in item_ids
            if int(item_id) in self._items_by_id
        }

    async def get_item_basic(self, *, item_id: int) -> ItemBasic | None:
        return self._items_by_id.get(int(item_id))

    async def get_uom(self, *, item_uom_id: int) -> PmsExportUom | None:
        return self._uoms_by_id.get(int(item_uom_id))


def _patch_pms_read_client(
    monkeypatch: MonkeyPatch,
    *,
    items_by_id: dict[int, ItemBasic],
    uoms_by_id: dict[int, PmsExportUom],
) -> None:
    fake = _FakePmsReadClient(items_by_id=items_by_id, uoms_by_id=uoms_by_id)

    def _factory(*args: Any, **kwargs: Any) -> _FakePmsReadClient:
        _ = args
        _ = kwargs
        return fake

    modules = (
        "app.procurement.services.purchase_order_create",
        "app.procurement.repos.purchase_order_create_repo",
        "app.procurement.repos.receive_po_line_repo",
        "app.finance.sources.purchase_cost_source",
    )

    for module_name in modules:
        module = __import__(module_name, fromlist=["dummy"])
        if hasattr(module, "create_pms_read_client"):
            monkeypatch.setattr(module, "create_pms_read_client", _factory)


async def _patch_pms_for_purchase_item(
    monkeypatch: MonkeyPatch,
    session: AsyncSession,
    *,
    item_id: int,
    uom_id: int,
) -> None:
    item = await _load_item_basic(session, item_id=item_id)
    uom = await _load_uom(session, item_uom_id=uom_id)

    _patch_pms_read_client(
        monkeypatch,
        items_by_id={int(item_id): item},
        uoms_by_id={int(uom_id): uom},
    )


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


@pytest.mark.asyncio
async def test_finance_purchase_sku_ledger_returns_po_line_level_prices_and_accounting_unit_price(
    client: httpx.AsyncClient,
    session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await _headers(client)
    item_id = await _pick_supplier_item(session)
    uom_id, ratio_to_base = await _pick_purchase_uom(session, item_id=item_id)
    await _patch_pms_for_purchase_item(monkeypatch, session, item_id=item_id, uom_id=uom_id)

    payload_1 = {
        "warehouse_id": 1,
        "supplier_id": 1,
        "purchaser": "UT",
        "purchase_time": "2036-01-14T10:00:00Z",
        "lines": [
            {
                "line_no": 1,
                "item_id": item_id,
                "uom_id": uom_id,
                "qty_input": 2,
                "supply_price": "2.50",
            }
        ],
    }
    payload_2 = {
        "warehouse_id": 1,
        "supplier_id": 1,
        "purchaser": "UT",
        "purchase_time": "2036-01-14T12:00:00Z",
        "lines": [
            {
                "line_no": 1,
                "item_id": item_id,
                "uom_id": uom_id,
                "qty_input": 1,
                "supply_price": "3.50",
            }
        ],
    }

    created_1 = await client.post("/purchase-orders/", json=payload_1, headers=headers)
    assert created_1.status_code == 200, created_1.text
    po_1 = created_1.json()
    po_line_id_1 = int(po_1["lines"][0]["id"])

    created_2 = await client.post("/purchase-orders/", json=payload_2, headers=headers)
    assert created_2.status_code == 200, created_2.text
    po_2 = created_2.json()
    po_line_id_2 = int(po_2["lines"][0]["id"])

    resp = await client.get(
        "/finance/purchase-costs/sku-purchase-ledger?from_date=2036-01-14&to_date=2036-01-14",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert set(body) == {"rows"}
    assert isinstance(body["rows"], list)

    rows_by_id = {int(row["po_line_id"]): row for row in body["rows"]}
    assert po_line_id_1 in rows_by_id, body
    assert po_line_id_2 in rows_by_id, body

    row_1 = rows_by_id[po_line_id_1]
    row_2 = rows_by_id[po_line_id_2]

    expected_fields = {
        "po_line_id",
        "po_id",
        "po_no",
        "line_no",
        "item_id",
        "item_sku",
        "item_name",
        "spec_text",
        "supplier_id",
        "supplier_name",
        "warehouse_id",
        "warehouse_name",
        "purchase_time",
        "purchase_date",
        "qty_ordered_input",
        "purchase_uom_name_snapshot",
        "purchase_ratio_to_base_snapshot",
        "qty_ordered_base",
        "purchase_unit_price",
        "planned_line_amount",
        "accounting_unit_price",
    }
    assert set(row_1) == expected_fields
    assert set(row_2) == expected_fields

    assert row_1["po_no"] == po_1["po_no"]
    assert row_2["po_no"] == po_2["po_no"]
    assert int(row_1["item_id"]) == item_id
    assert int(row_2["item_id"]) == item_id
    assert int(row_1["supplier_id"]) == 1
    assert int(row_2["supplier_id"]) == 1
    assert int(row_1["warehouse_id"]) == 1
    assert int(row_2["warehouse_id"]) == 1
    assert str(row_1["warehouse_name"]).strip()
    assert str(row_2["warehouse_name"]).strip()
    assert row_1["purchase_date"] == "2036-01-14"
    assert row_2["purchase_date"] == "2036-01-14"

    base_qty_1 = 2 * ratio_to_base
    base_qty_2 = 1 * ratio_to_base

    assert int(row_1["qty_ordered_input"]) == 2
    assert int(row_1["purchase_ratio_to_base_snapshot"]) == ratio_to_base
    assert int(row_1["qty_ordered_base"]) == base_qty_1
    assert _decimal(row_1["purchase_unit_price"]) == Decimal("2.50")
    assert _decimal(row_1["planned_line_amount"]) == Decimal("2.50") * Decimal(base_qty_1)

    assert int(row_2["qty_ordered_input"]) == 1
    assert int(row_2["purchase_ratio_to_base_snapshot"]) == ratio_to_base
    assert int(row_2["qty_ordered_base"]) == base_qty_2
    assert _decimal(row_2["purchase_unit_price"]) == Decimal("3.50")
    assert _decimal(row_2["planned_line_amount"]) == Decimal("3.50") * Decimal(base_qty_2)

    expected_accounting_unit_price = (
        (
            Decimal("2.50") * Decimal(base_qty_1)
            + Decimal("3.50") * Decimal(base_qty_2)
        )
        / Decimal(base_qty_1 + base_qty_2)
    ).quantize(Decimal("0.0001"))

    assert _decimal(row_1["accounting_unit_price"]) == expected_accounting_unit_price
    assert _decimal(row_2["accounting_unit_price"]) == expected_accounting_unit_price

    assert "supply_price" not in row_1
    assert "discount_amount" not in row_1
    assert "discount_note" not in row_1
    assert "discount_amount_snapshot" not in row_1


@pytest.mark.asyncio
async def test_finance_purchase_sku_ledger_filters_by_item_keyword_and_supplier(
    client: httpx.AsyncClient,
    session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await _headers(client)
    item_id = await _pick_supplier_item(session)
    uom_id, _ratio_to_base = await _pick_purchase_uom(session, item_id=item_id)
    await _patch_pms_for_purchase_item(monkeypatch, session, item_id=item_id, uom_id=uom_id)

    payload = {
        "warehouse_id": 1,
        "supplier_id": 1,
        "purchaser": "UT",
        "purchase_time": "2036-01-15T10:00:00Z",
        "lines": [
            {
                "line_no": 1,
                "item_id": item_id,
                "uom_id": uom_id,
                "qty_input": 1,
                "supply_price": "3.00",
            }
        ],
    }

    created = await client.post("/purchase-orders/", json=payload, headers=headers)
    assert created.status_code == 200, created.text
    po_line_id = int(created.json()["lines"][0]["id"])

    resp = await client.get(
        f"/finance/purchase-costs/sku-purchase-ledger"
        f"?from_date=2036-01-15"
        f"&to_date=2036-01-15"
        f"&supplier_id=1"
        f"&warehouse_id=1"
        f"&item_keyword={item_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    rows = resp.json()["rows"]
    assert any(int(row["po_line_id"]) == po_line_id for row in rows), rows


@pytest.mark.asyncio
async def test_finance_purchase_sku_ledger_options_include_items_suppliers_and_warehouses(
    client: httpx.AsyncClient,
    session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await _headers(client)
    item_id = await _pick_supplier_item(session)
    uom_id, _ratio_to_base = await _pick_purchase_uom(session, item_id=item_id)
    await _patch_pms_for_purchase_item(monkeypatch, session, item_id=item_id, uom_id=uom_id)

    payload = {
        "warehouse_id": 1,
        "supplier_id": 1,
        "purchaser": "UT",
        "purchase_time": "2036-01-16T10:00:00Z",
        "lines": [
            {
                "line_no": 1,
                "item_id": item_id,
                "uom_id": uom_id,
                "qty_input": 1,
                "supply_price": "4.00",
            }
        ],
    }

    created = await client.post("/purchase-orders/", json=payload, headers=headers)
    assert created.status_code == 200, created.text

    resp = await client.get(
        "/finance/purchase-costs/sku-purchase-ledger/options",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert set(body) == {"items", "suppliers", "warehouses"}
    assert any(int(row["item_id"]) == item_id for row in body["items"]), body
    assert any(int(row["supplier_id"]) == 1 for row in body["suppliers"]), body
    assert any(int(row["warehouse_id"]) == 1 for row in body["warehouses"]), body


@pytest.mark.asyncio
async def test_finance_purchase_sku_ledger_options_are_cascading(
    client: httpx.AsyncClient,
    session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    headers = await _headers(client)
    item_id = await _pick_supplier_item(session)
    uom_id, _ratio_to_base = await _pick_purchase_uom(session, item_id=item_id)
    await _patch_pms_for_purchase_item(monkeypatch, session, item_id=item_id, uom_id=uom_id)

    payload = {
        "warehouse_id": 1,
        "supplier_id": 1,
        "purchaser": "UT",
        "purchase_time": "2036-01-17T10:00:00Z",
        "lines": [
            {
                "line_no": 1,
                "item_id": item_id,
                "uom_id": uom_id,
                "qty_input": 1,
                "supply_price": "5.00",
            }
        ],
    }

    created = await client.post("/purchase-orders/", json=payload, headers=headers)
    assert created.status_code == 200, created.text

    resp = await client.get(
        f"/finance/purchase-costs/sku-purchase-ledger/options"
        f"?supplier_id=1"
        f"&warehouse_id=1"
        f"&item_keyword={item_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert set(body) == {"items", "suppliers", "warehouses"}

    assert body["items"], body
    assert body["suppliers"], body
    assert body["warehouses"], body

    assert all(int(row["item_id"]) == item_id for row in body["items"]), body
    assert all(int(row["supplier_id"]) == 1 for row in body["suppliers"]), body
    assert all(int(row["warehouse_id"]) == 1 for row in body["warehouses"]), body
