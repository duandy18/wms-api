# tests/services/test_pms_export_item_read_service.py
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.pms.export.items.contracts.item_query import ItemReadQuery
from app.pms.export.items.services.item_read_service import ItemReadService

pytestmark = pytest.mark.asyncio


async def test_item_read_service_aget_policy_by_id_returns_policy(
    session: AsyncSession,
) -> None:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  id,
                  expiry_policy::text AS expiry_policy,
                  shelf_life_value,
                  shelf_life_unit::text AS shelf_life_unit,
                  lot_source_policy::text AS lot_source_policy,
                  derivation_allowed,
                  uom_governance_enabled
                FROM items
                ORDER BY id
                LIMIT 1
                """
            )
        )
    ).mappings().first()

    assert row is not None

    svc = ItemReadService(session)
    got = await svc.aget_policy_by_id(item_id=int(row["id"]))

    assert got is not None
    assert got.item_id == int(row["id"])
    assert got.expiry_policy == str(row["expiry_policy"])
    assert got.shelf_life_value == (
        int(row["shelf_life_value"]) if row["shelf_life_value"] is not None else None
    )
    assert got.shelf_life_unit == (
        str(row["shelf_life_unit"]) if row["shelf_life_unit"] is not None else None
    )
    assert got.lot_source_policy == str(row["lot_source_policy"])
    assert got.derivation_allowed is bool(row["derivation_allowed"])
    assert got.uom_governance_enabled is bool(row["uom_governance_enabled"])


async def test_item_read_service_aget_basics_by_item_ids_returns_items_table_fields_only(
    session: AsyncSession,
) -> None:
    rows = (
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
                LEFT JOIN pms_brands b ON b.id = i.brand_id
                LEFT JOIN pms_business_categories c ON c.id = i.category_id
                ORDER BY i.id
                LIMIT 5
                """
            )
        )
    ).mappings().all()

    assert rows

    svc = ItemReadService(session)
    item_ids = [int(row["id"]) for row in rows]
    got = await svc.aget_basics_by_item_ids(item_ids=item_ids)

    assert set(got.keys()) == set(item_ids)

    for row in rows:
        item_id = int(row["id"])
        basic = got[item_id]

        assert basic.id == item_id
        assert basic.sku == str(row["sku"])
        assert basic.name == str(row["name"])
        assert basic.spec == (str(row["spec"]).strip() if row["spec"] is not None else None)
        assert basic.enabled is bool(row["enabled"])
        assert basic.supplier_id == (
            int(row["supplier_id"]) if row["supplier_id"] is not None else None
        )
        assert basic.brand == (str(row["brand"]).strip() if row["brand"] is not None else None)
        assert basic.category == (
            str(row["category"]).strip() if row["category"] is not None else None
        )
        assert not hasattr(basic, "primary_barcode")

async def test_item_read_service_alist_basic_filters_enabled_and_keyword(
    session: AsyncSession,
) -> None:
    row = (
        await session.execute(
            text(
                """
                SELECT id, sku, name
                FROM items
                WHERE enabled IS TRUE
                ORDER BY id
                LIMIT 1
                """
            )
        )
    ).mappings().first()

    assert row is not None

    got = await ItemReadService(session).alist_basic(
        query=ItemReadQuery(
            enabled=True,
            q=str(row["sku"]),
            limit=500,
        )
    )

    assert any(item.id == int(row["id"]) for item in got)
    assert all(item.enabled is True for item in got)
    assert len(got) <= 500
