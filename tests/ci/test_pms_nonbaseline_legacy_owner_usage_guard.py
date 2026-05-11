# tests/ci/test_pms_nonbaseline_legacy_owner_usage_guard.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = ROOT / "tests"

LEGACY_BASELINE_ALLOWLIST = {
    Path("tests/ci/test_pms_projection_baseline_seed.py"),
    Path("tests/ci/test_pms_nonbaseline_legacy_owner_usage_guard.py"),
}

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
    \bFROM\s+(items|item_uoms|item_barcodes|item_sku_codes)\b
    |
    \bJOIN\s+(items|item_uoms|item_barcodes|item_sku_codes)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _iter_test_sources() -> list[Path]:
    return sorted(
        path
        for path in TESTS_DIR.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".sql"}
        and path.relative_to(ROOT) not in LEGACY_BASELINE_ALLOWLIST
    )


def _scan(pattern: re.Pattern[str]) -> list[str]:
    hits: list[str] = []

    for path in _iter_test_sources():
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                hits.append(f"{rel}:{lineno}: {line.strip()}")

    return hits


def test_nonbaseline_tests_do_not_write_legacy_pms_owner_tables() -> None:
    """
    PMS 已拆出独立进程/库后，WMS 测试层不得再写旧 PMS owner 表。

    baseline PMS current-state 只能通过：
    - tests/fixtures/pms_projection_seed.sql
    - wms_pms_*_projection
    - projection-backed PMS fake client
    """
    hits = _scan(LEGACY_OWNER_WRITE_PATTERN)
    assert hits == []


def test_nonbaseline_tests_do_not_read_legacy_pms_owner_tables() -> None:
    """
    普通测试读取 PMS 商品 / UOM / SKU / Barcode 必须走 WMS PMS projection
    或 projection-backed PMS fake client。
    """
    hits = _scan(LEGACY_OWNER_READ_PATTERN)
    assert hits == []
