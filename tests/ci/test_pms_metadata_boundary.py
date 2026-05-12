# tests/ci/test_pms_metadata_boundary.py
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).resolve().parents[2]

PMS_OWNER_TABLES = {
    "items",
    "item_uoms",
    "item_barcodes",
    "item_sku_codes",
    "pms_brands",
    "pms_business_categories",
    "item_attribute_defs",
    "item_attribute_options",
    "item_attribute_values",
    "sku_code_templates",
    "sku_code_template_segments",
    "suppliers",
    "supplier_contacts",
}

WMS_PMS_PROJECTION_TABLES = {
    "wms_pms_item_projection",
    "wms_pms_uom_projection",
    "wms_pms_sku_code_projection",
    "wms_pms_barcode_projection",
    "wms_pms_supplier_projection",
}


def test_external_pms_anchor_module_is_removed() -> None:
    assert not (ROOT / "app/db/external_pms_models.py").exists()


def test_db_base_does_not_load_pms_owner_orm_or_external_anchors() -> None:
    text_value = (ROOT / "app" / "db" / "base.py").read_text(encoding="utf-8")

    assert "app.pms.items.models" not in text_value
    assert "app.pms.sku_coding.models" not in text_value
    assert "app.db.external_pms_models" not in text_value
    assert "_load_external_pms_orm_anchors" not in text_value


def test_fresh_init_models_registers_no_pms_owner_tables_and_keeps_projections() -> None:
    code = f"""
import json
from app.db.base import Base, init_models

PMS_OWNER_TABLES = set({json.dumps(sorted(PMS_OWNER_TABLES))})
WMS_PMS_PROJECTION_TABLES = set({json.dumps(sorted(WMS_PMS_PROJECTION_TABLES))})

init_models(force=True)
tables = set(Base.metadata.tables)
print("RESULT=" + json.dumps({{
    "owner_hits": sorted(tables & PMS_OWNER_TABLES),
    "projection_hits": sorted(tables & WMS_PMS_PROJECTION_TABLES),
}}))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = "."

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    marker = "RESULT="
    lines = [line for line in result.stdout.splitlines() if line.startswith(marker)]
    assert lines, result.stdout + result.stderr

    payload = json.loads(lines[-1][len(marker) :])
    assert payload["owner_hits"] == []
    assert set(payload["projection_hits"]) == WMS_PMS_PROJECTION_TABLES


def test_alembic_env_no_longer_depends_on_external_pms_anchor_filtering() -> None:
    text_value = (ROOT / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "app.db.external_pms_models" not in text_value
    assert "PMS_OWNED_TABLES" not in text_value
    assert "PMS_EXTERNAL_ANCHOR_TABLES" not in text_value
    assert "PMS-owned tables are managed by pms-api" not in text_value


def test_alembic_env_still_ignores_reflected_db_extras() -> None:
    text_value = (ROOT / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "reflected and compare_to is None" in text_value
    assert "return False" in text_value


@pytest.mark.asyncio
async def test_wms_db_has_no_residual_pms_owner_tables(session: AsyncSession) -> None:
    values_sql = ",\n".join(
        f"('{table_name}', to_regclass('public.{table_name}'))"
        for table_name in sorted(PMS_OWNER_TABLES)
    )
    rows = (
        await session.execute(
            text(
                f"""
                SELECT table_name, oid
                FROM (VALUES
                  {values_sql}
                ) AS t(table_name, oid)
                WHERE oid IS NOT NULL
                ORDER BY table_name
                """
            )
        )
    ).mappings().all()

    assert rows == []
