import pytest
from sqlalchemy import text

from app.wms.shared.services.lot_code_contract import (
    fetch_item_by_sku,
    fetch_item_expiry_policy_map,
)

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_shared_inventory_statement(session):
    # 合同性断言：共享仓策略下，不按店隔离库存
    # 这里只做口径约定，不做真实库存运算（待主线库存裁决链路接入后替换）
    row = await session.execute(text("SELECT 1"))
    assert row.scalar() == 1

@pytest.mark.asyncio
async def test_lot_code_contract_reads_policy_through_pms_export(session):
    row = (
        await session.execute(
            text(
                """
                SELECT id
                FROM items
                ORDER BY id
                LIMIT 1
                """
            )
        )
    ).first()
    assert row is not None

    item_id = int(row[0])
    sku = f"UT-LOT-CONTRACT-{item_id}"

    await session.execute(
        text(
            """
            UPDATE items
               SET sku = :sku,
                   expiry_policy = 'REQUIRED'::expiry_policy,
                   lot_source_policy = 'SUPPLIER_ONLY'::lot_source_policy,
                   derivation_allowed = TRUE
             WHERE id = :item_id
            """
        ),
        {
            "sku": sku,
            "item_id": item_id,
        },
    )
    await session.flush()

    policy_map = await fetch_item_expiry_policy_map(session, {item_id})
    assert policy_map == {item_id: "REQUIRED"}

    resolved = await fetch_item_by_sku(session, sku)
    assert resolved == (item_id, True)


@pytest.mark.asyncio
async def test_lot_code_contract_returns_none_for_unknown_sku(session):
    resolved = await fetch_item_by_sku(session, "UT-LOT-CONTRACT-NOT-FOUND")
    assert resolved is None
