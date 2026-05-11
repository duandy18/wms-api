# tests/ci/test_pms_split_legacy_owner_tables_frozen.py
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).resolve().parents[2]

BUSINESS_DIRS = (
    "app/wms",
    "app/oms",
    "app/procurement",
    "app/finance",
)

LEGACY_PMS_OWNER_TABLES = {
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
}

OWNER_MODEL_NAMES = (
    "Item",
    "ItemUOM",
    "ItemBarcode",
    "ItemSkuCode",
    "PmsBrand",
    "PmsBusinessCategory",
    "ItemAttributeDef",
    "ItemAttributeOption",
    "ItemAttributeValue",
    "SkuCodeTemplate",
    "SkuCodeTemplateSegment",
)

_TABLE_ALT = "|".join(
    sorted((re.escape(name) for name in LEGACY_PMS_OWNER_TABLES), key=len, reverse=True)
)

_MODEL_ALT = "|".join(re.escape(name) for name in OWNER_MODEL_NAMES)

DIRECT_OWNER_SQL_RE = re.compile(
    rf"\b(?:FROM|JOIN|UPDATE|INTO|DELETE\s+FROM|TRUNCATE\s+TABLE)\s+"
    rf"(?:public\.)?(?:{_TABLE_ALT})\b",
    re.IGNORECASE,
)

DIRECT_OWNER_ORM_RE = re.compile(
    rf"(?:Table|table)\(\s*[\"'](?:{_TABLE_ALT})[\"']"
    rf"|ForeignKey\(\s*[\"'](?:{_TABLE_ALT})\."
    rf"|ForeignKeyConstraint\([\s\S]*?[\"'](?:{_TABLE_ALT})\."
    rf"|relationship\(\s*[\"'](?:{_MODEL_ALT})[\"']",
    re.MULTILINE,
)

DIRECT_OWNER_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+app\.pms\b",
    re.MULTILINE,
)


def _business_python_files() -> list[Path]:
    files: list[Path] = []
    for rel_dir in BUSINESS_DIRS:
        root = ROOT / rel_dir
        if root.exists():
            files.extend(sorted(root.rglob("*.py")))
    return files


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _line_no(text: str, offset: int) -> int:
    return text[:offset].count("\n") + 1


def _snippet(value: str) -> str:
    return " ".join(value.split())[:180]


def test_legacy_app_pms_package_is_absent() -> None:
    assert not (ROOT / "app" / "pms").exists()


def test_business_domains_do_not_import_legacy_pms_owner_runtime() -> None:
    violations: list[str] = []

    for path in _business_python_files():
        text = path.read_text(encoding="utf-8")
        for match in DIRECT_OWNER_IMPORT_RE.finditer(text):
            violations.append(
                f"{_rel(path)}:{_line_no(text, match.start())}: {_snippet(match.group(0))}"
            )

    assert violations == []


def test_business_domains_do_not_read_or_write_legacy_pms_owner_tables_by_sql() -> None:
    violations: list[str] = []

    for path in _business_python_files():
        text = path.read_text(encoding="utf-8")
        for match in DIRECT_OWNER_SQL_RE.finditer(text):
            violations.append(
                f"{_rel(path)}:{_line_no(text, match.start())}: {_snippet(match.group(0))}"
            )

    assert violations == []


def test_business_domains_do_not_redeclare_legacy_pms_owner_orm_links() -> None:
    violations: list[str] = []

    for path in _business_python_files():
        text = path.read_text(encoding="utf-8")
        for match in DIRECT_OWNER_ORM_RE.finditer(text):
            violations.append(
                f"{_rel(path)}:{_line_no(text, match.start())}: {_snippet(match.group(0))}"
            )

    assert violations == []


@pytest.mark.asyncio
async def test_wms_legacy_pms_owner_tables_remain_only_as_stabilization_residue(
    session: AsyncSession,
) -> None:
    rows = (
        await session.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (
                    'items',
                    'item_uoms',
                    'item_barcodes',
                    'item_sku_codes',
                    'pms_brands',
                    'pms_business_categories',
                    'item_attribute_defs',
                    'item_attribute_options',
                    'item_attribute_values',
                    'sku_code_templates',
                    'sku_code_template_segments'
                  )
                ORDER BY table_name
                """
            )
        )
    ).mappings().all()

    got = {str(row["table_name"]) for row in rows}
    assert got == LEGACY_PMS_OWNER_TABLES


@pytest.mark.asyncio
async def test_wms_legacy_pms_owner_tables_have_no_cross_domain_physical_fk_dependents(
    session: AsyncSession,
) -> None:
    rows = (
        await session.execute(
            text(
                """
                WITH pms_tables(table_name) AS (
                  VALUES
                    ('items'),
                    ('item_uoms'),
                    ('item_barcodes'),
                    ('item_sku_codes'),
                    ('pms_brands'),
                    ('pms_business_categories'),
                    ('item_attribute_defs'),
                    ('item_attribute_options'),
                    ('item_attribute_values'),
                    ('sku_code_templates'),
                    ('sku_code_template_segments')
                )
                SELECT
                  c.conname,
                  c.conrelid::regclass::text AS referencing_table,
                  c.confrelid::regclass::text AS referenced_table,
                  pg_get_constraintdef(c.oid) AS constraint_def
                FROM pg_constraint c
                JOIN pms_tables referenced
                  ON referenced.table_name = c.confrelid::regclass::text
                WHERE c.contype = 'f'
                  AND NOT EXISTS (
                    SELECT 1
                    FROM pms_tables owner_table
                    WHERE owner_table.table_name = c.conrelid::regclass::text
                  )
                ORDER BY referenced_table, referencing_table, conname
                """
            )
        )
    ).mappings().all()

    assert rows == []
