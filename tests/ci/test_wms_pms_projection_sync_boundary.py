# tests/ci/test_wms_pms_projection_sync_boundary.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_OWNER_SQL_RE = re.compile(
    r"\bFROM\s+(items|item_uoms|item_sku_codes|item_barcodes)\b"
    r"|\bJOIN\s+(items|item_uoms|item_sku_codes|item_barcodes)\b",
    re.IGNORECASE,
)


def test_pms_projection_sync_uses_read_v1_feed_endpoints_only() -> None:
    text = (ROOT / "app/integrations/pms/projection_sync.py").read_text(encoding="utf-8")

    assert "/pms/read/v1/projection-feed/items" in text
    assert "/pms/read/v1/projection-feed/uoms" in text
    assert "/pms/read/v1/projection-feed/sku-codes" in text
    assert "/pms/read/v1/projection-feed/barcodes" in text

    assert "/pms/export/" not in text
    assert "/items/basic" not in text


def test_pms_projection_sync_does_not_read_owner_tables_directly() -> None:
    text = (ROOT / "app/integrations/pms/projection_sync.py").read_text(encoding="utf-8")

    assert FORBIDDEN_OWNER_SQL_RE.search(text) is None
    assert "app.pms" not in text


def test_pms_projection_sync_writes_projection_tables_only() -> None:
    text = (ROOT / "app/integrations/pms/projection_sync.py").read_text(encoding="utf-8")

    assert "INSERT INTO wms_pms_item_projection" in text
    assert "INSERT INTO wms_pms_uom_projection" in text
    assert "INSERT INTO wms_pms_sku_code_projection" in text
    assert "INSERT INTO wms_pms_barcode_projection" in text
