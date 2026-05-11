# tests/services/test_pms_projection_seed_helpers.py
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.pms_projection import (
    seed_pms_projection_item_with_base_uom,
)


@pytest.mark.asyncio
async def test_seed_pms_projection_item_with_base_uom(
    session: AsyncSession,
) -> None:
    seeded = await seed_pms_projection_item_with_base_uom(
        session,
        item_id=991001,
        item_uom_id=991011,
        sku_code_id=991021,
        barcode_id=991031,
        sku="UT-PROJ-991001",
        name="UT Projection Item 991001",
        barcode="UT-BC-991001",
        expiry_policy="REQUIRED",
    )
    await session.commit()

    assert seeded["item_id"] == 991001
    assert seeded["item_uom_id"] == 991011
    assert seeded["sku_code_id"] == 991021
    assert seeded["barcode_id"] == 991031

    item = (
        await session.execute(
            text(
                """
                SELECT
                    item_id,
                    sku,
                    name,
                    expiry_policy,
                    shelf_life_value,
                    shelf_life_unit,
                    lot_source_policy,
                    uom_governance_enabled
                FROM wms_pms_item_projection
                WHERE item_id = :item_id
                """
            ),
            {"item_id": 991001},
        )
    ).mappings().one()

    assert int(item["item_id"]) == 991001
    assert item["sku"] == "UT-PROJ-991001"
    assert item["name"] == "UT Projection Item 991001"
    assert item["expiry_policy"] == "REQUIRED"
    assert int(item["shelf_life_value"]) == 30
    assert item["shelf_life_unit"] == "DAY"
    assert item["lot_source_policy"] == "SUPPLIER_ONLY"
    assert item["uom_governance_enabled"] is True

    uom = (
        await session.execute(
            text(
                """
                SELECT item_uom_id, item_id, uom, uom_name, ratio_to_base, is_base
                FROM wms_pms_uom_projection
                WHERE item_uom_id = :item_uom_id
                """
            ),
            {"item_uom_id": 991011},
        )
    ).mappings().one()

    assert int(uom["item_uom_id"]) == 991011
    assert int(uom["item_id"]) == 991001
    assert uom["uom"] == "PCS"
    assert uom["uom_name"] == "PCS"
    assert int(uom["ratio_to_base"]) == 1
    assert uom["is_base"] is True

    sku_code = (
        await session.execute(
            text(
                """
                SELECT sku_code_id, item_id, sku_code, is_primary, is_active
                FROM wms_pms_sku_code_projection
                WHERE sku_code_id = :sku_code_id
                """
            ),
            {"sku_code_id": 991021},
        )
    ).mappings().one()

    assert int(sku_code["sku_code_id"]) == 991021
    assert int(sku_code["item_id"]) == 991001
    assert sku_code["sku_code"] == "UT-PROJ-991001"
    assert sku_code["is_primary"] is True
    assert sku_code["is_active"] is True

    barcode = (
        await session.execute(
            text(
                """
                SELECT barcode_id, item_id, item_uom_id, barcode, active
                FROM wms_pms_barcode_projection
                WHERE barcode_id = :barcode_id
                """
            ),
            {"barcode_id": 991031},
        )
    ).mappings().one()

    assert int(barcode["barcode_id"]) == 991031
    assert int(barcode["item_id"]) == 991001
    assert int(barcode["item_uom_id"]) == 991011
    assert barcode["barcode"] == "UT-BC-991001"
    assert barcode["active"] is True


@pytest.mark.asyncio
async def test_seed_pms_projection_item_with_base_uom_is_idempotent(
    session: AsyncSession,
) -> None:
    await seed_pms_projection_item_with_base_uom(
        session,
        item_id=991002,
        item_uom_id=991012,
        sku_code_id=991022,
        sku="UT-PROJ-991002-A",
        name="UT Projection Item A",
    )
    await seed_pms_projection_item_with_base_uom(
        session,
        item_id=991002,
        item_uom_id=991012,
        sku_code_id=991022,
        sku="UT-PROJ-991002-B",
        name="UT Projection Item B",
    )
    await session.commit()

    item = (
        await session.execute(
            text(
                """
                SELECT item_id, sku, name
                FROM wms_pms_item_projection
                WHERE item_id = :item_id
                """
            ),
            {"item_id": 991002},
        )
    ).mappings().one()

    assert int(item["item_id"]) == 991002
    assert item["sku"] == "UT-PROJ-991002-B"
    assert item["name"] == "UT Projection Item B"
