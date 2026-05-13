# app/pms/projections/routers/pms_projection.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.pms.projections.contracts.pms_projection import (
    PmsProjectionCheckOut,
    PmsProjectionStatusOut,
    PmsProjectionListOut,
    PmsProjectionSyncOut,
    PmsProjectionSyncRunsOut,
    ProjectionResource,
)
from app.pms.projections.services.pms_projection_service import PmsProjectionService
from app.db.session import get_db
from app.integrations.pms.projection_sync import PmsProjectionSyncError
from app.user.deps.auth import get_current_user
from app.user.services.user_service import UserService

router = APIRouter(prefix="/projections", tags=["pms-projections"])


def _service(db: Session) -> PmsProjectionService:
    return PmsProjectionService(db)


@router.get("/status", response_model=PmsProjectionStatusOut)
def get_pms_projection_sync_status(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    svc = UserService(db)
    svc.check_permission(current_user, ["page.pms.read"])
    return _service(db).get_status()


@router.get("/sync-runs", response_model=PmsProjectionSyncRunsOut)
def list_pms_projection_sync_runs(
    resource: ProjectionResource | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    svc = UserService(db)
    svc.check_permission(current_user, ["page.pms.read"])
    return _service(db).list_sync_runs(resource=resource, limit=limit)


@router.get("/{resource}", response_model=PmsProjectionListOut)
def list_pms_projection_rows(
    resource: ProjectionResource,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    svc = UserService(db)
    svc.check_permission(current_user, ["page.pms.read"])
    return _service(db).list_projection(
        resource=resource,
        limit=limit,
        offset=offset,
        q=q,
    )


@router.post("/{resource}/sync", response_model=PmsProjectionSyncOut)
async def sync_pms_projection_resource(
    resource: ProjectionResource,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    svc = UserService(db)
    svc.check_permission(current_user, ["page.pms.write"])

    try:
        run = await _service(db).sync_resource(
            resource=resource,
            triggered_by_user_id=int(getattr(current_user, "id")),
        )
    except (RuntimeError, PmsProjectionSyncError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PMS projection sync failed: {exc}")

    return {"run": run}


@router.post("/{resource}/check", response_model=PmsProjectionCheckOut)
def check_pms_projection_resource(
    resource: ProjectionResource,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    svc = UserService(db)
    svc.check_permission(current_user, ["page.pms.read"])
    return _service(db).check_projection(resource=resource, limit=limit)


__all__ = ["router"]
