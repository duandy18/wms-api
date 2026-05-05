from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


IdentityKind = Literal["merchant_code", "platform_sku_id", "platform_item_sku"]


class PlatformCodeMappingBindIn(BaseModel):
    platform: str = Field(..., min_length=1, max_length=32)
    store_code: str = Field(..., min_length=1, max_length=128)
    identity_kind: IdentityKind
    identity_value: str = Field(..., min_length=1, max_length=256)
    fsku_id: int = Field(..., ge=1)
    reason: Optional[str] = Field(None, max_length=500)


class PlatformCodeMappingDeleteIn(BaseModel):
    platform: str = Field(..., min_length=1, max_length=32)
    store_code: str = Field(..., min_length=1, max_length=128)
    identity_kind: IdentityKind
    identity_value: str = Field(..., min_length=1, max_length=256)


class StoreLiteOut(BaseModel):
    id: int
    store_name: str


class FskuLiteOut(BaseModel):
    id: int
    code: str
    name: str
    status: str


class PlatformCodeMappingRowOut(BaseModel):
    id: int
    platform: str
    store_code: str
    store: StoreLiteOut

    identity_kind: IdentityKind
    identity_value: str

    fsku_id: int
    fsku: FskuLiteOut

    reason: Optional[str]
    created_at: datetime
    updated_at: datetime


class PlatformCodeMappingOut(BaseModel):
    ok: bool = True
    data: PlatformCodeMappingRowOut


class PlatformCodeMappingListDataOut(BaseModel):
    items: list[PlatformCodeMappingRowOut]
    total: int
    limit: int
    offset: int


class PlatformCodeMappingListOut(BaseModel):
    ok: bool = True
    data: PlatformCodeMappingListDataOut
