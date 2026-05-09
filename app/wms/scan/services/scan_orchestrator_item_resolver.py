# app/wms/scan/services/scan_orchestrator_item_resolver.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.pms_projection.services.read_service import WmsPmsProjectionReadService


@dataclass(frozen=True)
class ScanBarcodeResolved:
    item_id: int
    item_uom_id: int | None
    ratio_to_base: int | None
    symbology: str | None
    active: bool | None


async def probe_item_from_barcode(
    session: AsyncSession,
    barcode: str,
) -> Optional[ScanBarcodeResolved]:
    """
    WMS scan 读取 WMS 本地 PMS projection：

    - 不直接查询 PMS owner item_barcodes；
    - 不远程依赖 PMS export barcode probe；
    - 只返回 /scan probe 所需的商品 / 包装识别结果。
    """
    code = (barcode or "").strip()
    if not code:
        return None

    try:
        probe = await WmsPmsProjectionReadService(session).aprobe_barcode(
            barcode=code,
            active_only=True,
        )
        if probe is None:
            return None

        return ScanBarcodeResolved(
            item_id=int(probe.item_id),
            item_uom_id=int(probe.item_uom_id),
            ratio_to_base=int(probe.ratio_to_base),
            symbology=str(probe.symbology),
            active=bool(probe.active),
        )
    except Exception:
        return None


async def resolve_item_id_from_barcode(
    session: AsyncSession,
    barcode: str,
) -> Optional[int]:
    """
    兼容壳：
    - 现阶段 parse_scan 仍只消费 item_id；
    - richer 结果继续由 probe_item_from_barcode 提供。
    """
    resolved = await probe_item_from_barcode(session, barcode)
    if resolved is None:
        return None
    return int(resolved.item_id)


async def resolve_item_id_from_sku(session: AsyncSession, sku: str) -> Optional[int]:
    """
    WMS scan SKU 文本解析读取 WMS 本地 PMS sku-code projection。

    保持原语义：
    - 只要求命中 active SKU code；
    - 不要求出库默认单位 / 基础单位；
    - 不在 WMS scan 内直接读取 PMS item_sku_codes / items 表。
    """
    s = (sku or "").strip().upper()
    if not s:
        return None

    try:
        return await WmsPmsProjectionReadService(session).aresolve_active_sku_code_item_id(
            code=s,
        )
    except Exception:
        return None
