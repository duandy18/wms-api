# tests/ci/test_pms_export_barcodes_openapi_contract.py
from __future__ import annotations

from app.main import app
from app.pms.export.barcodes.contracts.barcode import PmsExportBarcode


def test_pms_export_barcode_contract_fields_are_stable() -> None:
    fields = set(PmsExportBarcode.model_fields)

    assert {
        "id",
        "item_id",
        "item_uom_id",
        "barcode",
        "symbology",
        "active",
        "is_primary",
        "uom",
        "display_name",
        "uom_name",
        "ratio_to_base",
    } <= fields


def test_pms_export_barcode_openapi_paths_are_registered() -> None:
    schema = app.openapi()
    paths = schema.get("paths", {})

    assert "/pms/export/barcodes" in paths
    assert "/pms/export/barcodes/{barcode_id}" in paths
    assert "/pms/export/items/{item_id}/barcodes" in paths

    assert "get" in paths["/pms/export/barcodes"]
    assert "get" in paths["/pms/export/barcodes/{barcode_id}"]
    assert "get" in paths["/pms/export/items/{item_id}/barcodes"]
