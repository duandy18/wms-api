from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import ItemPolicy
from app.integrations.pms.factory import create_pms_read_client


async def get_item_policy_by_id(
    session: AsyncSession,
    *,
    item_id: int,
) -> ItemPolicy | None:
    return await create_pms_read_client(session=session).get_item_policy(item_id=int(item_id))


__all__ = ["get_item_policy_by_id"]
