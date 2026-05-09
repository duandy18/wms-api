# tests/ci/test_pms_export_sku_codes_openapi_contract.py
from __future__ import annotations

from app.main import app
from app.pms.export.sku_codes.contracts.sku_code import (
    PmsExportSkuCode,
    PmsExportSkuCodeResolution,
)


def test_pms_export_sku_code_contract_fields_are_stable() -> None:
    fields = set(PmsExportSkuCode.model_fields)

    assert {
        "id",
        "item_id",
        "code",
        "code_type",
        "is_primary",
        "is_active",
        "effective_from",
        "effective_to",
        "remark",
        "item_sku",
        "item_name",
        "item_enabled",
    } <= fields


def test_pms_export_sku_code_resolution_contract_fields_are_stable() -> None:
    fields = set(PmsExportSkuCodeResolution.model_fields)

    assert {
        "sku_code_id",
        "item_id",
        "sku_code",
        "code_type",
        "is_primary",
        "item_sku",
        "item_name",
        "item_uom_id",
        "uom",
        "display_name",
        "uom_name",
        "ratio_to_base",
    } <= fields


def test_pms_export_sku_code_openapi_paths_are_registered() -> None:
    schema = app.openapi()
    paths = schema.get("paths", {})

    assert "/pms/export/sku-codes" in paths
    assert "/pms/export/sku-codes/resolve" in paths
    assert "/pms/export/sku-codes/{sku_code_id}" in paths
    assert "/pms/export/items/{item_id}/sku-codes" in paths

    assert "get" in paths["/pms/export/sku-codes"]
    assert "get" in paths["/pms/export/sku-codes/resolve"]
    assert "get" in paths["/pms/export/sku-codes/{sku_code_id}"]
    assert "get" in paths["/pms/export/items/{item_id}/sku-codes"]
