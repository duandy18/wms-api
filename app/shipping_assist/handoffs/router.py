# app/shipping_assist/handoffs/router.py
#
# 分拆说明：
# - 本文件是 Shipping Assist / Handoffs 的路由入口；
# - 当前只暴露 GET /shipping-assist/handoffs；
# - import-results / shipping-results 仍由 WMS outbound 系统接口承载，不在业务页面暴露。
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session as get_session
from app.shipping_assist.handoffs.contracts import (
    ShippingHandoffListResponse,
    ShippingHandoffRow,
)
from app.shipping_assist.handoffs.repository import list_shipping_handoffs
from app.user.deps.auth import get_current_user

SourceDocType = Literal["ORDER_OUTBOUND", "MANUAL_OUTBOUND"]
ExportStatus = Literal["PENDING", "EXPORTED", "FAILED", "CANCELLED"]
LogisticsStatus = Literal[
    "NOT_IMPORTED",
    "IMPORTED",
    "IN_PROGRESS",
    "COMPLETED",
    "FAILED",
]

router = APIRouter(prefix="/shipping-assist/handoffs", tags=["shipping-assist-handoffs"])


@router.get(
    "",
    response_model=ShippingHandoffListResponse,
    summary="发货交接列表",
)
async def get_shipping_handoffs(
    source_doc_type: SourceDocType | None = Query(None),
    export_status: ExportStatus | None = Query(None),
    logistics_status: LogisticsStatus | None = Query(None),
    source_ref: str | None = Query(None, min_length=1, max_length=192),
    source_doc_no: str | None = Query(None, min_length=1, max_length=128),
    logistics_request_no: str | None = Query(None, min_length=1, max_length=64),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
) -> ShippingHandoffListResponse:
    del current_user

    total, rows = await list_shipping_handoffs(
        session=session,
        source_doc_type=source_doc_type,
        export_status=export_status,
        logistics_status=logistics_status,
        source_ref=source_ref,
        source_doc_no=source_doc_no,
        logistics_request_no=logistics_request_no,
        limit=limit,
        offset=offset,
    )

    return ShippingHandoffListResponse(
        ok=True,
        rows=[ShippingHandoffRow(**row) for row in rows],
        total=total,
    )
