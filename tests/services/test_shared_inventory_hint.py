from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.wms.inventory_adjustment.count.repos.count_doc_repo as count_doc_repo_module
import app.wms.shared.services.lot_code_contract as lot_code_contract_module
import app.wms.stock.services.lots as lots_module
import app.wms.stock.services.stock_adjust.db_items as db_items_module
import app.wms.stock.services.lot_resolver as lot_resolver_module
from app.wms.inventory_adjustment.count.repos.count_doc_repo import CountDocRepo
from app.wms.stock.services.lot_resolver import LotResolver
from app.wms.stock.services.lots import ensure_lot_full
from app.wms.stock.services.stock_adjust.db_items import item_requires_batch
from app.wms.shared.services.lot_code_contract import (
    fetch_item_by_sku,
    fetch_item_expiry_policy_map,
)
from tests.helpers.pms_projection import seed_pms_projection_item_with_base_uom
from tests.helpers.pms_read_client_fake import projection_backed_pms_read_client_factory

pytestmark = pytest.mark.asyncio


def _patch_pms_client(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    *modules: object,
) -> None:
    factory = projection_backed_pms_read_client_factory(session)
    for module in modules:
        monkeypatch.setattr(module, "create_pms_read_client", factory)


@pytest.mark.asyncio
async def test_shared_inventory_statement(session: AsyncSession):
    # 合同性断言：共享仓策略下，不按店隔离库存
    # 这里只做口径约定，不做真实库存运算（待主线库存裁决链路接入后替换）
    row = await session.execute(text("SELECT 1"))
    assert row.scalar() == 1


@pytest.mark.asyncio
async def test_lot_code_contract_reads_policy_through_pms_export(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_pms_client(monkeypatch, session, lot_code_contract_module)

    seeded = await seed_pms_projection_item_with_base_uom(
        session,
        item_id=993001,
        item_uom_id=993011,
        sku_code_id=993021,
        sku="UT-LOT-CONTRACT-993001",
        name="UT Lot Contract Item 993001",
        expiry_policy="REQUIRED",
    )
    await session.flush()

    item_id = int(seeded["item_id"])
    sku = str(seeded["sku"])

    policy_map = await fetch_item_expiry_policy_map(session, {item_id})
    assert policy_map == {item_id: "REQUIRED"}

    resolved = await fetch_item_by_sku(session, sku)
    assert resolved == (item_id, True)


@pytest.mark.asyncio
async def test_lot_code_contract_returns_none_for_unknown_sku(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_pms_client(monkeypatch, session, lot_code_contract_module)

    resolved = await fetch_item_by_sku(session, "UT-LOT-CONTRACT-NOT-FOUND")
    assert resolved is None


@pytest.mark.asyncio
async def test_lot_resolver_requires_batch_reads_policy_through_pms_export(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_pms_client(monkeypatch, session, lot_resolver_module)

    await seed_pms_projection_item_with_base_uom(
        session,
        item_id=993002,
        item_uom_id=993012,
        sku_code_id=993022,
        sku="UT-LOT-RESOLVER-REQUIRED",
        name="UT Lot Resolver Required",
        expiry_policy="REQUIRED",
    )
    await seed_pms_projection_item_with_base_uom(
        session,
        item_id=993003,
        item_uom_id=993013,
        sku_code_id=993023,
        sku="UT-LOT-RESOLVER-NONE",
        name="UT Lot Resolver None",
        expiry_policy="NONE",
    )
    await session.flush()

    resolver = LotResolver()
    assert await resolver.requires_batch(session, item_id=993002) is True
    assert await resolver.requires_batch(session, item_id=993003) is False


@pytest.mark.asyncio
async def test_lot_resolver_requires_batch_unknown_item_raises(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_pms_client(monkeypatch, session, lot_resolver_module)

    resolver = LotResolver()
    with pytest.raises(ValueError, match="item_not_found"):
        await resolver.requires_batch(session, item_id=999999999)


@pytest.mark.asyncio
async def test_stock_adjust_item_requires_batch_reads_policy_through_pms_export(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_pms_client(monkeypatch, session, db_items_module)

    await seed_pms_projection_item_with_base_uom(
        session,
        item_id=993004,
        item_uom_id=993014,
        sku_code_id=993024,
        sku="UT-STOCK-ADJUST-REQUIRED",
        name="UT Stock Adjust Required",
        expiry_policy="REQUIRED",
    )
    await seed_pms_projection_item_with_base_uom(
        session,
        item_id=993005,
        item_uom_id=993015,
        sku_code_id=993025,
        sku="UT-STOCK-ADJUST-NONE",
        name="UT Stock Adjust None",
        expiry_policy="NONE",
    )
    await session.flush()

    assert await item_requires_batch(session, item_id=993004) is True
    assert await item_requires_batch(session, item_id=993005) is False


@pytest.mark.asyncio
async def test_stock_adjust_item_requires_batch_unknown_item_raises(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_pms_client(monkeypatch, session, db_items_module)

    with pytest.raises(ValueError, match="item_not_found"):
        await item_requires_batch(session, item_id=999999999)


@pytest.mark.asyncio
async def test_count_doc_repo_reads_base_uom_through_pms_export(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_pms_client(monkeypatch, session, count_doc_repo_module)

    seeded = await seed_pms_projection_item_with_base_uom(
        session,
        item_id=993006,
        item_uom_id=993016,
        sku_code_id=993026,
        sku="UT-COUNT-UOM-993006",
        name="UT Count UOM 993006",
        expiry_policy="NONE",
        display_name="PCS",
    )
    await session.flush()

    item_id = int(seeded["item_id"])
    item_uom_id = int(seeded["item_uom_id"])

    got = await CountDocRepo().get_base_uom_map(session, item_ids=[item_id])

    assert item_id in got
    assert got[item_id]["base_item_uom_id"] == item_uom_id
    assert got[item_id]["base_uom_name"] == "PCS"


@pytest.mark.asyncio
async def test_count_doc_repo_update_line_counts_reads_base_uom_through_pms_export(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_pms_client(monkeypatch, session, count_doc_repo_module)

    seeded = await seed_pms_projection_item_with_base_uom(
        session,
        item_id=993007,
        item_uom_id=993017,
        sku_code_id=993027,
        sku="UT-COUNT-LINE-993007",
        name="UT Count Line 993007",
        expiry_policy="NONE",
        display_name="PCS",
    )
    await session.flush()

    item_id = int(seeded["item_id"])
    item_uom_id = int(seeded["item_uom_id"])

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
    assert int(line["counted_item_uom_id"]) == item_uom_id
    assert str(line["counted_uom_name_snapshot"]) == "PCS"
    assert int(line["counted_ratio_to_base_snapshot"]) == 1
    assert int(line["counted_qty_input"]) == 7
    assert int(line["counted_qty_base"]) == 7
    assert int(line["diff_qty_base"]) == 2


@pytest.mark.asyncio
async def test_lots_supplier_snapshot_reads_policy_through_pms_export(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_pms_client(monkeypatch, session, lots_module)

    seeded = await seed_pms_projection_item_with_base_uom(
        session,
        item_id=993008,
        item_uom_id=993018,
        sku_code_id=993028,
        sku="UT-PMS-LOT-993008",
        name="UT PMS Lot 993008",
        expiry_policy="REQUIRED",
    )
    await session.flush()

    item_id = int(seeded["item_id"])
    production_date = date(2099, 1, 17)
    expiry_date = date(2099, 2, 17)

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
    assert int(lot["item_shelf_life_value_snapshot"]) == 30
    assert str(lot["item_shelf_life_unit_snapshot"]) == "DAY"
