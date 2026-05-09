# tests/ci/test_pms_export_uoms_openapi_contract.py
from __future__ import annotations

from app.main import app
from app.pms.export.uoms.contracts.uom import PmsExportUom


def test_pms_export_uom_contract_fields_are_stable() -> None:
    fields = set(PmsExportUom.model_fields)

    assert {
        "id",
        "item_id",
        "uom",
        "display_name",
        "uom_name",
        "ratio_to_base",
        "net_weight_kg",
        "is_base",
        "is_purchase_default",
        "is_inbound_default",
        "is_outbound_default",
    } <= fields


def test_pms_export_uom_openapi_paths_are_registered() -> None:
    schema = app.openapi()
    paths = schema.get("paths", {})

    assert "/pms/export/uoms" in paths
    assert "/pms/export/uoms/{item_uom_id}" in paths
    assert "/pms/export/items/{item_id}/uoms" in paths

    assert "get" in paths["/pms/export/uoms"]
    assert "get" in paths["/pms/export/uoms/{item_uom_id}"]
    assert "get" in paths["/pms/export/items/{item_id}/uoms"]
