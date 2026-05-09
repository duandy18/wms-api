# app/wms/pms_projection/services/rebuild_service.py
# Split note:
# 本服务是 WMS PMS projection 的全量初始化 / 重建适配层。
# 在 PMS 物理独立前，只有本边界允许集中读取 PMS owner 表并写入 WMS 本地 projection。
# 业务执行链不得绕过 projection 直接读取 PMS owner 表。
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.pms.items.models.item import Item
from app.pms.items.models.item_barcode import ItemBarcode
from app.pms.items.models.item_sku_code import ItemSkuCode
from app.pms.items.models.item_uom import ItemUOM
from app.wms.pms_projection.models.projection import (
    WmsPmsItemBarcodeProjection,
    WmsPmsItemPolicyProjection,
    WmsPmsItemProjection,
    WmsPmsItemSkuCodeProjection,
    WmsPmsItemUomProjection,
)


@dataclass(frozen=True, slots=True)
class WmsPmsProjectionRebuildResult:
    source_items: int
    source_uoms: int
    source_policies: int
    source_sku_codes: int
    source_barcodes: int
    deleted_items: int
    deleted_uoms: int
    deleted_policies: int
    deleted_sku_codes: int
    deleted_barcodes: int


def _rowcount(result: object) -> int:
    raw = getattr(result, "rowcount", 0)
    if isinstance(raw, int) and raw > 0:
        return raw
    return 0


def _enum_text(value: object, *, label: str) -> str:
    raw = getattr(value, "value", value)
    if raw is None:
        raise RuntimeError(f"{label} is required")
    text = str(raw).strip()
    if text == "":
        raise RuntimeError(f"{label} is blank")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_datetime(value: object, *, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise RuntimeError(f"{label} must be datetime, got {type(value)!r}")
    return value


class WmsPmsProjectionRebuildService:
    """
    WMS PMS projection 全量重建服务。

    当前阶段职责：
    - 从 PMS owner 表读取商品、包装单位、条码、SKU code、策略；
    - 写入 WMS 本地 wms_pms_*_projection；
    - 支持幂等重复执行；
    - 清理 projection 中已不存在于 PMS owner 的陈旧行。

    明确不负责：
    - 不接入 WMS scan；
    - 不接入 inbound commit；
    - 不接入 ledger / count / return inbound；
    - 不实现 PMS outbox / changes 增量同步。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rebuild_all(self) -> WmsPmsProjectionRebuildResult:
        item_rows = (await self.session.execute(self._items_stmt())).mappings().all()
        uom_rows = (await self.session.execute(self._uoms_stmt())).mappings().all()
        sku_code_rows = (await self.session.execute(self._sku_codes_stmt())).mappings().all()
        barcode_rows = (await self.session.execute(self._barcodes_stmt())).mappings().all()

        item_ids = {int(row["id"]) for row in item_rows}
        uom_ids = {int(row["id"]) for row in uom_rows}
        sku_code_ids = {int(row["id"]) for row in sku_code_rows}
        barcode_ids = {int(row["id"]) for row in barcode_rows}

        deleted_barcodes = await self._delete_stale(
            WmsPmsItemBarcodeProjection,
            WmsPmsItemBarcodeProjection.barcode_id,
            barcode_ids,
        )
        deleted_sku_codes = await self._delete_stale(
            WmsPmsItemSkuCodeProjection,
            WmsPmsItemSkuCodeProjection.sku_code_id,
            sku_code_ids,
        )
        deleted_policies = await self._delete_stale(
            WmsPmsItemPolicyProjection,
            WmsPmsItemPolicyProjection.item_id,
            item_ids,
        )
        deleted_uoms = await self._delete_stale(
            WmsPmsItemUomProjection,
            WmsPmsItemUomProjection.item_uom_id,
            uom_ids,
        )
        deleted_items = await self._delete_stale(
            WmsPmsItemProjection,
            WmsPmsItemProjection.item_id,
            item_ids,
        )

        await self._upsert_items(item_rows)
        await self._upsert_uoms(uom_rows)
        await self._upsert_policies(item_rows)
        await self._upsert_sku_codes(sku_code_rows)
        await self._upsert_barcodes(barcode_rows)

        await self.session.flush()

        return WmsPmsProjectionRebuildResult(
            source_items=len(item_rows),
            source_uoms=len(uom_rows),
            source_policies=len(item_rows),
            source_sku_codes=len(sku_code_rows),
            source_barcodes=len(barcode_rows),
            deleted_items=deleted_items,
            deleted_uoms=deleted_uoms,
            deleted_policies=deleted_policies,
            deleted_sku_codes=deleted_sku_codes,
            deleted_barcodes=deleted_barcodes,
        )

    @staticmethod
    def _items_stmt():
        return (
            select(
                Item.id,
                Item.sku,
                Item.name,
                Item.spec,
                Item.enabled,
                Item.brand_id,
                Item.category_id,
                Item.updated_at,
                Item.lot_source_policy,
                Item.expiry_policy,
                Item.shelf_life_value,
                Item.shelf_life_unit,
                Item.derivation_allowed,
                Item.uom_governance_enabled,
            )
            .order_by(Item.id.asc())
        )

    @staticmethod
    def _uoms_stmt():
        return (
            select(
                ItemUOM.id,
                ItemUOM.item_id,
                ItemUOM.uom,
                ItemUOM.display_name,
                ItemUOM.ratio_to_base,
                ItemUOM.is_base,
                ItemUOM.is_purchase_default,
                ItemUOM.is_inbound_default,
                ItemUOM.is_outbound_default,
                ItemUOM.net_weight_kg,
                ItemUOM.updated_at,
            )
            .order_by(ItemUOM.item_id.asc(), ItemUOM.id.asc())
        )

    @staticmethod
    def _sku_codes_stmt():
        return (
            select(
                ItemSkuCode.id,
                ItemSkuCode.item_id,
                ItemSkuCode.code,
                ItemSkuCode.code_type,
                ItemSkuCode.is_primary,
                ItemSkuCode.is_active,
                ItemSkuCode.effective_from,
                ItemSkuCode.effective_to,
                ItemSkuCode.remark,
                ItemSkuCode.updated_at,
            )
            .order_by(ItemSkuCode.item_id.asc(), ItemSkuCode.id.asc())
        )

    @staticmethod
    def _barcodes_stmt():
        return (
            select(
                ItemBarcode.id,
                ItemBarcode.item_id,
                ItemBarcode.item_uom_id,
                ItemBarcode.barcode,
                ItemBarcode.active,
                ItemBarcode.is_primary,
                ItemBarcode.symbology,
                ItemBarcode.updated_at,
            )
            .order_by(ItemBarcode.item_id.asc(), ItemBarcode.id.asc())
        )

    async def _delete_stale(
        self,
        model: type[object],
        id_column: sa.ColumnElement[int],
        source_ids: set[int],
    ) -> int:
        stmt = sa.delete(model)
        if source_ids:
            stmt = stmt.where(~id_column.in_(sorted(source_ids)))
        result = await self.session.execute(stmt)
        return _rowcount(result)

    async def _upsert_items(self, rows: list[sa.RowMapping]) -> None:
        values: list[dict[str, object]] = []
        for row in rows:
            values.append(
                {
                    "item_id": int(row["id"]),
                    "sku": str(row["sku"]),
                    "name": str(row["name"]),
                    "spec": _optional_text(row["spec"]),
                    "enabled": bool(row["enabled"]),
                    "brand_id": int(row["brand_id"]) if row["brand_id"] is not None else None,
                    "category_id": (
                        int(row["category_id"])
                        if row["category_id"] is not None
                        else None
                    ),
                    "source_updated_at": _required_datetime(
                        row["updated_at"],
                        label=f"items.updated_at item_id={int(row['id'])}",
                    ),
                    "source_event_id": None,
                    "source_version": None,
                }
            )

        if not values:
            return

        stmt = pg_insert(WmsPmsItemProjection).values(values)
        await self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=["item_id"],
                set_={
                    "sku": stmt.excluded.sku,
                    "name": stmt.excluded.name,
                    "spec": stmt.excluded.spec,
                    "enabled": stmt.excluded.enabled,
                    "brand_id": stmt.excluded.brand_id,
                    "category_id": stmt.excluded.category_id,
                    "source_updated_at": stmt.excluded.source_updated_at,
                    "source_event_id": stmt.excluded.source_event_id,
                    "source_version": stmt.excluded.source_version,
                    "synced_at": sa.func.now(),
                    "updated_at": sa.func.now(),
                },
            )
        )

    async def _upsert_uoms(self, rows: list[sa.RowMapping]) -> None:
        values: list[dict[str, object]] = []
        for row in rows:
            values.append(
                {
                    "item_uom_id": int(row["id"]),
                    "item_id": int(row["item_id"]),
                    "uom": str(row["uom"]),
                    "display_name": _optional_text(row["display_name"]),
                    "ratio_to_base": int(row["ratio_to_base"]),
                    "is_base": bool(row["is_base"]),
                    "is_purchase_default": bool(row["is_purchase_default"]),
                    "is_inbound_default": bool(row["is_inbound_default"]),
                    "is_outbound_default": bool(row["is_outbound_default"]),
                    "net_weight_kg": (
                        Decimal(str(row["net_weight_kg"]))
                        if row["net_weight_kg"] is not None
                        else None
                    ),
                    "source_updated_at": _required_datetime(
                        row["updated_at"],
                        label=f"item_uoms.updated_at item_uom_id={int(row['id'])}",
                    ),
                    "source_event_id": None,
                    "source_version": None,
                }
            )

        if not values:
            return

        stmt = pg_insert(WmsPmsItemUomProjection).values(values)
        await self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=["item_uom_id"],
                set_={
                    "item_id": stmt.excluded.item_id,
                    "uom": stmt.excluded.uom,
                    "display_name": stmt.excluded.display_name,
                    "ratio_to_base": stmt.excluded.ratio_to_base,
                    "is_base": stmt.excluded.is_base,
                    "is_purchase_default": stmt.excluded.is_purchase_default,
                    "is_inbound_default": stmt.excluded.is_inbound_default,
                    "is_outbound_default": stmt.excluded.is_outbound_default,
                    "net_weight_kg": stmt.excluded.net_weight_kg,
                    "source_updated_at": stmt.excluded.source_updated_at,
                    "source_event_id": stmt.excluded.source_event_id,
                    "source_version": stmt.excluded.source_version,
                    "synced_at": sa.func.now(),
                    "updated_at": sa.func.now(),
                },
            )
        )

    async def _upsert_policies(self, rows: list[sa.RowMapping]) -> None:
        values: list[dict[str, object]] = []
        for row in rows:
            item_id = int(row["id"])
            values.append(
                {
                    "item_id": item_id,
                    "lot_source_policy": _enum_text(
                        row["lot_source_policy"],
                        label=f"items.lot_source_policy item_id={item_id}",
                    ),
                    "expiry_policy": _enum_text(
                        row["expiry_policy"],
                        label=f"items.expiry_policy item_id={item_id}",
                    ),
                    "shelf_life_value": (
                        int(row["shelf_life_value"])
                        if row["shelf_life_value"] is not None
                        else None
                    ),
                    "shelf_life_unit": _optional_text(row["shelf_life_unit"]),
                    "derivation_allowed": bool(row["derivation_allowed"]),
                    "uom_governance_enabled": bool(row["uom_governance_enabled"]),
                    "source_updated_at": _required_datetime(
                        row["updated_at"],
                        label=f"items.updated_at item_id={item_id}",
                    ),
                    "source_event_id": None,
                    "source_version": None,
                }
            )

        if not values:
            return

        stmt = pg_insert(WmsPmsItemPolicyProjection).values(values)
        await self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=["item_id"],
                set_={
                    "lot_source_policy": stmt.excluded.lot_source_policy,
                    "expiry_policy": stmt.excluded.expiry_policy,
                    "shelf_life_value": stmt.excluded.shelf_life_value,
                    "shelf_life_unit": stmt.excluded.shelf_life_unit,
                    "derivation_allowed": stmt.excluded.derivation_allowed,
                    "uom_governance_enabled": stmt.excluded.uom_governance_enabled,
                    "source_updated_at": stmt.excluded.source_updated_at,
                    "source_event_id": stmt.excluded.source_event_id,
                    "source_version": stmt.excluded.source_version,
                    "synced_at": sa.func.now(),
                    "updated_at": sa.func.now(),
                },
            )
        )

    async def _upsert_sku_codes(self, rows: list[sa.RowMapping]) -> None:
        values: list[dict[str, object]] = []
        for row in rows:
            values.append(
                {
                    "sku_code_id": int(row["id"]),
                    "item_id": int(row["item_id"]),
                    "code": str(row["code"]),
                    "code_type": str(row["code_type"]),
                    "is_primary": bool(row["is_primary"]),
                    "is_active": bool(row["is_active"]),
                    "effective_from": row["effective_from"],
                    "effective_to": row["effective_to"],
                    "remark": _optional_text(row["remark"]),
                    "source_updated_at": _required_datetime(
                        row["updated_at"],
                        label=f"item_sku_codes.updated_at sku_code_id={int(row['id'])}",
                    ),
                    "source_event_id": None,
                    "source_version": None,
                }
            )

        if not values:
            return

        stmt = pg_insert(WmsPmsItemSkuCodeProjection).values(values)
        await self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=["sku_code_id"],
                set_={
                    "item_id": stmt.excluded.item_id,
                    "code": stmt.excluded.code,
                    "code_type": stmt.excluded.code_type,
                    "is_primary": stmt.excluded.is_primary,
                    "is_active": stmt.excluded.is_active,
                    "effective_from": stmt.excluded.effective_from,
                    "effective_to": stmt.excluded.effective_to,
                    "remark": stmt.excluded.remark,
                    "source_updated_at": stmt.excluded.source_updated_at,
                    "source_event_id": stmt.excluded.source_event_id,
                    "source_version": stmt.excluded.source_version,
                    "synced_at": sa.func.now(),
                    "updated_at": sa.func.now(),
                },
            )
        )

    async def _upsert_barcodes(self, rows: list[sa.RowMapping]) -> None:
        values: list[dict[str, object]] = []
        for row in rows:
            values.append(
                {
                    "barcode_id": int(row["id"]),
                    "item_id": int(row["item_id"]),
                    "item_uom_id": int(row["item_uom_id"]),
                    "barcode": str(row["barcode"]),
                    "active": bool(row["active"]),
                    "is_primary": bool(row["is_primary"]),
                    "symbology": str(row["symbology"]),
                    "source_updated_at": _required_datetime(
                        row["updated_at"],
                        label=f"item_barcodes.updated_at barcode_id={int(row['id'])}",
                    ),
                    "source_event_id": None,
                    "source_version": None,
                }
            )

        if not values:
            return

        stmt = pg_insert(WmsPmsItemBarcodeProjection).values(values)
        await self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=["barcode_id"],
                set_={
                    "item_id": stmt.excluded.item_id,
                    "item_uom_id": stmt.excluded.item_uom_id,
                    "barcode": stmt.excluded.barcode,
                    "active": stmt.excluded.active,
                    "is_primary": stmt.excluded.is_primary,
                    "symbology": stmt.excluded.symbology,
                    "source_updated_at": stmt.excluded.source_updated_at,
                    "source_event_id": stmt.excluded.source_event_id,
                    "source_version": stmt.excluded.source_version,
                    "synced_at": sa.func.now(),
                    "updated_at": sa.func.now(),
                },
            )
        )
