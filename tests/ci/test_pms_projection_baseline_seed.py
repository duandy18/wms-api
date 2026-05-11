# tests/ci/test_pms_projection_baseline_seed.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_PROJECTION_TABLES = (
    "wms_pms_item_projection",
    "wms_pms_uom_projection",
    "wms_pms_sku_code_projection",
    "wms_pms_barcode_projection",
)


def test_base_seed_materializes_pms_projection_baseline() -> None:
    sql = (ROOT / "tests" / "fixtures" / "base_seed.sql").read_text(encoding="utf-8")

    missing = [
        table_name
        for table_name in REQUIRED_PROJECTION_TABLES
        if table_name not in sql
    ]

    assert missing == []


def test_conftest_keeps_projection_batch_policy_aligned_with_legacy_seed() -> None:
    conftest = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")

    assert "UPDATE items" in conftest
    assert "UPDATE wms_pms_item_projection" in conftest
    assert "test-baseline:required:" in conftest
