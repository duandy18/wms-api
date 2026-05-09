from __future__ import annotations

from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.pms.export.items.services.item_read_service import ItemReadService
from app.pms.export.uoms.contracts.uom import PmsExportUom
from app.pms.export.uoms.services.uom_read_service import PmsExportUomReadService


async def load_item_expiry_policy(session: AsyncSession, *, item_id: int) -> str:
    svc = ItemReadService(session)
    policy = await svc.aget_policy_by_id(item_id=int(item_id))
    if policy is None:
        return "NONE"
    return str(policy.expiry_policy or "NONE").upper()


async def load_item_lot_source_policy(session: AsyncSession, *, item_id: int) -> str:
    svc = ItemReadService(session)
    policy = await svc.aget_policy_by_id(item_id=int(item_id))
    if policy is None:
        return "INTERNAL_ONLY"
    return str(policy.lot_source_policy or "INTERNAL_ONLY").upper()


def _uom_name_snapshot(row: PmsExportUom) -> Optional[str]:
    name = str(row.uom_name or row.display_name or row.uom or "").strip()
    return name or None


async def require_item_uom_ratio_to_base(
    session: AsyncSession,
    *,
    item_id: int,
    uom_id: int,
) -> Tuple[int, Optional[str]]:
    if uom_id <= 0:
        raise HTTPException(status_code=400, detail="uom_id 必须为正整数")

    row = await PmsExportUomReadService(session).aget_by_id(item_uom_id=int(uom_id))
    if row is None or int(row.item_id) != int(item_id):
        raise HTTPException(
            status_code=400,
            detail=f"uom_id 不存在或不属于该商品：item_id={int(item_id)} uom_id={int(uom_id)}",
        )

    ratio = int(row.ratio_to_base or 0)
    if ratio <= 0:
        raise HTTPException(status_code=400, detail="PMS export uom.ratio_to_base 非法（必须 >= 1）")

    return ratio, _uom_name_snapshot(row)


__all__ = [
    "load_item_expiry_policy",
    "load_item_lot_source_policy",
    "require_item_uom_ratio_to_base",
]
