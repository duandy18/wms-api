# app/wms/outbound/routers/order_read.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session as get_session
from app.user.deps.auth import get_current_user
from app.wms.outbound.contracts.order_read_options import (
    OrderOutboundOptionOut,
    OrderOutboundOptionsOut,
)
from app.wms.outbound.contracts.order_read_view import (
    OrderOutboundViewLineOut,
    OrderOutboundViewOrderOut,
    OrderOutboundViewResponse,
)
from app.wms.outbound.repos.order_read_options_repo import (
    list_order_outbound_options,
)
from app.wms.outbound.repos.order_read_view_repo import (
    load_order_outbound_head,
    load_order_outbound_lines,
)

router = APIRouter(prefix="/wms/outbound", tags=["wms-outbound-order-read"])


@router.get(
    "/orders/options",
    response_model=OrderOutboundOptionsOut,
)
async def get_wms_outbound_order_options(
    q: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    store_code: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> OrderOutboundOptionsOut:
    data = await list_order_outbound_options(
        session,
        q=q,
        platform=platform,
        store_code=store_code,
        limit=int(limit),
        offset=int(offset),
    )

    return OrderOutboundOptionsOut(
        items=[OrderOutboundOptionOut(**x) for x in data["items"]],
        total=int(data["total"]),
        limit=int(data["limit"]),
        offset=int(data["offset"]),
    )


@router.get(
    "/orders/{order_id}/view",
    response_model=OrderOutboundViewResponse,
)
async def get_wms_outbound_order_view(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> OrderOutboundViewResponse:
    head = await load_order_outbound_head(session, order_id=int(order_id))
    lines = await load_order_outbound_lines(session, order_id=int(order_id))

    return OrderOutboundViewResponse(
        ok=True,
        order=OrderOutboundViewOrderOut(**head),
        lines=[OrderOutboundViewLineOut(**x) for x in lines],
    )
