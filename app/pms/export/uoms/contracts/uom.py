# app/pms/export/uoms/contracts/uom.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PmsExportUom(BaseModel):
    """
    PMS 对外包装单位读模型。

    定位：
    - 只读 export contract；
    - 不承载 owner 写入语义；
    - 供 WMS / OMS / Procurement / Finance 等跨域消费；
    - item_uoms 表仍是 PMS 内部真相源。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int

    uom: str
    display_name: str | None = None
    uom_name: str

    ratio_to_base: int = Field(ge=1)
    net_weight_kg: float | None = Field(default=None, ge=0)

    is_base: bool
    is_purchase_default: bool
    is_inbound_default: bool
    is_outbound_default: bool


__all__ = ["PmsExportUom"]
