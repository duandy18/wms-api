# tests/api/test_purchase_order_detail_base_contract.py
from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.procurement_pms_projection import (
    install_procurement_pms_projection_fake,
    pick_purchase_uom_id,
    seed_purchase_projection_item,
)


async def _login_admin_headers(client: httpx.AsyncClient) -> Dict[str, str]:
    r = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _pick_any_uom_id(session: AsyncSession, *, item_id: int) -> int:
    install_procurement_pms_projection_fake(session)
    return await pick_purchase_uom_id(session, item_id=int(item_id))


async def _insert_item_internal_none(session: AsyncSession, *, sku_prefix: str) -> int:
    seeded = await seed_purchase_projection_item(
        session,
        supplier_id=1,
        sku_prefix=sku_prefix,
        expiry_policy="NONE",
        lot_source_policy="INTERNAL_ONLY",
    )
    return int(seeded["item_id"])


def _assert_po_head_contract(detail: Dict[str, Any]) -> None:
    assert "id" in detail, detail
    assert isinstance(detail["id"], int), detail

    assert "po_no" in detail, detail
    po_no = str(detail.get("po_no") or "").strip()
    assert po_no, detail
    assert po_no.startswith("PO-"), detail

    assert "supplier_id" in detail, detail
    assert "supplier_name" in detail, detail
    assert isinstance(detail["supplier_id"], int), detail
    assert str(detail["supplier_name"]).strip(), detail


def _assert_line_plan_contract(line: Dict[str, Any]) -> None:
    # 计划合同：只看计划字段，不再混入执行态字段
    for k in ("qty_ordered_base", "qty_ordered_input", "purchase_ratio_to_base_snapshot"):
        assert k in line, line
        assert isinstance(line[k], int), line

    ordered_base = int(line["qty_ordered_base"])
    qty_input = int(line["qty_ordered_input"])
    ratio = int(line["purchase_ratio_to_base_snapshot"])

    assert ordered_base >= 0
    assert qty_input > 0
    assert ratio >= 1
    assert ordered_base == qty_input * ratio, line

    assert "qty_received_base" not in line, line
    assert "qty_remaining_base" not in line, line


def _assert_line_snapshot_contract(line: Dict[str, Any]) -> None:
    assert "item_name" in line, line
    assert "item_sku" in line, line

    name = (line.get("item_name") or "").strip()
    sku = (line.get("item_sku") or "").strip()

    assert name, f"item_name must be non-empty (backend-generated snapshot), line={line}"
    assert sku, f"item_sku must be non-empty (backend-generated snapshot), line={line}"


@pytest.mark.asyncio
async def test_purchase_order_detail_plan_contract(
    client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)

    item_id = await _insert_item_internal_none(session, sku_prefix="UT-PLAN-DETAIL")
    await session.commit()

    uom_id = await _pick_any_uom_id(session, item_id=item_id)

    payload = {
        "supplier_id": 1,
        "warehouse_id": 1,
        "purchaser": "UT",
        "purchase_time": "2026-01-14T10:00:00Z",
        "lines": [
            {"line_no": 1, "item_id": int(item_id), "uom_id": int(uom_id), "qty_input": 2},
        ],
    }

    r = await client.post("/purchase-orders/", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    po = r.json()
    assert isinstance(po, dict), po

    po_id = int(po.get("id") or 0)
    assert po_id > 0, po

    r2 = await client.get(f"/purchase-orders/{po_id}", headers=headers)
    assert r2.status_code == 200, r2.text
    detail = r2.json()
    assert isinstance(detail, dict), detail

    _assert_po_head_contract(detail)

    lines = detail.get("lines")
    assert isinstance(lines, list) and lines, detail

    for ln in lines:
        assert isinstance(ln, dict), ln
        _assert_line_plan_contract(ln)
        _assert_line_snapshot_contract(ln)
