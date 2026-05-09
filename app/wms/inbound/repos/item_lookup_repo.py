from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.pms_projection.services.read_service import (
    WmsPmsPolicyProjectionSnapshot,
    WmsPmsProjectionReadService,
)


async def get_item_policy_by_id(
    session: AsyncSession,
    *,
    item_id: int,
) -> WmsPmsPolicyProjectionSnapshot | None:
    """
    WMS 执行侧商品策略读取入口。

    策略必须来自 WMS 本地 PMS projection：
    - 不直接读取 PMS owner items；
    - 不远程依赖 PMS export API；
    - 调用方拿到后必须继续把策略冻结进 lot / event / count 快照。
    """
    return await WmsPmsProjectionReadService(session).aget_policy_snapshot(
        item_id=int(item_id),
    )


__all__ = ["get_item_policy_by_id"]
