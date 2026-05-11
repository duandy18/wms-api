# tests/ci/test_pms_projection_tables_are_truncated.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_PROJECTION_TABLES = (
    "wms_pms_item_projection",
    "wms_pms_uom_projection",
    "wms_pms_sku_code_projection",
    "wms_pms_barcode_projection",
)


def test_test_truncate_clears_pms_projection_tables() -> None:
    truncate_sql = (ROOT / "tests" / "fixtures" / "truncate.sql").read_text(
        encoding="utf-8"
    )

    missing = [
        table_name
        for table_name in REQUIRED_PROJECTION_TABLES
        if table_name not in truncate_sql
    ]

    assert missing == []
