# app/pms/export/sku_codes/routers/sku_codes_read.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.pms.export.sku_codes.contracts.sku_code import (
    PmsExportSkuCode,
    PmsExportSkuCodeResolution,
)
from app.pms.export.sku_codes.services.sku_code_read_service import (
    PmsExportSkuCodeReadService,
)

router = APIRouter(tags=["pms-export-sku-codes"])


@router.get("/pms/export/sku-codes", response_model=list[PmsExportSkuCode])
def list_export_sku_codes(
    item_id: list[int] = Query(default=[], description="可重复：item_id=1&item_id=2"),
    sku_code_id: list[int] = Query(
        default=[],
        description="可重复：sku_code_id=1&sku_code_id=2",
    ),
    code: Optional[str] = Query(default=None, description="精确 SKU code，大小写不敏感"),
    active: Optional[bool] = Query(default=True, description="默认只返回 active=true；传空则不过滤"),
    primary_only: bool = Query(default=False, description="true 时只返回主编码"),
    db: Session = Depends(get_db),
) -> list[PmsExportSkuCode]:
    return PmsExportSkuCodeReadService(db).list_sku_codes(
        item_ids=item_id,
        sku_code_ids=sku_code_id,
        code=code,
        active=active,
        primary_only=bool(primary_only),
    )


@router.get("/pms/export/sku-codes/resolve", response_model=PmsExportSkuCodeResolution)
def resolve_export_sku_code(
    code: str = Query(..., min_length=1, description="SKU code，大小写不敏感"),
    enabled_only: bool = Query(default=True, description="默认只解析 enabled=true 的商品"),
    db: Session = Depends(get_db),
) -> PmsExportSkuCodeResolution:
    row = PmsExportSkuCodeReadService(db).resolve_active_code_for_outbound_default(
        code=code,
        enabled_only=bool(enabled_only),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="sku_code_not_found_or_no_outbound_uom")
    return row


@router.get("/pms/export/sku-codes/{sku_code_id}", response_model=PmsExportSkuCode)
def get_export_sku_code(
    sku_code_id: int,
    db: Session = Depends(get_db),
) -> PmsExportSkuCode:
    row = PmsExportSkuCodeReadService(db).get_by_id(sku_code_id=int(sku_code_id))
    if row is None:
        raise HTTPException(status_code=404, detail="sku_code_not_found")
    return row


@router.get("/pms/export/items/{item_id}/sku-codes", response_model=list[PmsExportSkuCode])
def list_export_item_sku_codes(
    item_id: int,
    active: Optional[bool] = Query(default=True, description="默认只返回 active=true；传空则不过滤"),
    primary_only: bool = Query(default=False, description="true 时只返回主编码"),
    db: Session = Depends(get_db),
) -> list[PmsExportSkuCode]:
    return PmsExportSkuCodeReadService(db).list_by_item_id(
        item_id=int(item_id),
        active=active,
        primary_only=bool(primary_only),
    )


__all__ = ["router"]
