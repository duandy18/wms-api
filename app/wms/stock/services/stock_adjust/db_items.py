# app/wms/stock/services/stock_adjust/db_items.py
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.pms_projection.services.read_service import WmsPmsProjectionReadService


async def item_requires_batch(session: AsyncSession, *, item_id: int) -> bool:
    """
    WMS stock_adjust 执行层批次策略判断。

    策略真相源：
    - wms_pms_item_policy_projection.expiry_policy

    规则：
    - expiry_policy='REQUIRED' => requires_batch=True
    - expiry_policy='NONE'     => requires_batch=False

    重要：
    - item policy projection 不存在时必须明确失败；
    - 禁止 fallback 回 PMS owner items；
    - 禁止把 unknown item 默认成 NONE。
    """
    policy = await WmsPmsProjectionReadService(session).aget_policy_snapshot(
        item_id=int(item_id),
    )
    if policy is None:
        raise ValueError("item_not_found")

    return str(policy.expiry_policy or "").upper() == "REQUIRED"


__all__ = ["item_requires_batch"]
