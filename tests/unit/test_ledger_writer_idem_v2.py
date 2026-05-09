from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.ledger.services.ledger_writer import write_ledger
from app.wms.stock.services.lots import ensure_lot_full
from tests.utils.ensure_minimal import ensure_item

UTC = timezone.utc


@pytest.mark.asyncio
async def test_write_ledger_idempotent(session: AsyncSession):
    # 确保基础主数据存在
    await session.execute(
        text("INSERT INTO warehouses (id, name) VALUES (1, 'WH-1') ON CONFLICT (id) DO NOTHING")
    )
    await ensure_item(session, id=3003, sku="SKU-3003", name="ITEM-3003", expiry_required=True)

    prod = date.today()
    exp = prod + timedelta(days=365)

    # 终态：lot 创建必须走 ensure_lot_full（禁止 tests 直接 INSERT INTO lots）
    lot_id = await ensure_lot_full(
        session,
        item_id=3003,
        warehouse_id=1,
        lot_code="IDEM",
        production_date=prod,
        expiry_date=exp,
    )

    # 本测试只验证 ledger writer 的幂等，不验证库存余额变更。
    # make test 的后置 seed-opening-ledger-test 会检查 Σledger == stocks_lot，
    # 因此这里必须清理本测试直接写入的 ledger 行，避免污染测试库三账一致性。
    try:
        id1 = await write_ledger(
            session,
            warehouse_id=1,
            item_id=3003,
            reason="COUNT",
            delta=1,
            after_qty=6,
            ref="LED-IDEM-1",
            ref_line=1,
            occurred_at=datetime.now(UTC),
            lot_id=int(lot_id),
        )
        assert id1 > 0

        id2 = await write_ledger(
            session,
            warehouse_id=1,
            item_id=3003,
            reason="COUNT",
            delta=1,
            after_qty=6,
            ref="LED-IDEM-1",
            ref_line=1,
            occurred_at=datetime.now(UTC),
            lot_id=int(lot_id),
        )
        assert id2 == 0
    finally:
        await session.execute(text("DELETE FROM stock_ledger WHERE ref = 'LED-IDEM-1'"))
        await session.flush()
