# app/oms/services/platform_order_resolve_binding.py
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_fsku_id_by_binding(
    session: AsyncSession,
    *,
    platform: str,
    store_code: str,
    merchant_code: str,
) -> tuple[Optional[int], Optional[str]]:
    """
    Resolve merchant_code/fill_code to published OMS FSKU by platform code mapping.

    This legacy helper only receives merchant_code, so it resolves identity_kind='merchant_code'.
    Platform mirror SKU resolution supports more identity kinds directly.
    """
    code = (merchant_code or "").strip()
    if not code:
        return None, "MISSING_CODE"

    row = (
        await session.execute(
            text(
                """
                SELECT m.fsku_id, f.status AS fsku_status
                  FROM platform_code_fsku_mappings m
                  JOIN oms_fskus f ON f.id = m.fsku_id
                 WHERE m.platform = :platform
                   AND m.store_code = :store_code
                   AND m.identity_kind = 'merchant_code'
                   AND m.identity_value = :code
                 LIMIT 1
                """
            ),
            {
                "platform": platform,
                "store_code": store_code,
                "code": code,
            },
        )
    ).mappings().first()

    if not row:
        return None, "CODE_NOT_MAPPED"

    if str(row.get("fsku_status") or "") != "published":
        return None, "FSKU_NOT_PUBLISHED"

    return int(row["fsku_id"]), None
