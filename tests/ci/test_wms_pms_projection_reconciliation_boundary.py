# tests/ci/test_wms_pms_projection_reconciliation_boundary.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_OWNER_SQL_RE = re.compile(
    r"\bFROM\s+(items|item_uoms|item_sku_codes|item_barcodes)\b"
    r"|\bJOIN\s+(items|item_uoms|item_sku_codes|item_barcodes)\b",
    re.IGNORECASE,
)


def test_pms_projection_reconciliation_reads_projection_not_owner_tables() -> None:
    text = (ROOT / "app/integrations/pms/projection_reconciliation.py").read_text(
        encoding="utf-8"
    )

    assert "wms_pms_item_projection" in text
    assert "wms_pms_uom_projection" in text
    assert "wms_pms_sku_code_projection" in text
    assert "wms_pms_supplier_projection" in text
    assert "wms_pms_barcode_projection" not in text
    assert FORBIDDEN_OWNER_SQL_RE.search(text) is None


def test_pms_projection_reconciliation_is_read_only() -> None:
    text = (ROOT / "app/integrations/pms/projection_reconciliation.py").read_text(
        encoding="utf-8"
    )

    assert "INSERT INTO" not in text
    assert "UPDATE " not in text
    assert "DELETE FROM" not in text
    assert "DROP " not in text
    assert "ALTER " not in text


def test_pms_projection_reconciliation_cli_uses_service() -> None:
    text = (ROOT / "scripts/pms/reconcile_projection.py").read_text(encoding="utf-8")

    assert "reconcile_pms_projection_references" in text
    assert "fail-on-issues" in text
