# app/pms/export/sku_codes/contracts/sku_code.py
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PmsExportSkuCodeType = Literal["PRIMARY", "ALIAS", "LEGACY", "MANUAL"]


class PmsExportSkuCode(BaseModel):
    """
    PMS 对外 SKU 编码读模型。

    定位：
    - 只读 export contract；
    - 不承载 owner 写入、停用、启用、主编码切换语义；
    - item_sku_codes 是编码治理真相表；
    - items.sku 只是当前主 SKU 投影。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int

    code: str = Field(min_length=1)
    code_type: PmsExportSkuCodeType
    is_primary: bool
    is_active: bool

    effective_from: datetime | None = None
    effective_to: datetime | None = None
    remark: str | None = None

    item_sku: str = Field(min_length=1)
    item_name: str = Field(min_length=1)
    item_enabled: bool


class PmsExportSkuCodeResolution(BaseModel):
    """
    PMS SKU 编码解析结果。

    用途：
    - OMS FSKU 表达式组件解析；
    - 通过 SKU code 得到稳定 item_id / sku_code_id；
    - 同时返回该商品出库默认包装或基础包装，用于生成 OMS FSKU 组件快照。
    """

    model_config = ConfigDict(from_attributes=True)

    sku_code_id: int
    item_id: int

    sku_code: str = Field(min_length=1)
    code_type: PmsExportSkuCodeType
    is_primary: bool

    item_sku: str = Field(min_length=1)
    item_name: str = Field(min_length=1)

    item_uom_id: int
    uom: str
    display_name: str | None = None
    uom_name: str
    ratio_to_base: int = Field(ge=1)


__all__ = [
    "PmsExportSkuCode",
    "PmsExportSkuCodeResolution",
    "PmsExportSkuCodeType",
]
