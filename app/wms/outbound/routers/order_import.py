# app/wms/outbound/routers/order_import.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session as get_session
from app.user.deps.auth import get_current_user
from app.wms.outbound.contracts.order_import import (
    OmsProjectionOrderImportCandidatesOut,
    OmsProjectionOrderImportCandidateOut,
    OmsProjectionOrderImportIn,
    OmsProjectionOrderImportOut,
)
from app.wms.outbound.services.oms_projection_order_import_service import (
    import_orders_from_oms_projection,
    list_oms_projection_import_candidates,
)

router = APIRouter(prefix="/wms/outbound", tags=["wms-outbound-order-import"])


@router.get(
    "/orders/oms-projection-candidates",
    response_model=OmsProjectionOrderImportCandidatesOut,
)
async def list_wms_outbound_oms_projection_candidates(
    q: str | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> OmsProjectionOrderImportCandidatesOut:
    data = await list_oms_projection_import_candidates(
        session,
        q=q,
        limit=int(limit),
        offset=int(offset),
    )
    return OmsProjectionOrderImportCandidatesOut(
        items=[OmsProjectionOrderImportCandidateOut(**item) for item in data["items"]],
        total=int(data["total"]),
        limit=int(data["limit"]),
        offset=int(data["offset"]),
    )


@router.post(
    "/orders/import-from-oms-projection",
    response_model=OmsProjectionOrderImportOut,
)
async def import_wms_orders_from_oms_projection(
    payload: OmsProjectionOrderImportIn,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
) -> OmsProjectionOrderImportOut:
    result = await import_orders_from_oms_projection(
        session,
        ready_order_ids=payload.ready_order_ids,
        dry_run=bool(payload.dry_run),
        imported_by_user_id=getattr(user, "id", None),
    )
    await session.commit()
    return result
