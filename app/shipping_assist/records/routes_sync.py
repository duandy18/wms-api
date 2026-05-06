# app/shipping_assist/records/routes_sync.py
#
# 分拆说明：
# - 本文件承载 WMS 从独立 Logistics 系统拉取 shipping_records 发货事实的手动同步入口；
# - 前端只调用 WMS，本文件再调用 Logistics export API；
# - 同步服务用 warehouse_code / shipping_provider_code 映射 WMS 本地 ID，不复制 Logistics 数字主键。
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.user.deps.auth import get_current_user
from app.db.deps import get_async_session as get_session
from app.shipping_assist.records.sync.client import (
    LogisticsShippingFactsClientError,
    fetch_logistics_shipping_record_facts,
)
from app.shipping_assist.records.sync.service import (
    LogisticsShippingRecordSyncError,
    sync_logistics_shipping_record_facts_once,
)


class SyncLogisticsShippingRecordsIn(BaseModel):
    after_id: int | None = Field(default=None, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)
    platform: str | None = None
    store_code: str | None = None


class SyncLogisticsShippingRecordsOut(BaseModel):
    ok: bool = True
    fetched: int
    upserted: int
    last_cursor: int
    has_more: bool


def register(router: APIRouter) -> None:
    @router.post(
        "/sync-from-logistics",
        response_model=SyncLogisticsShippingRecordsOut,
        summary="从 Logistics 同步发货事实",
    )
    async def sync_from_logistics(
        payload: SyncLogisticsShippingRecordsIn,
        session: AsyncSession = Depends(get_session),
        current_user: Any = Depends(get_current_user),
    ) -> SyncLogisticsShippingRecordsOut:
        del current_user

        try:
            result = await sync_logistics_shipping_record_facts_once(
                session,
                after_id=payload.after_id,
                limit=payload.limit,
                platform=payload.platform,
                store_code=payload.store_code,
                fetch_facts=fetch_logistics_shipping_record_facts,
            )
            await session.commit()
        except LogisticsShippingFactsClientError as exc:
            await session.rollback()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except LogisticsShippingRecordSyncError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return SyncLogisticsShippingRecordsOut(
            ok=True,
            fetched=result.fetched,
            upserted=result.upserted,
            last_cursor=result.last_cursor,
            has_more=result.has_more,
        )
