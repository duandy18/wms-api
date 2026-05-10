# tests/ci/test_pms_export_items_openapi_contract.py
from __future__ import annotations

from typing import Any

from app.main import app
from app.pms.export.items.contracts.barcode_probe import (
    BarcodeProbeError,
    BarcodeProbeIn,
    BarcodeProbeOut,
    BarcodeProbeStatus,
)
from app.pms.export.items.contracts.item_basic import ItemBasic
from app.pms.export.items.contracts.item_policy import ItemPolicy


def _schema_props(spec: dict[str, Any], name: str) -> set[str]:
    schema = spec.get("components", {}).get("schemas", {}).get(name)
    assert isinstance(schema, dict), f"missing schema: {name}"
    props = schema.get("properties")
    assert isinstance(props, dict), f"schema has no properties: {name}"
    return set(props)


def test_pms_export_item_basic_contract_fields_are_stable() -> None:
    """
    PMS export ItemBasic 是跨域商品基础读模型。

    它只暴露商品当前态基础字段，不混入 owner 兼容字段，
    也不混入 item_uoms / item_barcodes / item_sku_codes 子表事实。
    """

    assert set(ItemBasic.model_fields) == {
        "id",
        "sku",
        "name",
        "spec",
        "enabled",
        "supplier_id",
        "brand",
        "category",
    }


def test_pms_export_item_policy_contract_fields_are_stable() -> None:
    """
    PMS export ItemPolicy 是执行域读取商品策略的稳定合同。

    WMS lot / expiry / batch 判断只能依赖该合同字段，
    不应回到 items owner 表散读。
    """

    assert set(ItemPolicy.model_fields) == {
        "item_id",
        "expiry_policy",
        "shelf_life_value",
        "shelf_life_unit",
        "lot_source_policy",
        "derivation_allowed",
        "uom_governance_enabled",
    }


def test_pms_export_barcode_probe_contract_fields_are_stable() -> None:
    """
    BarcodeProbe 是跨域条码解析合同。

    它返回条码绑定状态、item_id、item_uom_id、ratio_to_base、
    条码元信息和 ItemBasic，不承载 owner 写入 / 改绑语义。
    """

    assert {x.value for x in BarcodeProbeStatus} == {"BOUND", "UNBOUND", "ERROR"}

    assert set(BarcodeProbeIn.model_fields) == {"barcode"}

    assert set(BarcodeProbeError.model_fields) == {
        "stage",
        "error",
    }

    assert set(BarcodeProbeOut.model_fields) == {
        "ok",
        "status",
        "barcode",
        "item_id",
        "item_uom_id",
        "ratio_to_base",
        "symbology",
        "active",
        "item_basic",
        "errors",
    }


def test_pms_export_items_openapi_paths_are_registered() -> None:
    """
    PMS export item public HTTP surface 必须稳定暴露。

    注意：ItemPolicy 当前是内部 service contract，
    不在本测试中要求暴露 HTTP path。
    """

    schema = app.openapi()
    paths = schema.get("paths", {})

    assert "/pms/export/items" in paths
    assert "/pms/export/items/{item_id}" in paths
    assert "/pms/export/items/barcode-probe" in paths

    assert "get" in paths["/pms/export/items"]
    assert "get" in paths["/pms/export/items/{item_id}"]
    assert "post" in paths["/pms/export/items/barcode-probe"]


def test_pms_export_items_openapi_schemas_match_contract_fields() -> None:
    """
    runtime OpenAPI 中的 export item schemas 必须和 Python contract 对齐。
    """

    spec = app.openapi()

    assert _schema_props(spec, "ItemBasic") == set(ItemBasic.model_fields)
    assert _schema_props(spec, "BarcodeProbeIn") == set(BarcodeProbeIn.model_fields)
    assert _schema_props(spec, "BarcodeProbeError") == set(BarcodeProbeError.model_fields)
    assert _schema_props(spec, "BarcodeProbeOut") == set(BarcodeProbeOut.model_fields)
