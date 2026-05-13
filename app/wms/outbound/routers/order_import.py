# app/wms/outbound/routers/order_import.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session as get_session
from app.user.deps.auth import get_current_user
from app.wms.outbound.contracts.order_import import (
    OmsProjectionOrderImportIn,
    OmsProjectionOrderImportOut,
)
from app.wms.outbound.services.oms_projection_order_import_service import (
    import_orders_from_oms_projection,
)

router = APIRouter(prefix="/wms/outbound", tags=["wms-outbound-order-import"])


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
