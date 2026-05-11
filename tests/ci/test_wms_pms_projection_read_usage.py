# tests/ci/test_wms_pms_projection_read_usage.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_inventory_options_items_read_from_projection_not_http() -> None:
    text = (ROOT / "app/wms/stock/repos/inventory_options_repo.py").read_text(encoding="utf-8")

    assert "wms_pms_item_projection" in text
    assert "create_pms_read_client" not in text
    assert "ItemReadQuery" not in text


def test_inventory_options_items_do_not_read_pms_owner_tables() -> None:
    text = (ROOT / "app/wms/stock/repos/inventory_options_repo.py").read_text(encoding="utf-8")

    forbidden = re.compile(
        r"\bFROM\s+(items|item_uoms|item_sku_codes|item_barcodes)\b"
        r"|\bJOIN\s+(items|item_uoms|item_sku_codes|item_barcodes)\b",
        re.IGNORECASE,
    )
    assert forbidden.search(text) is None


def test_inventory_options_items_do_not_write_projection() -> None:
    text = (ROOT / "app/wms/stock/repos/inventory_options_repo.py").read_text(encoding="utf-8")

    assert "INSERT INTO wms_pms_" not in text
    assert "UPDATE wms_pms_" not in text
    assert "DELETE FROM wms_pms_" not in text
