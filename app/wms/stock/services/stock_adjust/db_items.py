# app/wms/stock/services/stock_adjust/db_items.py
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.factory import create_pms_read_client


async def item_requires_batch(session: AsyncSession, *, item_id: int) -> bool:
    """
    通过 PMS integration 商品策略读面判断是否批次受控。

    - expiry_policy='REQUIRED' => requires_batch=True
    - expiry_policy='NONE'     => requires_batch=False
    - item 不存在时必须明确失败，unknown item 不能默认成 NONE。
    """
    policy = await create_pms_read_client(session=session).get_item_policy(item_id=int(item_id))
    if policy is None:
        raise ValueError("item_not_found")

    return str(policy.expiry_policy or "").upper() == "REQUIRED"
