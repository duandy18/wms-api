# app/pms/items/services/item_list_service.py
from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.orm import Session

from app.pms.items.contracts.item_list import (
    ItemListAttributeOut,
    ItemListBarcodeOut,
    ItemListDetailOut,
    ItemListRowOut,
    ItemListSkuCodeOut,
    ItemListUomOut,
)
from app.pms.items.repos.item_list_repo import (
    get_item_list_row_mapping,
    list_item_list_attribute_mappings,
    list_item_list_barcode_mappings,
    list_item_list_row_mappings,
    list_item_list_sku_code_mappings,
    list_item_list_uom_mappings,
)


SKU_GENERATION_PRODUCT_KINDS = {"FOOD", "SUPPLY"}
VALID_PRODUCT_KINDS = {"FOOD", "SUPPLY", "OTHER"}


def _as_bool(value: object) -> bool:
    return bool(value is True)


def _as_clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []

    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _build_completeness(row: Mapping[str, object]) -> dict[str, object]:
    raw_product_kind = _as_clean_text(row.get("product_kind"))
    product_kind = raw_product_kind if raw_product_kind in VALID_PRODUCT_KINDS else None

    has_brand = _as_bool(row.get("has_brand"))
    has_active_leaf_category = _as_bool(row.get("has_active_leaf_category"))
    has_base_uom = _as_bool(row.get("has_base_uom"))
    has_active_primary_barcode = _as_bool(row.get("has_active_primary_barcode"))
    has_active_primary_sku = _as_bool(row.get("has_active_primary_sku"))
    has_active_sku_template = _as_bool(row.get("has_active_sku_template"))

    spec = _as_clean_text(row.get("spec"))
    has_spec = spec is not None

    missing_item_required_attribute_codes = _as_str_list(
        row.get("missing_item_required_attribute_codes")
    )
    missing_sku_required_attribute_codes = _as_str_list(
        row.get("missing_sku_required_attribute_codes")
    )
    missing_sku_segment_attribute_codes = _as_str_list(
        row.get("missing_sku_segment_attribute_codes")
    )

    item_required_attributes_complete = len(missing_item_required_attribute_codes) == 0
    sku_required_attributes_complete = len(missing_sku_required_attribute_codes) == 0
    sku_segment_attributes_present = len(missing_sku_segment_attribute_codes) == 0

    sku_generation_applicable = bool(
        has_active_leaf_category and product_kind in SKU_GENERATION_PRODUCT_KINDS
    )
    can_generate_sku = bool(
        sku_generation_applicable
        and has_brand
        and has_spec
        and has_active_sku_template
        and sku_required_attributes_complete
    )

    blocking_items: list[str] = []
    warnings: list[str] = []

    if not has_brand:
        blocking_items.append("未绑定启用品牌")
    if not has_active_leaf_category:
        blocking_items.append("未绑定启用叶子分类")
    if not has_base_uom:
        blocking_items.append("未维护基础包装")
    if not has_active_primary_barcode:
        blocking_items.append("未绑定启用主条码")
    if not has_active_primary_sku:
        blocking_items.append("未维护启用主 SKU")

    for code in missing_item_required_attribute_codes:
        blocking_items.append(f"缺少商品必填属性：{code}")

    for code in missing_sku_required_attribute_codes:
        blocking_items.append(f"缺少 SKU 必填属性：{code}")

    if has_active_leaf_category and product_kind == "OTHER":
        warnings.append("OTHER 商品类型暂不支持 SKU 编码生成")
    elif has_active_leaf_category and product_kind not in SKU_GENERATION_PRODUCT_KINDS:
        warnings.append("当前商品类型暂不支持 SKU 编码生成")

    if sku_generation_applicable:
        if not has_spec:
            warnings.append("商品规格为空，不能生成候选 SKU")
        if not has_active_sku_template:
            warnings.append(f"缺少启用 SKU 编码模板：{product_kind}")
        for code in missing_sku_segment_attribute_codes:
            if code not in missing_sku_required_attribute_codes:
                warnings.append(f"缺少 SKU 段属性：{code}")

    if blocking_items:
        status = "BLOCKED"
    elif warnings:
        status = "WARNING"
    else:
        status = "COMPLETE"

    blocking_items = _unique(blocking_items)
    warnings = _unique(warnings)

    return {
        "status": status,
        "is_complete": status == "COMPLETE",
        "product_kind": product_kind,
        "has_brand": has_brand,
        "has_active_leaf_category": has_active_leaf_category,
        "has_base_uom": has_base_uom,
        "has_active_primary_barcode": has_active_primary_barcode,
        "has_active_primary_sku": has_active_primary_sku,
        "item_required_attributes_complete": item_required_attributes_complete,
        "sku_required_attributes_complete": sku_required_attributes_complete,
        "sku_segment_attributes_present": sku_segment_attributes_present,
        "sku_generation_applicable": sku_generation_applicable,
        "can_generate_sku": can_generate_sku,
        "missing_item_required_attribute_codes": missing_item_required_attribute_codes,
        "missing_sku_required_attribute_codes": missing_sku_required_attribute_codes,
        "missing_sku_segment_attribute_codes": missing_sku_segment_attribute_codes,
        "missing_items": _unique(blocking_items + warnings),
        "blocking_items": blocking_items,
        "warnings": warnings,
    }


def _row_out_from_mapping(row: Mapping[str, object]) -> ItemListRowOut:
    payload = dict(row)
    payload["completeness"] = _build_completeness(row)
    return ItemListRowOut.model_validate(payload)


class ItemListReadService:
    def __init__(self, db: Session):
        self.db = db

    def list_rows(
        self,
        *,
        enabled: bool | None = None,
        supplier_id: int | None = None,
        q: str | None = None,
        limit: int = 200,
    ) -> list[ItemListRowOut]:
        rows = list_item_list_row_mappings(
            self.db,
            enabled=enabled,
            supplier_id=supplier_id,
            q=q,
            limit=limit,
        )
        return [_row_out_from_mapping(row) for row in rows]

    def get_detail(self, *, item_id: int) -> ItemListDetailOut | None:
        row = get_item_list_row_mapping(self.db, item_id=int(item_id))
        if row is None:
            return None

        uoms = list_item_list_uom_mappings(self.db, item_id=int(item_id))
        barcodes = list_item_list_barcode_mappings(self.db, item_id=int(item_id))
        sku_codes = list_item_list_sku_code_mappings(self.db, item_id=int(item_id))
        attributes = list_item_list_attribute_mappings(self.db, item_id=int(item_id))

        return ItemListDetailOut(
            row=_row_out_from_mapping(row),
            uoms=[ItemListUomOut.model_validate(dict(x)) for x in uoms],
            barcodes=[ItemListBarcodeOut.model_validate(dict(x)) for x in barcodes],
            sku_codes=[ItemListSkuCodeOut.model_validate(dict(x)) for x in sku_codes],
            attributes=[ItemListAttributeOut.model_validate(dict(x)) for x in attributes],
        )
