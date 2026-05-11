# tests/fixtures/po_batch_semantics_fixtures.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.procurement.models.purchase_order import PurchaseOrder
from app.procurement.models.purchase_order_line import PurchaseOrderLine


def _is_required_expiry_policy(expiry_policy: str) -> bool:
    return str(expiry_policy or "").strip().upper() == "REQUIRED"


async def _get_any_supplier(session: AsyncSession) -> tuple[int, str]:
    row = await session.execute(text("SELECT id, name FROM suppliers ORDER BY id ASC LIMIT 1"))
    r = row.first()
    if r is None or r[0] is None:
        raise RuntimeError("tests require at least one supplier seeded in test database.")
    sid = int(r[0])
    sname = (str(r[1]).strip() if r[1] is not None else "").strip() or "UNKNOWN SUPPLIER"
    return sid, sname


async def _get_any_warehouse_id(session: AsyncSession) -> int:
    row = await session.execute(text("SELECT id FROM warehouses ORDER BY id ASC LIMIT 1"))
    r = row.first()
    if r is None or r[0] is None:
        raise RuntimeError("tests require at least one warehouse seeded in test database.")
    return int(r[0])


async def _create_test_item(
    session: AsyncSession,
    *,
    supplier_id: int,
    expiry_policy: str,
) -> tuple[int, str, str]:
    exp = str(expiry_policy or "").strip().upper() or "NONE"
    sku = f"UT-SKU-{uuid4().hex[:16]}"
    name = "UT-Item"

    row = (
        await session.execute(
            text(
                """
                INSERT INTO items (
                    name,
                    sku,
                    enabled,
                    supplier_id,
                    lot_source_policy,
                    expiry_policy,
                    derivation_allowed,
                    uom_governance_enabled,
                    shelf_life_value,
                    shelf_life_unit
                )
                VALUES (
                    :name,
                    :sku,
                    TRUE,
                    :supplier_id,
                    CAST('SUPPLIER_ONLY' AS lot_source_policy),
                    CAST(:expiry_policy AS expiry_policy),
                    TRUE,
                    TRUE,
                    :shelf_life_value,
                    CASE
                        WHEN :shelf_life_unit IS NULL THEN NULL
                        ELSE CAST(:shelf_life_unit AS shelf_life_unit)
                    END
                )
                RETURNING id, sku, name
                """
            ),
            {
                "name": name,
                "sku": sku,
                "supplier_id": int(supplier_id),
                "expiry_policy": exp,
                "shelf_life_value": 30 if _is_required_expiry_policy(exp) else None,
                "shelf_life_unit": "DAY" if _is_required_expiry_policy(exp) else None,
            },
        )
    ).first()

    assert row is not None
    return int(row[0]), str(row[1]), str(row[2])


async def _create_base_item_uom(session: AsyncSession, *, item_id: int) -> int:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO item_uoms (
                    item_id,
                    uom,
                    ratio_to_base,
                    display_name,
                    is_base,
                    is_purchase_default,
                    is_inbound_default,
                    is_outbound_default
                )
                VALUES (
                    :item_id,
                    'EA',
                    1,
                    NULL,
                    TRUE,
                    TRUE,
                    TRUE,
                    TRUE
                )
                RETURNING id
                """
            ),
            {"item_id": int(item_id)},
        )
    ).first()

    assert row is not None
    return int(row[0])


async def _create_po_with_one_line(
    session: AsyncSession,
    *,
    expiry_policy: str,
):
    exp = str(expiry_policy or "").strip().upper() or "NONE"

    wid = await _get_any_warehouse_id(session)
    sid, sname = await _get_any_supplier(session)

    item_id, item_sku, item_name = await _create_test_item(
        session,
        supplier_id=sid,
        expiry_policy=exp,
    )
    item_uom_id = await _create_base_item_uom(session, item_id=item_id)

    now = datetime.now(tz=timezone.utc)
    po = PurchaseOrder(
        warehouse_id=wid,
        supplier_id=sid,
        supplier_name=sname,
        purchaser="UT-PURCHASER",
        purchase_time=now,
        status="CREATED",
        total_amount=None,
        remark=None,
        created_at=now,
        updated_at=now,
    )
    session.add(po)
    await session.flush()

    qty_base = 10
    line = PurchaseOrderLine(
        po_id=int(po.id),
        line_no=1,
        item_id=int(item_id),
        item_name=item_name,
        item_sku=item_sku,
        spec_text=None,
        purchase_uom_id_snapshot=int(item_uom_id),
        purchase_ratio_to_base_snapshot=1,
        qty_ordered_input=qty_base,
        qty_ordered_base=qty_base,
        supply_price=None,
        remark=None,
    )
    session.add(line)
    await session.flush()

    await session.refresh(po)
    await session.refresh(line)
    po.lines = [line]
    return po


@pytest.fixture
async def seeded_po_with_one_line_non_shelf_life(async_session: AsyncSession):
    po = await _create_po_with_one_line(async_session, expiry_policy="NONE")
    await async_session.commit()
    return po


@pytest.fixture
async def seeded_po_with_one_line_shelf_life(async_session: AsyncSession):
    po = await _create_po_with_one_line(async_session, expiry_policy="REQUIRED")
    await async_session.commit()
    return po
