# tests/services/test_pms_supplier_projection_reconciliation.py
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.projection_reconciliation import (
    SupplierReference,
    reconcile_pms_projection_references,
)

pytestmark = pytest.mark.asyncio


async def test_supplier_projection_reconciliation_reports_missing_supplier(
    session: AsyncSession,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO wms_pms_supplier_projection (
                supplier_id,
                supplier_code,
                supplier_name,
                active,
                website,
                pms_updated_at,
                source_hash,
                sync_version,
                synced_at
            )
            VALUES (
                880001,
                'UT-SUP-880001',
                'UT Supplier 880001',
                TRUE,
                NULL,
                now(),
                'ut-supplier-880001',
                'ut-supplier-projection',
                now()
            )
            ON CONFLICT (supplier_id) DO UPDATE SET
                supplier_code = EXCLUDED.supplier_code,
                supplier_name = EXCLUDED.supplier_name,
                active = EXCLUDED.active,
                website = EXCLUDED.website,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        )
    )

    await session.execute(
        text(
            """
            CREATE TEMP TABLE tmp_pms_reconcile_supplier_refs (
                id INTEGER NOT NULL,
                supplier_id INTEGER
            ) ON COMMIT DROP
            """
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO tmp_pms_reconcile_supplier_refs (id, supplier_id)
            VALUES
              (1, 880001),
              (2, 880099)
            """
        )
    )

    result = await reconcile_pms_projection_references(
        session,
        item_references=(),
        uom_references=(),
        sku_code_references=(),
        supplier_references=(
            SupplierReference("pg_temp.tmp_pms_reconcile_supplier_refs", "id", "supplier_id"),
        ),
    )

    assert result.ok is False
    assert result.issue_count == 1
    assert result.summary_by_type() == {"SUPPLIER_MISSING_IN_PROJECTION": 1}

    issue = result.issues[0]
    assert issue.issue_type == "SUPPLIER_MISSING_IN_PROJECTION"
    assert issue.source_table == "pg_temp.tmp_pms_reconcile_supplier_refs"
    assert issue.source_column == "supplier_id"
    assert issue.source_id == "2"
    assert issue.supplier_id == 880099


async def test_supplier_projection_reconciliation_returns_ok_for_clean_supplier_refs(
    session: AsyncSession,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO wms_pms_supplier_projection (
                supplier_id,
                supplier_code,
                supplier_name,
                active,
                website,
                pms_updated_at,
                source_hash,
                sync_version,
                synced_at
            )
            VALUES (
                880002,
                'UT-SUP-880002',
                'UT Supplier 880002',
                TRUE,
                NULL,
                now(),
                'ut-supplier-880002',
                'ut-supplier-projection',
                now()
            )
            ON CONFLICT (supplier_id) DO UPDATE SET
                supplier_code = EXCLUDED.supplier_code,
                supplier_name = EXCLUDED.supplier_name,
                active = EXCLUDED.active,
                website = EXCLUDED.website,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        )
    )

    await session.execute(
        text(
            """
            CREATE TEMP TABLE tmp_pms_reconcile_supplier_clean_refs (
                id INTEGER NOT NULL,
                supplier_id INTEGER
            ) ON COMMIT DROP
            """
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO tmp_pms_reconcile_supplier_clean_refs (id, supplier_id)
            VALUES (1, 880002)
            """
        )
    )

    result = await reconcile_pms_projection_references(
        session,
        item_references=(),
        uom_references=(),
        sku_code_references=(),
        supplier_references=(
            SupplierReference("pg_temp.tmp_pms_reconcile_supplier_clean_refs", "id", "supplier_id"),
        ),
    )

    assert result.ok is True
    assert result.issue_count == 0
