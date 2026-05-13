# tests/api/test_purchase_order_detail_editability_api.py
from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

import httpx
import pytest
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


async def _create_po_one_line(
    session: AsyncSession,
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    *,
    item_id: int,
) -> Dict[str, Any]:
    uom_id = await _pick_any_uom_id(session, item_id=int(item_id))
    payload = {
        "warehouse_id": 1,
        "supplier_id": 1,
        "purchaser": "UT",
        "purchase_time": "2026-01-14T10:00:00Z",
        "lines": [
            {"line_no": 1, "item_id": int(item_id), "uom_id": int(uom_id), "qty_input": 2},
        ],
    }
    r = await client.post("/purchase-orders/", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, dict), data
    return data


async def _commit_purchase_inbound(
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    *,
    po: Dict[str, Any],
    uom_id: int,
) -> Dict[str, Any]:
    po_no = str(po["po_no"])
    line = po["lines"][0]

    payload = {
        "warehouse_id": 1,
        "source_type": "PURCHASE_ORDER",
        "source_ref": po_no,
        "occurred_at": "2026-01-14T10:30:00Z",
        "remark": f"editability test for po_no={po_no}",
        "lines": [
            {
                "item_id": int(line["item_id"]),
                "uom_id": int(uom_id),
                "qty_input": 1,
                "source_line_id": int(line["id"]),
            },
        ],
    }

    r = await client.post("/wms/inbound/commit", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    out = r.json()
    assert isinstance(out, dict), out
    assert int(out.get("event_id") or 0) > 0, out
    return out


@pytest.mark.asyncio
async def test_purchase_order_detail_returns_editable_true_when_clean(
    client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)

    item_id = await _insert_item_internal_none(session, sku_prefix="UT-EDITABLE-CLEAN")
    await session.commit()

    po = await _create_po_one_line(session, client, headers, item_id=int(item_id))
    po_id = int(po["id"])

    r = await client.get(f"/purchase-orders/{po_id}", headers=headers)
    assert r.status_code == 200, r.text
    detail = r.json()

    assert detail["editable"] is True, detail
    assert detail["edit_block_reason"] is None, detail


@pytest.mark.asyncio
async def test_purchase_order_detail_returns_not_editable_when_committed_inbound_exists(
    client: httpx.AsyncClient,
    session: AsyncSession,
) -> None:
    headers = await _login_admin_headers(client)

    item_id = await _insert_item_internal_none(session, sku_prefix="UT-EDITABLE-COMMIT")
    await session.commit()

    po = await _create_po_one_line(session, client, headers, item_id=int(item_id))
    po_id = int(po["id"])
    uom_id = await _pick_any_uom_id(session, item_id=int(item_id))

    await _commit_purchase_inbound(client, headers, po=po, uom_id=int(uom_id))

    r = await client.get(f"/purchase-orders/{po_id}", headers=headers)
    assert r.status_code == 200, r.text
    detail = r.json()

    assert detail["editable"] is False, detail
    assert "正式采购入库事实" in str(detail["edit_block_reason"] or ""), detail
