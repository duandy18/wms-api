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


def test_admin_pms_integration_migration_retires_old_pms_pages_and_route_prefixes() -> None:
    text = (
        ROOT / "alembic/versions/8a4f2d6c9b31_add_wms_pms_projection_sync_admin_ops.py"
    ).read_text(encoding="utf-8")

    assert "wms_pms_projection_sync_runs" in text

    for old_page_code in [
        "pms",
        "pms.items",
        "pms.brands",
        "pms.categories",
        "pms.item_attributes",
        "pms.sku_coding",
        "pms.item_barcodes",
        "pms.item_uoms",
    ]:
        assert old_page_code in text

    for old_route_prefix in [
        "/items",
        "/item-barcodes",
        "/item-uoms",
        "/items/sku-coding",
        "/pms/brands",
        "/pms/categories",
        "/pms/item-attribute-defs",
    ]:
        assert old_route_prefix in text

    for new_page_code in [
        "admin.pms_integration",
        "admin.pms_integration.items",
        "admin.pms_integration.suppliers",
        "admin.pms_integration.uoms",
        "admin.pms_integration.sku_codes",
        "admin.pms_integration.barcodes",
    ]:
        assert new_page_code in text

    assert "admin.pms_integration.connection" not in text
    assert "/admin/pms-integration/connection" not in text
