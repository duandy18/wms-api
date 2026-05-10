from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import ItemPolicy
from app.integrations.pms.inprocess_client import InProcessPmsReadClient


async def get_item_policy_by_id(
    session: AsyncSession,
    *,
    item_id: int,
) -> ItemPolicy | None:
    return await InProcessPmsReadClient(session).get_item_policy(item_id=int(item_id))


__all__ = ["get_item_policy_by_id"]
