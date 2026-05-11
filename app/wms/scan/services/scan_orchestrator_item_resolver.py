# app/wms/scan/services/scan_orchestrator_item_resolver.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.projection_read import (
    resolve_projection_barcode,
    resolve_projection_sku_code_item_id,
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
    WMS /scan probe reads barcode current-state from WMS local PMS projection.

    Boundary:
    - /scan is probe-only and does not post inventory facts;
    - this read path must not call pms-api per scan request;
    - this read path must not read PMS owner tables directly;
    - write validation remains in formal WMS submit flows and PMS HTTP integration.
    """
    code = (barcode or "").strip()
    if not code:
        return None

    try:
        resolved = await resolve_projection_barcode(session, barcode=code)
        if resolved is None:
            return None

        return ScanBarcodeResolved(
            item_id=int(resolved.item_id),
            item_uom_id=(
                int(resolved.item_uom_id)
                if resolved.item_uom_id is not None
                else None
            ),
            ratio_to_base=(
                int(resolved.ratio_to_base)
                if resolved.ratio_to_base is not None
                else None
            ),
            symbology=(
                str(resolved.symbology)
                if resolved.symbology is not None
                else None
            ),
            active=resolved.active if resolved.active is not None else None,
        )
    except Exception:
        return None


async def resolve_item_id_from_barcode(
    session: AsyncSession,
    barcode: str,
) -> Optional[int]:
    """
    兼容壳：
    - parse_scan 仍可只消费 item_id；
    - richer barcode projection result 仍由 probe_item_from_barcode 承载。
    """
    resolved = await probe_item_from_barcode(session, barcode)
    if resolved is None:
        return None
    return int(resolved.item_id)


async def resolve_item_id_from_sku(session: AsyncSession, sku: str) -> Optional[int]:
    """
    WMS /scan SKU text probe reads active sku_code current-state from projection.

    Boundary:
    - only resolves active SKU code to item_id;
    - does not require outbound default/base uom;
    - does not call pms-api per scan request;
    - does not read PMS owner tables directly.
    """
    s = (sku or "").strip().upper()
    if not s:
        return None

    try:
        return await resolve_projection_sku_code_item_id(
            session,
            sku_code=s,
            active_only=True,
        )
    except Exception:
        return None
