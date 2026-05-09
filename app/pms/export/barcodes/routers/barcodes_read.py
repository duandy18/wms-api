# app/pms/export/barcodes/routers/barcodes_read.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.pms.export.barcodes.contracts.barcode import PmsExportBarcode
from app.pms.export.barcodes.services.barcode_read_service import (
    PmsExportBarcodeReadService,
)

router = APIRouter(tags=["pms-export-barcodes"])


@router.get("/pms/export/barcodes", response_model=list[PmsExportBarcode])
def list_export_barcodes(
    item_id: list[int] = Query(default=[], description="可重复：item_id=1&item_id=2"),
    item_uom_id: list[int] = Query(
        default=[],
        description="可重复：item_uom_id=1&item_uom_id=2",
    ),
    barcode: Optional[str] = Query(default=None, description="精确条码查询"),
    active: Optional[bool] = Query(default=True, description="默认只返回 active=true；传空则不过滤"),
    primary_only: bool = Query(default=False, description="true 时只返回主条码"),
    db: Session = Depends(get_db),
) -> list[PmsExportBarcode]:
    return PmsExportBarcodeReadService(db).list_barcodes(
        item_ids=item_id,
        item_uom_ids=item_uom_id,
        barcode=barcode,
        active=active,
        primary_only=bool(primary_only),
    )


@router.get("/pms/export/barcodes/{barcode_id}", response_model=PmsExportBarcode)
def get_export_barcode(
    barcode_id: int,
    db: Session = Depends(get_db),
) -> PmsExportBarcode:
    row = PmsExportBarcodeReadService(db).get_by_id(barcode_id=int(barcode_id))
    if row is None:
        raise HTTPException(status_code=404, detail="barcode_not_found")
    return row


@router.get("/pms/export/items/{item_id}/barcodes", response_model=list[PmsExportBarcode])
def list_export_item_barcodes(
    item_id: int,
    active: Optional[bool] = Query(default=True, description="默认只返回 active=true；传空则不过滤"),
    primary_only: bool = Query(default=False, description="true 时只返回主条码"),
    db: Session = Depends(get_db),
) -> list[PmsExportBarcode]:
    return PmsExportBarcodeReadService(db).list_by_item_id(
        item_id=int(item_id),
        active=active,
        primary_only=bool(primary_only),
    )


__all__ = ["router"]
