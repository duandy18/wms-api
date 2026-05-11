from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.stock.services.lots import ensure_lot_full
from app.wms.stock.services.stock_adjust import adjust_lot_impl
from tests.helpers.pms_projection import seed_pms_projection_item_with_base_uom
from tests.helpers.procurement_pms_projection import install_procurement_pms_projection_fake

pytestmark = pytest.mark.asyncio


async def _ensure_min_domain_v2(
    session: AsyncSession,
    *,
    warehouse_id: int = 1,
    item_id: int = 777,
) -> None:
    """
    Phase M-5：lot-world 下确保最小域存在（不再创建/触碰 legacy stocks）。
    - warehouses: id = warehouse_id
    - PMS current-state: wms_pms_*_projection 中的 item/uom/sku-code
    """
    install_procurement_pms_projection_fake(session)

    await session.execute(
        text("INSERT INTO warehouses(id, name) VALUES (:w, :name) ON CONFLICT (id) DO NOTHING"),
        {"w": warehouse_id, "name": f"WH-{warehouse_id}"},
    )

    await seed_pms_projection_item_with_base_uom(
        session,
        item_id=int(item_id),
        item_uom_id=int(item_id),
        sku_code_id=int(item_id),
        sku=f"SKU-{item_id}",
        name=f"ITEM-{item_id}",
        expiry_policy="REQUIRED",
        lot_source_policy="SUPPLIER_ONLY",
        ratio_to_base=1,
        uom="PCS",
        display_name="PCS",
        sync_version="ut-inbound-smoke-projection",
    )

    await session.commit()


async def _qty_lot(session: AsyncSession, *, warehouse_id: int, item_id: int, batch_code: str | None) -> int:
    if batch_code is None:
        r = await session.execute(
            text(
                """
                SELECT COALESCE(qty, 0)
                  FROM stocks_lot
                 WHERE warehouse_id = :w
                   AND item_id = :i
                   AND lot_id IS NULL
                 LIMIT 1
                """
            ),
            {"w": int(warehouse_id), "i": int(item_id)},
        )
        return int(r.scalar_one_or_none() or 0)

    r = await session.execute(
        text(
            """
            SELECT COALESCE(sl.qty, 0)
              FROM stocks_lot sl
              JOIN lots l ON l.id = sl.lot_id
             WHERE sl.warehouse_id = :w
               AND sl.item_id = :i
               AND l.lot_code = :c
             LIMIT 1
            """
        ),
        {"w": int(warehouse_id), "i": int(item_id), "c": str(batch_code)},
    )
    return int(r.scalar_one_or_none() or 0)


async def test_inbound_ledger_snapshot_smoke(session: AsyncSession):
    """
    入库烟雾测试（最小闭环，lot-world 余额 + ledger 一致性）：
    """
    install_procurement_pms_projection_fake(session)

    WH, ITEM, BATCH = 1, 777, "SMOKE-BATCH-001"

    await _ensure_min_domain_v2(session, warehouse_id=WH, item_id=ITEM)

    before = await _qty_lot(session, warehouse_id=WH, item_id=ITEM, batch_code=BATCH)

    production_date = date.today()
    expiry_date = production_date + timedelta(days=30)
    lot_id = await ensure_lot_full(
        session,
        item_id=int(ITEM),
        warehouse_id=int(WH),
        lot_code=str(BATCH),
        production_date=production_date,
        expiry_date=expiry_date,
    )
    await adjust_lot_impl(
        session=session,
        warehouse_id=int(WH),
        item_id=int(ITEM),
        lot_id=int(lot_id),
        delta=5,
        reason="INBOUND",
        ref="SMOKE-INBOUND",
        ref_line=1,
        occurred_at=datetime.now(timezone.utc),
        meta=None,
        lot_code=BATCH,
        production_date=production_date,
        expiry_date=expiry_date,
        trace_id=None,
        utc_now=lambda: datetime.now(timezone.utc),
    )
    await session.commit()

    qty_now = await _qty_lot(session, warehouse_id=WH, item_id=ITEM, batch_code=BATCH)
    assert qty_now == before + 5

    row = (
        await session.execute(
            text(
                """
                SELECT delta, after_qty
                  FROM stock_ledger
                 WHERE ref = 'SMOKE-INBOUND'
                   AND ref_line = 1
                 ORDER BY id DESC
                 LIMIT 1
                """
            )
        )
    ).first()

    assert row is not None
    assert int(row.delta) == 5
    assert int(row.after_qty) == qty_now
