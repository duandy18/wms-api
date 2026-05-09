# app/pms/export/uoms/routers/uoms_read.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.pms.export.uoms.contracts.uom import PmsExportUom
from app.pms.export.uoms.services.uom_read_service import PmsExportUomReadService

router = APIRouter(tags=["pms-export-uoms"])


@router.get("/pms/export/uoms", response_model=list[PmsExportUom])
def list_export_uoms(
    item_id: list[int] = Query(default=[], description="可重复：item_id=1&item_id=2"),
    item_uom_id: list[int] = Query(default=[], description="可重复：item_uom_id=1&item_uom_id=2"),
    db: Session = Depends(get_db),
) -> list[PmsExportUom]:
    return PmsExportUomReadService(db).list_uoms(
        item_ids=item_id,
        item_uom_ids=item_uom_id,
    )


@router.get("/pms/export/uoms/{item_uom_id}", response_model=PmsExportUom)
def get_export_uom(
    item_uom_id: int,
    db: Session = Depends(get_db),
) -> PmsExportUom:
    row = PmsExportUomReadService(db).get_by_id(item_uom_id=int(item_uom_id))
    if row is None:
        raise HTTPException(status_code=404, detail="item_uom_not_found")
    return row


@router.get("/pms/export/items/{item_id}/uoms", response_model=list[PmsExportUom])
def list_export_item_uoms(
    item_id: int,
    db: Session = Depends(get_db),
) -> list[PmsExportUom]:
    return PmsExportUomReadService(db).list_by_item_id(item_id=int(item_id))


__all__ = ["router"]
