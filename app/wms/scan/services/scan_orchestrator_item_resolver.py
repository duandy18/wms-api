# app/wms/scan/services/scan_orchestrator_item_resolver.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.pms.export.items.services.barcode_probe_service import BarcodeProbeService
from app.pms.export.sku_codes.services.sku_code_read_service import (
    PmsExportSkuCodeReadService,
)


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
    WMS scan 读取链复用 PMS export barcode probe：

    - 不再直接查询 item_barcodes
    - 从 PMS BarcodeProbeService 获取主数据解析结果
    - 当前返回 richer 结构，供 parse_scan 后续阶段继续透传
    """
    code = (barcode or "").strip()
    if not code:
        return None

    try:
        probe = await BarcodeProbeService(session).aprobe(barcode=code)
        if probe.status != "BOUND":
            return None
        if probe.item_id is None:
            return None

        return ScanBarcodeResolved(
            item_id=int(probe.item_id),
            item_uom_id=(
                int(probe.item_uom_id) if probe.item_uom_id is not None else None
            ),
            ratio_to_base=(
                int(probe.ratio_to_base) if probe.ratio_to_base is not None else None
            ),
            symbology=(str(probe.symbology) if probe.symbology is not None else None),
            active=probe.active if probe.active is not None else None,
        )
    except Exception:
        return None


async def resolve_item_id_from_barcode(
    session: AsyncSession,
    barcode: str,
) -> Optional[int]:
    """
    兼容壳：
    - 现阶段 parse_scan 仍只消费 item_id
    - 后续阶段将逐步改为直接消费 probe_item_from_barcode 的 richer 结果
    """
    resolved = await probe_item_from_barcode(session, barcode)
    if resolved is None:
        return None
    return int(resolved.item_id)


async def resolve_item_id_from_sku(session: AsyncSession, sku: str) -> Optional[int]:
    """
    WMS scan SKU 文本解析复用 PMS export SKU code read service。

    保持原语义：
    - 只要求命中 active SKU code；
    - 不要求出库默认单位 / 基础单位；
    - 不在 WMS scan 内直接读取 PMS item_sku_codes / items 表。
    """
    s = (sku or "").strip().upper()
    if not s:
        return None

    try:
        rows = await PmsExportSkuCodeReadService(session).alist_sku_codes(
            code=s,
            active=True,
        )
        if not rows:
            return None
        return int(rows[0].item_id)
    except Exception:
        return None
