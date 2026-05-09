# app/pms/export/barcodes/contracts/barcode.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PmsExportBarcode(BaseModel):
    """
    PMS 对外条码读模型。

    定位：
    - 只读 export contract；
    - 不承载 owner 写入、改绑、设主条码语义；
    - barcode 绑定终态来自 item_barcodes；
    - 包装语义通过 item_uom_id 关联 item_uoms。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    item_uom_id: int

    barcode: str = Field(min_length=1)
    symbology: str

    active: bool
    is_primary: bool

    uom: str
    display_name: str | None = None
    uom_name: str
    ratio_to_base: int = Field(ge=1)


__all__ = ["PmsExportBarcode"]
