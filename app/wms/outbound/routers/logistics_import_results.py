# app/wms/outbound/routers/logistics_import_results.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session as get_session
from app.user.deps.auth import get_current_user
from app.wms.outbound.contracts.logistics_import_results import (
    LogisticsImportResultIn,
    LogisticsImportResultOut,
)
from app.wms.outbound.repos.logistics_export_record_repo import (
    apply_logistics_import_failure,
    apply_logistics_import_success,
)

router = APIRouter(prefix="/wms/outbound", tags=["wms-outbound-logistics-import-results"])


@router.post("/logistics-import-results", response_model=LogisticsImportResultOut)
async def record_wms_outbound_logistics_import_result(
    payload: LogisticsImportResultIn,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
) -> LogisticsImportResultOut:
    try:
        if payload.export_status == "EXPORTED":
            row = await apply_logistics_import_success(
                session,
                source_ref=payload.source_ref,
                logistics_request_id=int(payload.logistics_request_id or 0),
                logistics_request_no=str(payload.logistics_request_no or ""),
            )
        else:
            row = await apply_logistics_import_failure(
                session,
                source_ref=payload.source_ref,
                error_message=str(payload.error_message or ""),
            )

        if row is None:
            await session.rollback()
            raise HTTPException(status_code=404, detail="logistics export record not found")

        await session.commit()
        return LogisticsImportResultOut(ok=True, **row)

    except HTTPException:
        raise
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        await session.rollback()
        raise
