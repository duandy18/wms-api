from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WmsReadWarehouseOut(BaseModel):
    """WMS warehouse read-v1 contract for cross-system consumers.

    Boundary:
    - WMS owns warehouse master data.
    - Cross-system consumers only receive stable read fields.
    - This contract intentionally does not expose management fields.
    """

    id: int = Field(ge=1)
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    active: bool

    model_config = ConfigDict(extra="forbid")


class WmsReadWarehouseListOut(BaseModel):
    items: list[WmsReadWarehouseOut] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "WmsReadWarehouseListOut",
    "WmsReadWarehouseOut",
]
