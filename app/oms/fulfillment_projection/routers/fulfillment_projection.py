# app/oms/fulfillment_projection/routers/fulfillment_projection.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.oms.projection_sync import OmsFulfillmentProjectionSyncError
from app.oms.fulfillment_projection.contracts.fulfillment_projection import (
    OmsProjectionCheckOut,
    OmsProjectionListOut,
    OmsProjectionPlatform,
    OmsProjectionResource,
    OmsProjectionStatusOut,
    OmsProjectionSyncOut,
    OmsProjectionSyncRunsOut,
)
from app.oms.fulfillment_projection.services.fulfillment_projection_service import (
    OmsFulfillmentProjectionService,
)
from app.user.deps.auth import get_current_user
from app.user.services.user_service import UserService

router = APIRouter(
    prefix="/fulfillment-projection",
    tags=["oms-fulfillment-projection"],
)


def _service(db: Session) -> OmsFulfillmentProjectionService:
    return OmsFulfillmentProjectionService(db)


@router.get("/status", response_model=OmsProjectionStatusOut)
def get_oms_fulfillment_projection_status(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    svc = UserService(db)
    svc.check_permission(current_user, ["page.oms.read"])
    return _service(db).get_status()


@router.get("/sync-runs", response_model=OmsProjectionSyncRunsOut)
def list_oms_fulfillment_projection_sync_runs(
    platform: OmsProjectionPlatform | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    svc = UserService(db)
    svc.check_permission(current_user, ["page.oms.read"])
    return _service(db).list_sync_runs(platform=platform, limit=limit)


@router.get("/projections/{resource}", response_model=OmsProjectionListOut)
def list_oms_fulfillment_projection_rows(
    resource: OmsProjectionResource,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    svc = UserService(db)
    svc.check_permission(current_user, ["page.oms.read"])
    return _service(db).list_projection(
        resource=resource,
        limit=limit,
        offset=offset,
        q=q,
    )


@router.post("/projections/fulfillment-ready-orders/sync", response_model=OmsProjectionSyncOut)
async def sync_oms_fulfillment_ready_orders(
    platform: OmsProjectionPlatform | None = Query(default=None),
    store_code: str | None = Query(default=None, min_length=1, max_length=128),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    svc = UserService(db)
    svc.check_permission(current_user, ["page.oms.write"])

    try:
        run = await _service(db).sync_fulfillment_ready_orders(
            platform=platform,
            store_code=store_code,
            limit=limit,
            triggered_by_user_id=int(getattr(current_user, "id")),
        )
    except (RuntimeError, OmsFulfillmentProjectionSyncError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OMS fulfillment projection sync failed: {exc}")

    return {"run": run}


@router.post("/projections/{resource}/check", response_model=OmsProjectionCheckOut)
def check_oms_fulfillment_projection_resource(
    resource: OmsProjectionResource,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    svc = UserService(db)
    svc.check_permission(current_user, ["page.oms.read"])
    return _service(db).check_projection(resource=resource, limit=limit)


__all__ = ["router"]
