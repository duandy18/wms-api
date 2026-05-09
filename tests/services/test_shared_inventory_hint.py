from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text

from app.wms.inventory_adjustment.count.repos.count_doc_repo import CountDocRepo
from app.wms.stock.services.lot_resolver import LotResolver
from app.wms.stock.services.lots import ensure_lot_full
from app.wms.stock.services.stock_adjust.db_items import item_requires_batch
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

@pytest.mark.asyncio
async def test_lot_resolver_requires_batch_reads_policy_through_pms_export(session):
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
    resolver = LotResolver()

    await session.execute(
        text(
            """
            UPDATE items
               SET expiry_policy = 'REQUIRED'::expiry_policy
             WHERE id = :item_id
            """
        ),
        {"item_id": item_id},
    )
    await session.flush()
    assert await resolver.requires_batch(session, item_id=item_id) is True

    await session.execute(
        text(
            """
            UPDATE items
               SET expiry_policy = 'NONE'::expiry_policy
             WHERE id = :item_id
            """
        ),
        {"item_id": item_id},
    )
    await session.flush()
    assert await resolver.requires_batch(session, item_id=item_id) is False


@pytest.mark.asyncio
async def test_lot_resolver_requires_batch_unknown_item_raises(session):
    resolver = LotResolver()

    with pytest.raises(ValueError, match="item_not_found"):
        await resolver.requires_batch(session, item_id=999999999)

@pytest.mark.asyncio
async def test_stock_adjust_item_requires_batch_reads_policy_through_pms_export(session):
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

    await session.execute(
        text(
            """
            UPDATE items
               SET expiry_policy = 'REQUIRED'::expiry_policy
             WHERE id = :item_id
            """
        ),
        {"item_id": item_id},
    )
    await session.flush()
    assert await item_requires_batch(session, item_id=item_id) is True

    await session.execute(
        text(
            """
            UPDATE items
               SET expiry_policy = 'NONE'::expiry_policy
             WHERE id = :item_id
            """
        ),
        {"item_id": item_id},
    )
    await session.flush()
    assert await item_requires_batch(session, item_id=item_id) is False


@pytest.mark.asyncio
async def test_stock_adjust_item_requires_batch_unknown_item_raises(session):
    with pytest.raises(ValueError, match="item_not_found"):
        await item_requires_batch(session, item_id=999999999)

@pytest.mark.asyncio
async def test_count_doc_repo_reads_base_uom_through_pms_export(session):
    row = (
        await session.execute(
            text(
                """
                SELECT item_id, id, COALESCE(NULLIF(display_name, ''), uom) AS uom_name
                  FROM item_uoms
                 WHERE is_base IS TRUE
                 ORDER BY item_id ASC, id ASC
                 LIMIT 1
                """
            )
        )
    ).mappings().first()
    assert row is not None

    item_id = int(row["item_id"])
    got = await CountDocRepo().get_base_uom_map(session, item_ids=[item_id])

    assert item_id in got
    assert got[item_id]["base_item_uom_id"] == int(row["id"])
    assert got[item_id]["base_uom_name"] == str(row["uom_name"])


@pytest.mark.asyncio
async def test_count_doc_repo_update_line_counts_reads_base_uom_through_pms_export(session):
    item_row = (
        await session.execute(
            text(
                """
                SELECT item_id, id, COALESCE(NULLIF(display_name, ''), uom) AS uom_name
                  FROM item_uoms
                 WHERE is_base IS TRUE
                 ORDER BY item_id ASC, id ASC
                 LIMIT 1
                """
            )
        )
    ).mappings().first()
    assert item_row is not None

    item_id = int(item_row["item_id"])
    repo = CountDocRepo()
    doc = await repo.create_doc(
        session,
        count_no=f"UT-COUNT-{item_id}",
        warehouse_id=1,
        snapshot_at=datetime.now(UTC),
        created_by=None,
        remark="ut count doc repo uom",
    )
    await session.flush()

    line_row = (
        await session.execute(
            text(
                """
                INSERT INTO count_doc_lines (
                  doc_id,
                  line_no,
                  item_id,
                  item_name_snapshot,
                  item_spec_snapshot,
                  snapshot_qty_base
                )
                VALUES (
                  :doc_id,
                  1,
                  :item_id,
                  'UT-ITEM',
                  NULL,
                  5
                )
                RETURNING id
                """
            ),
            {
                "doc_id": int(doc.id),
                "item_id": item_id,
            },
        )
    ).first()
    assert line_row is not None

    line_id = int(line_row[0])
    updated = await repo.update_line_counts(
        session,
        doc_id=int(doc.id),
        counted_by_name_snapshot="UT_COUNTER",
        lines=[
            {
                "line_id": line_id,
                "counted_qty_input": 7,
            }
        ],
    )
    assert updated == 1

    line = (
        await session.execute(
            text(
                """
                SELECT
                  counted_item_uom_id,
                  counted_uom_name_snapshot,
                  counted_ratio_to_base_snapshot,
                  counted_qty_input,
                  counted_qty_base,
                  diff_qty_base
                FROM count_doc_lines
                WHERE id = :line_id
                LIMIT 1
                """
            ),
            {"line_id": line_id},
        )
    ).mappings().first()
    assert line is not None
    assert int(line["counted_item_uom_id"]) == int(item_row["id"])
    assert str(line["counted_uom_name_snapshot"]) == str(item_row["uom_name"])
    assert int(line["counted_ratio_to_base_snapshot"]) == 1
    assert int(line["counted_qty_input"]) == 7
    assert int(line["counted_qty_base"]) == 7
    assert int(line["diff_qty_base"]) == 2

@pytest.mark.asyncio
async def test_lots_supplier_snapshot_reads_policy_through_pms_export(session):
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
    production_date = date(2099, 1, 17)
    expiry_date = date(2099, 2, 17)

    await session.execute(
        text(
            """
            UPDATE items
               SET expiry_policy = 'REQUIRED'::expiry_policy,
                   lot_source_policy = 'SUPPLIER_ONLY'::lot_source_policy,
                   derivation_allowed = TRUE,
                   uom_governance_enabled = TRUE,
                   shelf_life_value = 31,
                   shelf_life_unit = 'DAY'
             WHERE id = :item_id
            """
        ),
        {"item_id": item_id},
    )
    await session.execute(
        text(
            """
            DELETE FROM lots
             WHERE warehouse_id = 1
               AND item_id = :item_id
               AND lot_code_source = 'SUPPLIER'
               AND production_date = :production_date
            """
        ),
        {
            "item_id": item_id,
            "production_date": production_date,
        },
    )
    await session.flush()

    lot_id = await ensure_lot_full(
        session,
        item_id=item_id,
        warehouse_id=1,
        lot_code=f"UT-PMS-LOT-{item_id}",
        production_date=production_date,
        expiry_date=expiry_date,
    )

    lot = (
        await session.execute(
            text(
                """
                SELECT
                  item_lot_source_policy_snapshot,
                  item_expiry_policy_snapshot,
                  item_derivation_allowed_snapshot,
                  item_uom_governance_enabled_snapshot,
                  item_shelf_life_value_snapshot,
                  item_shelf_life_unit_snapshot
                FROM lots
                WHERE id = :lot_id
                LIMIT 1
                """
            ),
            {"lot_id": int(lot_id)},
        )
    ).mappings().first()
    assert lot is not None

    assert str(lot["item_lot_source_policy_snapshot"]) == "SUPPLIER_ONLY"
    assert str(lot["item_expiry_policy_snapshot"]) == "REQUIRED"
    assert bool(lot["item_derivation_allowed_snapshot"]) is True
    assert bool(lot["item_uom_governance_enabled_snapshot"]) is True
    assert int(lot["item_shelf_life_value_snapshot"]) == 31
    assert str(lot["item_shelf_life_unit_snapshot"]) == "DAY"
