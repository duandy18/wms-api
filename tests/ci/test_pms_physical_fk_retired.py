# tests/ci/test_pms_physical_fk_retired.py
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


PMS_OWNER_TABLES = {
    "items",
    "item_uoms",
    "item_sku_codes",
    "item_barcodes",
    "item_attribute_values",
    "item_attribute_defs",
    "item_attribute_options",
    "sku_code_templates",
    "sku_code_template_segments",
    "pms_brands",
    "pms_business_categories",
}

PMS_REFERENCED_TABLES = {
    "items",
    "item_uoms",
    "item_sku_codes",
    "item_barcodes",
}

EXPECTED_INTERNAL_FKS = {
    ("item_barcodes", "fk_item_barcodes_item_uom_pair", "item_uoms"),
    ("item_attribute_values", "fk_item_attribute_values_item", "items"),
    ("item_barcodes", "item_barcodes_item_id_fkey", "items"),
    ("item_sku_codes", "fk_item_sku_codes_item", "items"),
    ("item_uoms", "item_uoms_item_id_fkey", "items"),
}


@pytest.mark.asyncio
async def test_cross_domain_pms_physical_fks_are_retired(
    session: AsyncSession,
) -> None:
    rows = (
        await session.execute(
            text(
                """
                select
                  c.conname,
                  c.conrelid::regclass::text as referencing_table,
                  c.confrelid::regclass::text as referenced_table,
                  pg_get_constraintdef(c.oid) as constraint_def
                from pg_constraint c
                where c.contype = 'f'
                  and c.confrelid in (
                    'items'::regclass,
                    'item_uoms'::regclass,
                    'item_sku_codes'::regclass,
                    'item_barcodes'::regclass
                  )
                  and c.conrelid::regclass::text not in (
                    'items',
                    'item_uoms',
                    'item_sku_codes',
                    'item_barcodes',
                    'item_attribute_values',
                    'item_attribute_defs',
                    'item_attribute_options',
                    'sku_code_templates',
                    'sku_code_template_segments',
                    'pms_brands',
                    'pms_business_categories'
                  )
                order by referenced_table, referencing_table, conname
                """
            )
        )
    ).mappings().all()

    assert rows == []


@pytest.mark.asyncio
async def test_pms_internal_physical_fks_remain(
    session: AsyncSession,
) -> None:
    rows = (
        await session.execute(
            text(
                """
                select
                  c.conrelid::regclass::text as referencing_table,
                  c.conname,
                  c.confrelid::regclass::text as referenced_table
                from pg_constraint c
                where c.contype = 'f'
                  and c.confrelid in (
                    'items'::regclass,
                    'item_uoms'::regclass,
                    'item_sku_codes'::regclass,
                    'item_barcodes'::regclass
                  )
                  and c.conrelid::regclass::text in (
                    'items',
                    'item_uoms',
                    'item_sku_codes',
                    'item_barcodes',
                    'item_attribute_values',
                    'item_attribute_defs',
                    'item_attribute_options',
                    'sku_code_templates',
                    'sku_code_template_segments',
                    'pms_brands',
                    'pms_business_categories'
                  )
                order by referenced_table, referencing_table, conname
                """
            )
        )
    ).mappings().all()

    got = {
        (
            str(row["referencing_table"]),
            str(row["conname"]),
            str(row["referenced_table"]),
        )
        for row in rows
    }

    assert got == EXPECTED_INTERNAL_FKS
