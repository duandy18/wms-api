# tests/ci/test_wms_pms_projection_sync_cursor_schema.py
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def test_wms_pms_projection_sync_cursor_schema(session: AsyncSession) -> None:
    rows = await session.execute(
        text(
            """
            SELECT
              column_name,
              is_nullable,
              data_type,
              column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'wms_pms_projection_sync_cursors'
            """
        )
    )
    columns = {str(row["column_name"]): row for row in rows.mappings().all()}

    required_columns = {
        "source_name",
        "last_source_updated_at",
        "last_synced_at",
        "last_status",
        "last_error",
        "retry_count",
        "created_at",
        "updated_at",
    }
    assert required_columns <= set(columns)

    assert columns["source_name"]["is_nullable"] == "NO"
    assert columns["last_source_updated_at"]["is_nullable"] == "NO"
    assert columns["last_synced_at"]["is_nullable"] == "NO"
    assert columns["last_status"]["is_nullable"] == "NO"
    assert columns["retry_count"]["is_nullable"] == "NO"

    constraints = await session.execute(
        text(
            """
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t
              ON t.oid = c.conrelid
            JOIN pg_namespace n
              ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = 'wms_pms_projection_sync_cursors'
            """
        )
    )
    constraint_names = {str(row["conname"]) for row in constraints.mappings().all()}

    assert {
        "pk_wms_pms_projection_sync_cursors",
        "ck_wms_pms_projection_sync_cursor_source_name_non_empty",
        "ck_wms_pms_projection_sync_cursor_status",
        "ck_wms_pms_projection_sync_cursor_retry_non_negative",
    } <= constraint_names
