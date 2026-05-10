# app/procurement/helpers/purchase_reports.py
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.inprocess_client import InProcessPmsReadClient


async def resolve_report_item_ids(
    session: AsyncSession,
    *,
    item_id: Optional[int],
    item_keyword: Optional[str],
) -> Optional[list[int]]:
    """
    返回：
    - [item_id]：显式 item_id 过滤
    - [ids...]：按 PMS integration item 搜索出的 item_id 集合
    - None：不加 item 过滤
    """
    if item_id is not None:
        return [int(item_id)]

    kw = str(item_keyword or "").strip()
    if not kw:
        return None

    return await InProcessPmsReadClient(session).search_report_item_ids_by_keyword(keyword=kw)
