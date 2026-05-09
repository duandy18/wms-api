# app/wms/pms_projection/services/read_service.py
# Split note:
# WMS PMS projection read service 是 WMS 执行侧读取 PMS 本地投影的统一入口。
# 业务链路不得绕过本服务直接读取 PMS owner 表。
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.pms_projection.models.projection import (
    WmsPmsItemBarcodeProjection,
    WmsPmsItemPolicyProjection,
    WmsPmsItemProjection,
    WmsPmsItemSkuCodeProjection,
    WmsPmsItemUomProjection,
)


def _norm_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _uom_name(*, uom: str, display_name: str | None) -> str:
    name = str(display_name or "").strip()
    if name:
        return name
    return str(uom or "").strip()


def _enum_text(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").strip()


@dataclass(frozen=True, slots=True)
class WmsPmsItemProjectionSnapshot:
    item_id: int
    sku: str
    name: str
    spec: str | None
    enabled: bool
    brand_id: int | None
    category_id: int | None
    source_updated_at: datetime


@dataclass(frozen=True, slots=True)
class WmsPmsUomProjectionSnapshot:
    item_uom_id: int
    item_id: int
    uom: str
    display_name: str | None
    uom_name: str
    ratio_to_base: int
    is_base: bool
    is_purchase_default: bool
    is_inbound_default: bool
    is_outbound_default: bool
    net_weight_kg: Decimal | None
    source_updated_at: datetime


@dataclass(frozen=True, slots=True)
class WmsPmsPolicyProjectionSnapshot:
    item_id: int
    lot_source_policy: str
    expiry_policy: str
    shelf_life_value: int | None
    shelf_life_unit: str | None
    derivation_allowed: bool
    uom_governance_enabled: bool
    source_updated_at: datetime


@dataclass(frozen=True, slots=True)
class WmsPmsBarcodeProjectionResolution:
    item_id: int
    item_uom_id: int
    ratio_to_base: int
    symbology: str
    active: bool
    uom: str
    display_name: str | None
    uom_name: str


def _item_snapshot(row: WmsPmsItemProjection) -> WmsPmsItemProjectionSnapshot:
    return WmsPmsItemProjectionSnapshot(
        item_id=int(row.item_id),
        sku=str(row.sku),
        name=str(row.name),
        spec=_norm_text(row.spec),
        enabled=bool(row.enabled),
        brand_id=int(row.brand_id) if row.brand_id is not None else None,
        category_id=int(row.category_id) if row.category_id is not None else None,
        source_updated_at=row.source_updated_at,
    )


def _uom_snapshot(row: WmsPmsItemUomProjection) -> WmsPmsUomProjectionSnapshot:
    display_name = _norm_text(row.display_name)
    uom = str(row.uom)
    return WmsPmsUomProjectionSnapshot(
        item_uom_id=int(row.item_uom_id),
        item_id=int(row.item_id),
        uom=uom,
        display_name=display_name,
        uom_name=_uom_name(uom=uom, display_name=display_name),
        ratio_to_base=int(row.ratio_to_base),
        is_base=bool(row.is_base),
        is_purchase_default=bool(row.is_purchase_default),
        is_inbound_default=bool(row.is_inbound_default),
        is_outbound_default=bool(row.is_outbound_default),
        net_weight_kg=row.net_weight_kg,
        source_updated_at=row.source_updated_at,
    )


def _policy_snapshot(row: WmsPmsItemPolicyProjection) -> WmsPmsPolicyProjectionSnapshot:
    return WmsPmsPolicyProjectionSnapshot(
        item_id=int(row.item_id),
        lot_source_policy=_enum_text(row.lot_source_policy),
        expiry_policy=_enum_text(row.expiry_policy),
        shelf_life_value=(
            int(row.shelf_life_value)
            if row.shelf_life_value is not None
            else None
        ),
        shelf_life_unit=_norm_text(row.shelf_life_unit),
        derivation_allowed=bool(row.derivation_allowed),
        uom_governance_enabled=bool(row.uom_governance_enabled),
        source_updated_at=row.source_updated_at,
    )


class WmsPmsProjectionReadService:
    """
    WMS PMS projection 只读服务。

    当前职责：
    - barcode -> item / item_uom / ratio_to_base；
    - sku code -> item_id；
    - item / uom / policy projection snapshot；
    - base / inbound default UOM lookup。

    明确不负责：
    - 不读取 PMS owner 表；
    - 不修改 projection；
    - 不承担库存提交语义；
    - 不创建 lot / ledger / stock fact。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def aget_item_snapshot(
        self,
        *,
        item_id: int,
        enabled_only: bool = False,
    ) -> WmsPmsItemProjectionSnapshot | None:
        stmt = (
            select(WmsPmsItemProjection)
            .where(WmsPmsItemProjection.item_id == int(item_id))
            .limit(1)
        )
        if enabled_only:
            stmt = stmt.where(WmsPmsItemProjection.enabled.is_(True))

        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _item_snapshot(row)

    async def aget_uom_snapshot(
        self,
        *,
        item_id: int,
        item_uom_id: int,
    ) -> WmsPmsUomProjectionSnapshot | None:
        stmt = (
            select(WmsPmsItemUomProjection)
            .where(WmsPmsItemUomProjection.item_id == int(item_id))
            .where(WmsPmsItemUomProjection.item_uom_id == int(item_uom_id))
            .limit(1)
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _uom_snapshot(row)

    async def aget_base_uom_snapshot(
        self,
        *,
        item_id: int,
    ) -> WmsPmsUomProjectionSnapshot | None:
        stmt = (
            select(WmsPmsItemUomProjection)
            .where(WmsPmsItemUomProjection.item_id == int(item_id))
            .where(WmsPmsItemUomProjection.is_base.is_(True))
            .order_by(WmsPmsItemUomProjection.item_uom_id.asc())
            .limit(1)
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _uom_snapshot(row)

    async def aget_inbound_default_uom_snapshot(
        self,
        *,
        item_id: int,
    ) -> WmsPmsUomProjectionSnapshot | None:
        stmt = (
            select(WmsPmsItemUomProjection)
            .where(WmsPmsItemUomProjection.item_id == int(item_id))
            .where(WmsPmsItemUomProjection.is_inbound_default.is_(True))
            .order_by(WmsPmsItemUomProjection.item_uom_id.asc())
            .limit(1)
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _uom_snapshot(row)

    async def aget_policy_snapshot(
        self,
        *,
        item_id: int,
    ) -> WmsPmsPolicyProjectionSnapshot | None:
        stmt = (
            select(WmsPmsItemPolicyProjection)
            .where(WmsPmsItemPolicyProjection.item_id == int(item_id))
            .limit(1)
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return _policy_snapshot(row)

    async def aprobe_barcode(
        self,
        *,
        barcode: str,
        active_only: bool = True,
    ) -> WmsPmsBarcodeProjectionResolution | None:
        code = _norm_text(barcode)
        if code is None:
            return None

        stmt = (
            select(WmsPmsItemBarcodeProjection, WmsPmsItemUomProjection)
            .join(
                WmsPmsItemUomProjection,
                (WmsPmsItemUomProjection.item_uom_id == WmsPmsItemBarcodeProjection.item_uom_id)
                & (WmsPmsItemUomProjection.item_id == WmsPmsItemBarcodeProjection.item_id),
            )
            .where(WmsPmsItemBarcodeProjection.barcode == code)
            .order_by(
                WmsPmsItemBarcodeProjection.is_primary.desc(),
                WmsPmsItemBarcodeProjection.active.desc(),
                WmsPmsItemBarcodeProjection.barcode_id.asc(),
            )
            .limit(1)
        )
        if active_only:
            stmt = stmt.where(WmsPmsItemBarcodeProjection.active.is_(True))

        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None

        barcode_row, uom_row = row
        display_name = _norm_text(uom_row.display_name)
        uom = str(uom_row.uom)
        return WmsPmsBarcodeProjectionResolution(
            item_id=int(barcode_row.item_id),
            item_uom_id=int(barcode_row.item_uom_id),
            ratio_to_base=int(uom_row.ratio_to_base),
            symbology=str(barcode_row.symbology),
            active=bool(barcode_row.active),
            uom=uom,
            display_name=display_name,
            uom_name=_uom_name(uom=uom, display_name=display_name),
        )

    async def aresolve_active_sku_code_item_id(self, *, code: str) -> int | None:
        norm = _norm_text(code)
        if norm is None:
            return None

        stmt = (
            select(WmsPmsItemSkuCodeProjection.item_id)
            .where(sa.func.lower(WmsPmsItemSkuCodeProjection.code) == norm.lower())
            .where(WmsPmsItemSkuCodeProjection.is_active.is_(True))
            .order_by(
                WmsPmsItemSkuCodeProjection.is_primary.desc(),
                WmsPmsItemSkuCodeProjection.sku_code_id.asc(),
            )
            .limit(1)
        )
        value = (await self.session.execute(stmt)).scalar_one_or_none()
        return int(value) if value is not None else None

    async def aget_uom_name(
        self,
        *,
        item_id: int,
        item_uom_id: int | None,
    ) -> str | None:
        if item_uom_id is None:
            return None

        uom = await self.aget_uom_snapshot(
            item_id=int(item_id),
            item_uom_id=int(item_uom_id),
        )
        if uom is None:
            return None
        return uom.uom_name


__all__ = [
    "WmsPmsItemProjectionSnapshot",
    "WmsPmsUomProjectionSnapshot",
    "WmsPmsPolicyProjectionSnapshot",
    "WmsPmsBarcodeProjectionResolution",
    "WmsPmsProjectionReadService",
]
