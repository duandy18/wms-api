# app/wms/pms_projection/services/read_service.py
# Split note:
# WMS PMS projection read service 是 WMS 执行侧读取 PMS 本地投影的统一入口。
# 业务链路不得绕过本服务直接读取 PMS owner 表。
from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.pms_projection.models.projection import (
    WmsPmsItemBarcodeProjection,
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


class WmsPmsProjectionReadService:
    """
    WMS PMS projection 只读服务。

    当前职责：
    - barcode -> item / item_uom / ratio_to_base；
    - sku code -> item_id；
    - item_uom -> uom_name。

    明确不负责：
    - 不读取 PMS owner 表；
    - 不修改 projection；
    - 不承担库存提交语义。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
        return WmsPmsBarcodeProjectionResolution(
            item_id=int(barcode_row.item_id),
            item_uom_id=int(barcode_row.item_uom_id),
            ratio_to_base=int(uom_row.ratio_to_base),
            symbology=str(barcode_row.symbology),
            active=bool(barcode_row.active),
            uom=str(uom_row.uom),
            display_name=(
                str(uom_row.display_name).strip()
                if uom_row.display_name is not None
                else None
            ),
            uom_name=_uom_name(
                uom=str(uom_row.uom),
                display_name=uom_row.display_name,
            ),
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

        stmt = (
            select(WmsPmsItemUomProjection.uom, WmsPmsItemUomProjection.display_name)
            .where(WmsPmsItemUomProjection.item_uom_id == int(item_uom_id))
            .where(WmsPmsItemUomProjection.item_id == int(item_id))
            .limit(1)
        )
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None

        uom, display_name = row
        return _uom_name(uom=str(uom), display_name=display_name)


__all__ = [
    "WmsPmsBarcodeProjectionResolution",
    "WmsPmsProjectionReadService",
]
