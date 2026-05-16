# app/wms/inbound/routers/inbound_events.py
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.wms.system.service_auth.deps import require_wms_service_capability
from app.wms.inbound.contracts.inbound_event_read import (
    InboundEventDetailOut,
    InboundEventListOut,
)
from app.wms.inbound.contracts.procurement_receiving_result import (
    ProcurementReceivingResultDetailOut,
    ProcurementReceivingResultsOut,
)
from app.wms.inbound.services.inbound_event_read_service import (
    get_inbound_event_detail,
    list_inbound_events,
)
from app.wms.inbound.services.procurement_receiving_result_service import (
    get_procurement_receiving_result_detail,
    list_procurement_receiving_results,
)

router = APIRouter(prefix="/wms/inbound", tags=["wms-inbound-events"])

require_wms_read_procurement_receiving_results = require_wms_service_capability(
    "wms.read.procurement_receiving_results"
)


@router.get(
    "/procurement-receiving-results",
    response_model=ProcurementReceivingResultsOut,
)
async def list_procurement_receiving_results_endpoint(
    after_event_id: int = Query(default=0, ge=0, description="只返回 event_id 大于该值的收货结果"),
    limit: int = Query(default=50, ge=1, le=200, description="最多读取多少个 WMS event"),
    procurement_po_id: int | None = Query(default=None, ge=1, description="采购系统采购单 ID"),
    receipt_no: str | None = Query(default=None, description="WMS 入库单号"),
    session: AsyncSession = Depends(get_session),
    _service_permission: None = Depends(require_wms_read_procurement_receiving_results),
) -> ProcurementReceivingResultsOut:
    try:
        return await list_procurement_receiving_results(
            session,
            after_event_id=after_event_id,
            limit=limit,
            procurement_po_id=procurement_po_id,
            receipt_no=receipt_no,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/procurement-receiving-results/{event_id}",
    response_model=ProcurementReceivingResultDetailOut,
)
async def get_procurement_receiving_result_detail_endpoint(
    event_id: int,
    session: AsyncSession = Depends(get_session),
    _service_permission: None = Depends(require_wms_read_procurement_receiving_results),
) -> ProcurementReceivingResultDetailOut:
    try:
        return await get_procurement_receiving_result_detail(
            session,
            event_id=int(event_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/events", response_model=InboundEventListOut)
async def list_inbound_events_endpoint(
    warehouse_id: int | None = Query(default=None, ge=1, description="仓库 ID"),
    source_type: str | None = Query(default=None, description="来源类型"),
    source_ref: str | None = Query(default=None, description="来源单号/外部引用号"),
    date_from: datetime | None = Query(default=None, description="业务发生时间起点（含）"),
    date_to: datetime | None = Query(default=None, description="业务发生时间终点（含）"),
    limit: int = Query(default=20, ge=1, le=200, description="分页大小"),
    offset: int = Query(default=0, ge=0, description="分页偏移"),
    session: AsyncSession = Depends(get_session),
) -> InboundEventListOut:
    try:
        return await list_inbound_events(
            session,
            warehouse_id=warehouse_id,
            source_type=source_type,
            source_ref=source_ref,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/events/{event_id}", response_model=InboundEventDetailOut)
async def get_inbound_event_detail_endpoint(
    event_id: int,
    session: AsyncSession = Depends(get_session),
) -> InboundEventDetailOut:
    try:
        return await get_inbound_event_detail(
            session,
            event_id=int(event_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


__all__ = [
    "require_wms_read_procurement_receiving_results",
    "router",
]
