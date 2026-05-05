from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CodeMappingCodeOptionOut(BaseModel):
    platform: str
    store_code: str
    merchant_code: str

    latest_title: Optional[str] = None
    platform_item_id: Optional[str] = None
    platform_sku_id: Optional[str] = None
    latest_platform_order_no: Optional[str] = None
    latest_synced_at: Optional[datetime] = None

    orders_count: int

    is_bound: bool
    binding_id: Optional[int] = None
    fsku_id: Optional[int] = None
    fsku_code: Optional[str] = None
    fsku_name: Optional[str] = None
    fsku_status: Optional[str] = None
    binding_updated_at: Optional[datetime] = None


class CodeMappingCodeOptionListDataOut(BaseModel):
    items: list[CodeMappingCodeOptionOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class CodeMappingCodeOptionListOut(BaseModel):
    ok: bool = True
    data: CodeMappingCodeOptionListDataOut
