# app/pms/fsku/contracts/fsku.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


FskuShape = Literal["single", "bundle"]
FskuExprType = Literal["DIRECT", "SEGMENT_GROUP"]
FskuStatus = Literal["draft", "published", "retired"]


def _trim(v: object) -> object:
    return v.strip() if isinstance(v, str) else v


class FskuCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, min_length=1, max_length=128)
    shape: FskuShape = "bundle"
    fsku_expr: str = Field(..., min_length=1, max_length=2000)

    @field_validator("name", "code", "fsku_expr", mode="before")
    @classmethod
    def _trim_text(cls, v: object) -> object:
        return _trim(v)


class FskuNameUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def _trim_name(cls, v: object) -> object:
        return _trim(v)


class FskuExpressionReplaceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fsku_expr: str = Field(..., min_length=1, max_length=2000)

    @field_validator("fsku_expr", mode="before")
    @classmethod
    def _trim_expr(cls, v: object) -> object:
        return _trim(v)


class FskuComponentOut(BaseModel):
    component_sku_code: str
    qty_per_fsku: Decimal
    alloc_unit_price: Decimal

    resolved_item_id: int
    resolved_item_sku_code_id: int
    resolved_item_uom_id: int

    sku_code_snapshot: str
    item_name_snapshot: str
    uom_snapshot: str

    sort_order: int


class FskuDetailOut(BaseModel):
    id: int
    code: str
    name: str
    shape: FskuShape
    status: FskuStatus

    fsku_expr: str
    normalized_expr: str
    expr_type: FskuExprType
    component_count: int

    published_at: datetime | None
    retired_at: datetime | None
    created_at: datetime
    updated_at: datetime

    components: list[FskuComponentOut]


class FskuListItem(BaseModel):
    id: int
    code: str
    name: str
    shape: FskuShape
    status: FskuStatus

    fsku_expr: str
    normalized_expr: str
    expr_type: FskuExprType
    component_count: int

    updated_at: datetime
    published_at: datetime | None
    retired_at: datetime | None

    components_summary: str
    components_summary_name: str


class FskuListOut(BaseModel):
    items: list[FskuListItem]
    total: int
    limit: int
    offset: int
