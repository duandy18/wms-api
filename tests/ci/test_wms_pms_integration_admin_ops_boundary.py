# tests/ci/test_wms_pms_integration_admin_ops_boundary.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_OWNER_SQL_RE = re.compile(
    r"\bFROM\s+(items|item_uoms|item_sku_codes|item_barcodes|suppliers|supplier_contacts)\b"
    r"|\bJOIN\s+(items|item_uoms|item_sku_codes|item_barcodes|suppliers|supplier_contacts)\b"
    r"|\bINSERT\s+INTO\s+(items|item_uoms|item_sku_codes|item_barcodes|suppliers|supplier_contacts)\b"
    r"|\bUPDATE\s+(items|item_uoms|item_sku_codes|item_barcodes|suppliers|supplier_contacts)\b"
    r"|\bDELETE\s+FROM\s+(items|item_uoms|item_sku_codes|item_barcodes|suppliers|supplier_contacts)\b",
    re.IGNORECASE,
)


def test_admin_pms_integration_service_uses_projection_tables_only() -> None:
    text = (ROOT / "app/admin/services/pms_integration_service.py").read_text(encoding="utf-8")

    assert "wms_pms_item_projection" in text
    assert "wms_pms_supplier_projection" in text
    assert "wms_pms_uom_projection" in text
    assert "wms_pms_sku_code_projection" in text
    assert "wms_pms_barcode_projection" in text
    assert "wms_pms_projection_sync_runs" in text
    assert FORBIDDEN_OWNER_SQL_RE.search(text) is None


def test_admin_pms_integration_does_not_reintroduce_pms_owner_routes_or_connection_page() -> None:
    text = (ROOT / "app/admin/routers/pms_integration.py").read_text(encoding="utf-8")

    assert "/items" not in text
    assert "/item-uoms" not in text
    assert "/item-barcodes" not in text
    assert "/pms/brands" not in text
    assert "/pms/categories" not in text
    assert "/pms/item-attribute-defs" not in text
    assert "/connection" not in text


def test_pms_projection_pages_are_rehomed_to_product_management_navigation() -> None:
    migration_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "alembic/versions").glob("*rehome_projection_pages.py")
    )

    assert "pms.projections" in migration_text
    assert "pms.projections.items" in migration_text
    assert "pms.projections.suppliers" in migration_text
    assert "pms.projections.uoms" in migration_text
    assert "pms.projections.sku_codes" in migration_text
    assert "pms.projections.barcodes" in migration_text

    assert "/pms/projections/items" in migration_text
    assert "/pms/projections/suppliers" in migration_text
    assert "/pms/projections/uoms" in migration_text
    assert "/pms/projections/sku-codes" in migration_text
    assert "/pms/projections/barcodes" in migration_text

    assert "admin.pms_integration.items" in migration_text
    assert "/admin/pms-integration/items" in migration_text
    assert "page.pms.read" in migration_text
    assert "page.pms.write" in migration_text
