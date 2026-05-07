
# app/shipping_assist/handoffs/router.py
#
# 分拆说明：
# - 本文件是 Shipping Assist / Handoffs 的路由入口；
# - GET /shipping-assist/handoffs：页面只读交接列表；
# - GET /shipping-assist/handoffs/ready：独立 Logistics 拉取待导入交接数据；
# - POST /shipping-assist/handoffs/import-results：独立 Logistics 导入结果回写；
# - POST /shipping-assist/handoffs/shipping-results：独立 Logistics 发货完成结果回写；
# - 旧 /wms/outbound/logistics-* 不保留兼容。
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session as get_session
from app.shipping_assist.handoffs.contracts import (
    ShippingHandoffListResponse,
    ShippingHandoffRow,
)
from app.shipping_assist.handoffs.contracts_machine import (
    LogisticsImportResultIn,
    LogisticsImportResultOut,
    LogisticsReadyListOut,
    LogisticsShippingResultIn,
    LogisticsShippingResultOut,
)
from app.shipping_assist.handoffs.repository import list_shipping_handoffs
from app.shipping_assist.handoffs.repository_import_results import (
    apply_logistics_import_failure,
    apply_logistics_import_success,
)
from app.shipping_assist.handoffs.repository_ready import (
    count_logistics_ready_records,
    list_logistics_ready_records,
)
from app.shipping_assist.handoffs.repository_shipping_results import (
    apply_logistics_shipping_results,
)
from app.user.deps.auth import get_current_user

SourceDocType = Literal["ORDER_OUTBOUND", "MANUAL_OUTBOUND"]
ExportStatus = Literal["PENDING", "EXPORTED", "FAILED", "CANCELLED"]
ReadyExportStatus = Literal["PENDING", "FAILED"]
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


@router.get(
    "/ready",
    response_model=LogisticsReadyListOut,
    summary="独立 Logistics 拉取待导入交接数据",
)
async def list_shipping_assist_handoff_ready(
    source_doc_type: SourceDocType | None = Query(
        default=None,
        description="来源单据类型：ORDER_OUTBOUND / MANUAL_OUTBOUND；为空返回全部",
    ),
    export_status: ReadyExportStatus | None = Query(
        default=None,
        description="导出状态：PENDING / FAILED；为空返回 PENDING + FAILED",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
) -> LogisticsReadyListOut:
    del current_user

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


@router.post(
    "/import-results",
    response_model=LogisticsImportResultOut,
    summary="独立 Logistics 导入结果回写",
)
async def record_shipping_assist_handoff_import_result(
    payload: LogisticsImportResultIn,
    session: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
) -> LogisticsImportResultOut:
    del current_user

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


@router.post(
    "/shipping-results",
    response_model=LogisticsShippingResultOut,
    summary="独立 Logistics 发货完成结果回写",
)
async def record_shipping_assist_handoff_shipping_result(
    payload: LogisticsShippingResultIn,
    session: AsyncSession = Depends(get_session),
    current_user: Any = Depends(get_current_user),
) -> LogisticsShippingResultOut:
    del current_user

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
