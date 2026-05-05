from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.problem import make_problem
from app.db.deps import get_async_session as get_session
from app.oms.fsku.contracts.platform_code_mappings import (
    FskuLiteOut,
    PlatformCodeMappingBindIn,
    PlatformCodeMappingDeleteIn,
    PlatformCodeMappingListDataOut,
    PlatformCodeMappingListOut,
    PlatformCodeMappingOut,
    PlatformCodeMappingRowOut,
    StoreLiteOut,
)
from app.oms.fsku.models.fsku import Fsku
from app.oms.fsku.models.platform_code_fsku_mapping import PlatformCodeFskuMapping
from app.oms.fsku.services.platform_code_mapping_service import PlatformCodeMappingService
from app.oms.services.platform_order_resolve_service import norm_platform, norm_store_code
from app.oms.stores.models.store import Store


router = APIRouter(tags=["platform-code-mappings"])


def _row_out(*, row: PlatformCodeFskuMapping, fsku: Fsku, store: Store) -> PlatformCodeMappingRowOut:
    return PlatformCodeMappingRowOut(
        id=int(row.id),
        platform=str(row.platform),
        store_code=str(row.store_code),
        store=StoreLiteOut(id=int(store.id), store_name=str(store.store_name)),
        identity_kind=row.identity_kind,  # type: ignore[arg-type]
        identity_value=str(row.identity_value),
        fsku_id=int(row.fsku_id),
        fsku=FskuLiteOut(id=int(fsku.id), code=str(fsku.code), name=str(fsku.name), status=str(fsku.status)),
        reason=row.reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get(
    "/platform-code-mappings",
    response_model=PlatformCodeMappingListOut,
    summary="列表：平台订单行身份 → published OMS FSKU 映射",
)
async def list_platform_code_mappings(
    platform: str | None = Query(None, min_length=1, max_length=32),
    store_code: str | None = Query(None, min_length=1, max_length=128),
    identity_kind: str | None = Query(None, min_length=1, max_length=32),
    identity_value: str | None = Query(None, min_length=1, max_length=256),
    fsku_id: int | None = Query(None, ge=1),
    fsku_code: str | None = Query(None, min_length=1, max_length=128),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> PlatformCodeMappingListOut:
    try:
        plat = norm_platform(platform) if platform else None
        sid = norm_store_code(store_code) if store_code else None
        kind = (identity_kind or "").strip() or None
        value = (identity_value or "").strip() or None
        fc = (fsku_code or "").strip() or None

        conds = []
        if plat is not None:
            conds.append(PlatformCodeFskuMapping.platform == plat)
        if sid is not None:
            conds.append(PlatformCodeFskuMapping.store_code == sid)
        if kind is not None:
            conds.append(PlatformCodeFskuMapping.identity_kind == kind)
        if value is not None:
            conds.append(PlatformCodeFskuMapping.identity_value.like(f"%{value}%"))
        if fsku_id is not None:
            conds.append(PlatformCodeFskuMapping.fsku_id == int(fsku_id))
        if fc is not None:
            conds.append(Fsku.code.like(f"%{fc}%"))

        total_stmt = (
            select(func.count())
            .select_from(PlatformCodeFskuMapping)
            .join(Fsku, Fsku.id == PlatformCodeFskuMapping.fsku_id)
            .join(Store, (Store.platform == PlatformCodeFskuMapping.platform) & (Store.store_code == PlatformCodeFskuMapping.store_code))
        )
        if conds:
            total_stmt = total_stmt.where(*conds)

        total = int((await session.execute(total_stmt)).scalar_one())

        stmt = (
            select(PlatformCodeFskuMapping, Fsku, Store)
            .join(Fsku, Fsku.id == PlatformCodeFskuMapping.fsku_id)
            .join(Store, (Store.platform == PlatformCodeFskuMapping.platform) & (Store.store_code == PlatformCodeFskuMapping.store_code))
            .order_by(PlatformCodeFskuMapping.id.desc())
            .limit(int(limit))
            .offset(int(offset))
        )
        if conds:
            stmt = stmt.where(*conds)

        rows = (await session.execute(stmt)).all()
        items = [_row_out(row=item[0], fsku=item[1], store=item[2]) for item in rows]

        return PlatformCodeMappingListOut(
            ok=True,
            data=PlatformCodeMappingListDataOut(items=items, total=total, limit=int(limit), offset=int(offset)),
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=make_problem(status_code=422, error_code="request_validation_error", message=str(exc), context={}),
        ) from exc


@router.post(
    "/platform-code-mappings/bind",
    response_model=PlatformCodeMappingOut,
    summary="新增/覆盖：平台订单行身份 → published OMS FSKU",
)
async def bind_platform_code_mapping(
    payload: PlatformCodeMappingBindIn = Body(...),
    session: AsyncSession = Depends(get_session),
) -> PlatformCodeMappingOut:
    plat = norm_platform(payload.platform)
    store_code = norm_store_code(payload.store_code)

    svc = PlatformCodeMappingService(session)

    try:
        obj = await svc.bind_upsert(
            platform=plat,
            store_code=store_code,
            identity_kind=payload.identity_kind,
            identity_value=payload.identity_value,
            fsku_id=int(payload.fsku_id),
            reason=payload.reason,
        )
        await session.commit()
        await session.refresh(obj)

        fsku = await session.get(Fsku, int(obj.fsku_id))
        store = (
            await session.execute(select(Store).where(Store.platform == plat, Store.store_code == store_code).limit(1))
        ).scalars().first()

        if fsku is None or store is None:
            raise RuntimeError("映射已写入但关联展示数据缺失")

        return PlatformCodeMappingOut(ok=True, data=_row_out(row=obj, fsku=fsku, store=store))

    except PlatformCodeMappingService.BadInput as exc:
        raise HTTPException(
            status_code=422,
            detail=make_problem(status_code=422, error_code="request_validation_error", message=exc.message, context={}),
        ) from exc
    except PlatformCodeMappingService.NotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=make_problem(status_code=404, error_code="not_found", message=str(exc), context={}),
        ) from exc
    except PlatformCodeMappingService.Conflict as exc:
        raise HTTPException(
            status_code=409,
            detail=make_problem(status_code=409, error_code="conflict", message=str(exc), context={}),
        ) from exc


@router.post(
    "/platform-code-mappings/delete",
    response_model=PlatformCodeMappingOut,
    summary="删除：平台订单行身份 → OMS FSKU 映射",
)
async def delete_platform_code_mapping(
    payload: PlatformCodeMappingDeleteIn = Body(...),
    session: AsyncSession = Depends(get_session),
) -> PlatformCodeMappingOut:
    plat = norm_platform(payload.platform)
    store_code = norm_store_code(payload.store_code)
    svc = PlatformCodeMappingService(session)

    try:
        obj = await svc.delete_mapping(
            platform=plat,
            store_code=store_code,
            identity_kind=payload.identity_kind,
            identity_value=payload.identity_value,
        )

        fsku = await session.get(Fsku, int(obj.fsku_id))
        store = (
            await session.execute(select(Store).where(Store.platform == plat, Store.store_code == store_code).limit(1))
        ).scalars().first()

        await session.commit()

        if fsku is None or store is None:
            raise RuntimeError("映射已删除但关联展示数据缺失")

        return PlatformCodeMappingOut(ok=True, data=_row_out(row=obj, fsku=fsku, store=store))

    except PlatformCodeMappingService.BadInput as exc:
        raise HTTPException(
            status_code=422,
            detail=make_problem(status_code=422, error_code="request_validation_error", message=exc.message, context={}),
        ) from exc
    except PlatformCodeMappingService.NotFound as exc:
        raise HTTPException(
            status_code=404,
            detail=make_problem(status_code=404, error_code="not_found", message=str(exc), context={}),
        ) from exc
