# tests/ci/test_wms_pms_projection_retired_schema.py
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def test_wms_pms_projection_tables_are_retired(session: AsyncSession) -> None:
    rows = await session.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                'wms_pms_item_projection',
                'wms_pms_item_uom_projection',
                'wms_pms_item_policy_projection',
                'wms_pms_item_sku_code_projection',
                'wms_pms_item_barcode_projection',
                'wms_pms_projection_sync_cursors'
              )
            ORDER BY table_name
            """
        )
    )

    assert [str(row["table_name"]) for row in rows.mappings().all()] == []
