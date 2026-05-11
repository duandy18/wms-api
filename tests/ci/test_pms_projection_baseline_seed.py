# tests/ci/test_pms_projection_baseline_seed.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BASE_SEED_PATH = ROOT / "tests" / "fixtures" / "base_seed.sql"
PROJECTION_SEED_PATH = ROOT / "tests" / "fixtures" / "pms_projection_seed.sql"
SEED_SCRIPT_PATH = ROOT / "scripts" / "seed_test_baseline.py"
CONFTEST_PATH = ROOT / "tests" / "conftest.py"

REQUIRED_PROJECTION_TABLES = (
    "wms_pms_item_projection",
    "wms_pms_uom_projection",
    "wms_pms_sku_code_projection",
    "wms_pms_barcode_projection",
)

LEGACY_OWNER_WRITE_PATTERN = re.compile(
    r"""
    \bINSERT\s+INTO\s+
      (items|item_uoms|item_barcodes|item_sku_codes|
       pms_brands|pms_business_categories|
       item_attribute_defs|item_attribute_options|item_attribute_values|
       sku_code_templates|sku_code_template_segments)\b
    |
    \bUPDATE\s+
      (items|item_uoms|item_barcodes|item_sku_codes|
       pms_brands|pms_business_categories|
       item_attribute_defs|item_attribute_options|item_attribute_values|
       sku_code_templates|sku_code_template_segments)\b
    |
    \bDELETE\s+FROM\s+
      (items|item_uoms|item_barcodes|item_sku_codes|
       pms_brands|pms_business_categories|
       item_attribute_defs|item_attribute_options|item_attribute_values|
       sku_code_templates|sku_code_template_segments)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

LEGACY_OWNER_READ_PATTERN = re.compile(
    r"""
    \bFROM\s+(items|item_uoms|item_barcodes|item_sku_codes|
               pms_brands|pms_business_categories|
               item_attribute_defs|item_attribute_options|item_attribute_values|
               sku_code_templates|sku_code_template_segments)\b
    |
    \bJOIN\s+(items|item_uoms|item_barcodes|item_sku_codes|
               pms_brands|pms_business_categories|
               item_attribute_defs|item_attribute_options|item_attribute_values|
               sku_code_templates|sku_code_template_segments)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _scan_lines(pattern: re.Pattern[str], text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if pattern.search(line)
    ]


def test_projection_baseline_seed_sql_exists_and_writes_required_projection_tables() -> None:
    sql = _read(PROJECTION_SEED_PATH)

    missing = [
        table_name
        for table_name in REQUIRED_PROJECTION_TABLES
        if f"INSERT INTO {table_name}" not in sql
    ]

    assert missing == []


def test_base_seed_no_longer_materializes_pms_projection_baseline() -> None:
    sql = _read(BASE_SEED_PATH)

    hits = [
        table_name
        for table_name in REQUIRED_PROJECTION_TABLES
        if table_name in sql
    ]

    assert hits == []


def test_base_seed_is_legacy_owner_independent() -> None:
    sql = _read(BASE_SEED_PATH)

    write_hits = _scan_lines(LEGACY_OWNER_WRITE_PATTERN, sql)
    read_hits = _scan_lines(LEGACY_OWNER_READ_PATTERN, sql)

    assert write_hits == []
    assert read_hits == []


def test_projection_seed_is_owner_independent() -> None:
    sql = _read(PROJECTION_SEED_PATH)

    write_hits = _scan_lines(LEGACY_OWNER_WRITE_PATTERN, sql)
    read_hits = _scan_lines(LEGACY_OWNER_READ_PATTERN, sql)

    assert write_hits == []
    assert read_hits == []


def test_seed_test_baseline_executes_projection_seed_after_base_seed() -> None:
    source = _read(SEED_SCRIPT_PATH)

    assert "base_seed.sql" in source
    assert "pms_projection_seed.sql" in source
    assert source.index("base_seed.sql") < source.index("pms_projection_seed.sql")


def test_conftest_updates_projection_batch_policy_only() -> None:
    conftest = _read(CONFTEST_PATH)

    assert "UPDATE items" not in conftest
    assert "UPDATE wms_pms_item_projection" in conftest
    assert "test-baseline:required:" in conftest
