# app/wms/outbound/routers/logistics_shipping_results.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session as get_session
from app.user.deps.auth import get_current_user
from app.wms.outbound.contracts.logistics_shipping_results import (
    LogisticsShippingResultIn,
    LogisticsShippingResultOut,
)
from app.wms.outbound.repos.logistics_shipping_result_repo import (
    apply_logistics_shipping_results,
)

router = APIRouter(prefix="/wms/outbound", tags=["wms-outbound-logistics-shipping-results"])


@router.post("/logistics-shipping-results", response_model=LogisticsShippingResultOut)
async def record_wms_outbound_logistics_shipping_result(
    payload: LogisticsShippingResultIn,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
) -> LogisticsShippingResultOut:
    try:
        row = await apply_logistics_shipping_results(
            session,
            source_ref=payload.source_ref,
            logistics_request_id=payload.logistics_request_id,
            logistics_request_no=payload.logistics_request_no,
            completed_at=payload.completed_at,
            packages=[pkg.model_dump() for pkg in payload.packages],
        )

        if row is None:
            await session.rollback()
            raise HTTPException(status_code=404, detail="logistics export record not found")

        await session.commit()
        return LogisticsShippingResultOut(ok=True, **row)

    except HTTPException:
        raise
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        await session.rollback()
        raise
