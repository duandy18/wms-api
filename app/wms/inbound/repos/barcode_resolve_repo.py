# app/wms/inbound/repos/barcode_resolve_repo.py
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.pms_projection.services.read_service import WmsPmsProjectionReadService


@dataclass(frozen=True)
class InboundBarcodeResolved:
    """
    入库条码解析结果。

    说明：
    - 这是 WMS inbound 对 WMS 本地 PMS projection 的轻包装；
    - 只承载入库提交链真正需要的最小字段；
    - 不承载 qty / event_id / lot 等仓内执行语义。
    """

    item_id: int
    item_uom_id: int | None
    ratio_to_base: int | None
    symbology: str | None
    active: bool | None


async def resolve_inbound_barcode(
    session: AsyncSession,
    *,
    barcode: str,
) -> InboundBarcodeResolved | None:
    """
    通过 WMS PMS projection 解析入库条码。

    规则：
    - 空条码 => None
    - 未绑定/非 active => None
    - 已绑定 => 返回 item_id / item_uom_id / ratio_to_base 等最小结果
    """
    code = (barcode or "").strip()
    if not code:
        return None

    probe = await WmsPmsProjectionReadService(session).aprobe_barcode(
        barcode=code,
        active_only=True,
    )
    if probe is None:
        return None

    return InboundBarcodeResolved(
        item_id=int(probe.item_id),
        item_uom_id=int(probe.item_uom_id),
        ratio_to_base=int(probe.ratio_to_base),
        symbology=str(probe.symbology),
        active=bool(probe.active),
    )


__all__ = [
    "InboundBarcodeResolved",
    "resolve_inbound_barcode",
]
