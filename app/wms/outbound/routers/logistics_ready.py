# app/wms/outbound/routers/logistics_ready.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session as get_session
from app.user.deps.auth import get_current_user
from app.wms.outbound.contracts.logistics_ready import LogisticsReadyListOut
from app.wms.outbound.repos.logistics_ready_repo import (
    READY_EXPORT_STATUSES,
    READY_SOURCE_DOC_TYPES,
    count_logistics_ready_records,
    list_logistics_ready_records,
)

router = APIRouter(prefix="/wms/outbound", tags=["wms-outbound-logistics-ready"])


@router.get("/logistics-ready", response_model=LogisticsReadyListOut)
async def list_wms_outbound_logistics_ready(
    source_doc_type: str | None = Query(
        default=None,
        description="来源单据类型：ORDER_OUTBOUND / MANUAL_OUTBOUND；为空返回全部",
    ),
    export_status: str | None = Query(
        default=None,
        description="导出状态：PENDING / FAILED；为空返回 PENDING + FAILED",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
) -> LogisticsReadyListOut:
    if source_doc_type is not None and source_doc_type not in READY_SOURCE_DOC_TYPES:
        raise HTTPException(status_code=422, detail="invalid source_doc_type")

    if export_status is not None and export_status not in READY_EXPORT_STATUSES:
        raise HTTPException(status_code=422, detail="invalid export_status")

    total = await count_logistics_ready_records(
        session,
        source_doc_type=source_doc_type,
        export_status=export_status,
    )
    rows = await list_logistics_ready_records(
        session,
        source_doc_type=source_doc_type,
        export_status=export_status,
        limit=int(limit),
        offset=int(offset),
    )

    return LogisticsReadyListOut(
        ok=True,
        rows=rows,
        total=int(total),
        limit=int(limit),
        offset=int(offset),
    )
