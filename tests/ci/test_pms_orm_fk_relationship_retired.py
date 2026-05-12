# tests/ci/test_pms_orm_fk_relationship_retired.py
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base, init_models

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

FORBIDDEN_TEXT_RE = re.compile(
    r"ForeignKey\(\s*[\"'](?:items|item_uoms|item_sku_codes|item_barcodes|suppliers)\."
    r"|ForeignKeyConstraint\([\s\S]*?\[(?:[^\]]*[\"'](?:items|item_uoms|item_sku_codes|item_barcodes|suppliers)\.)"
    r"|relationship\(\s*[\"'](?:Item|ItemUOM|ItemSkuCode|ItemBarcode|Supplier|SupplierContact)[\"']",
    re.MULTILINE,
)


def _runtime_model_files() -> list[Path]:
    roots = [
        ROOT / "app" / "wms",
        ROOT / "app" / "oms",
        ROOT / "app" / "procurement",
        ROOT / "app" / "finance",
    ]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(sorted(root.rglob("models/*.py")))
    return files


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_runtime_models_do_not_declare_pms_owner_orm_foreign_keys_or_relationships() -> None:
    violations: list[str] = []

    for path in _runtime_model_files():
        text_value = path.read_text(encoding="utf-8")
        for match in FORBIDDEN_TEXT_RE.finditer(text_value):
            snippet = " ".join(match.group(0).split())
            violations.append(f"{_rel(path)}: {snippet}")

    assert violations == []


def test_runtime_metadata_has_no_pms_owner_tables() -> None:
    init_models(force=True)

    assert sorted(set(Base.metadata.tables) & PMS_OWNER_TABLES) == []


@pytest.mark.asyncio
async def test_database_has_no_fk_constraints_to_pms_owner_tables(session: AsyncSession) -> None:
    values_sql = ",\n".join(
        f"(to_regclass('public.{table_name}'))"
        for table_name in sorted(PMS_OWNER_TABLES)
    )

    rows = (
        await session.execute(
            text(
                f"""
                WITH targets(oid) AS (
                  VALUES
                  {values_sql}
                )
                SELECT
                  c.conname AS constraint_name,
                  c.conrelid::regclass::text AS owner_table,
                  c.confrelid::regclass::text AS referenced_table
                FROM pg_constraint c
                WHERE c.contype = 'f'
                  AND c.confrelid IN (
                    SELECT oid FROM targets WHERE oid IS NOT NULL
                  )
                ORDER BY owner_table, constraint_name
                """
            )
        )
    ).mappings().all()

    assert rows == []
