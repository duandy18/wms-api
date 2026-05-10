# app/integrations/pms/contracts.py
"""
PMS integration contracts.

These contracts belong to the WMS-side consumer boundary.

Important:
- Non-PMS domains should import PMS read models from app.integrations.pms.
- This file must not depend on legacy PMS owner/export modules.
- pms-api is now the PMS owner runtime; WMS keeps these local contract models
  so the integration client remains independent from the legacy in-process
  PMS owner package.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", populate_by_name=True)


ShelfLifeUnit = Literal["DAY", "WEEK", "MONTH", "YEAR"]
ExpiryPolicy = Literal["NONE", "REQUIRED"]
LotSourcePolicy = Literal["INTERNAL_ONLY", "SUPPLIER_ONLY"]
PmsExportSkuCodeType = Literal["PRIMARY", "ALIAS", "LEGACY", "MANUAL"]


def _norm_text(v: object) -> object:
    if isinstance(v, str):
        return v.strip()
    return v


class ItemReadQuery(_Base):
    """
    PMS item read query used by WMS-side consumers.

    Keep this intentionally small. The HTTP client maps q to pms-api keyword.
    """

    q: str | None = Field(default=None, max_length=128)
    limit: int | None = Field(default=None, ge=1, le=500)
    enabled: bool | None = None

    @field_validator("q", mode="before")
    @classmethod
    def _trim_q(cls, v: object) -> object:
        v = _norm_text(v)
        if v == "":
            return None
        return v


class ItemBasic(_Base):
    id: int = Field(gt=0)
    sku: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    spec: str | None = Field(default=None, max_length=128)

    enabled: bool = True
    supplier_id: int | None = None

    brand: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=64)


class ItemPolicy(_Base):
    item_id: int = Field(gt=0)

    expiry_policy: ExpiryPolicy
    shelf_life_value: int | None = Field(default=None, gt=0)
    shelf_life_unit: ShelfLifeUnit | None = None

    lot_source_policy: LotSourcePolicy
    derivation_allowed: bool
    uom_governance_enabled: bool


class PmsExportUom(_Base):
    id: int = Field(gt=0)
    item_id: int = Field(gt=0)

    uom: str = Field(min_length=1, max_length=16)
    display_name: str | None = Field(default=None, max_length=32)
    uom_name: str = Field(min_length=1, max_length=32)

    ratio_to_base: int = Field(ge=1)
    net_weight_kg: float | None = Field(default=None, ge=0)

    is_base: bool
    is_purchase_default: bool
    is_inbound_default: bool
    is_outbound_default: bool


class PmsExportBarcode(_Base):
    id: int = Field(gt=0)
    item_id: int = Field(gt=0)
    item_uom_id: int = Field(gt=0)

    barcode: str = Field(min_length=1, max_length=128)
    symbology: str = Field(min_length=1, max_length=32)

    active: bool
    is_primary: bool

    uom: str = Field(min_length=1, max_length=16)
    display_name: str | None = Field(default=None, max_length=32)
    uom_name: str = Field(min_length=1, max_length=32)
    ratio_to_base: int = Field(ge=1)


class BarcodeProbeStatus(str, Enum):
    BOUND = "BOUND"
    UNBOUND = "UNBOUND"
    ERROR = "ERROR"


class BarcodeProbeIn(_Base):
    barcode: str = Field(min_length=1, max_length=128)

    @field_validator("barcode", mode="before")
    @classmethod
    def _trim_barcode(cls, v: object) -> object:
        return _norm_text(v)


class BarcodeProbeError(_Base):
    stage: str
    error: str


class BarcodeProbeOut(_Base):
    ok: bool
    status: BarcodeProbeStatus
    barcode: str

    item_id: int | None = None
    item_uom_id: int | None = None
    ratio_to_base: int | None = None

    symbology: str | None = None
    active: bool | None = None

    item_basic: ItemBasic | None = None

    errors: list[BarcodeProbeError] = Field(default_factory=list)


class PmsExportSkuCode(_Base):
    id: int = Field(gt=0)
    item_id: int = Field(gt=0)

    code: str = Field(min_length=1, max_length=128)
    code_type: PmsExportSkuCodeType
    is_primary: bool
    is_active: bool

    effective_from: datetime | None = None
    effective_to: datetime | None = None
    remark: str | None = Field(default=None, max_length=255)

    item_sku: str = Field(min_length=1, max_length=128)
    item_name: str = Field(min_length=1, max_length=128)
    item_enabled: bool


class PmsExportSkuCodeResolution(_Base):
    sku_code_id: int = Field(gt=0)
    item_id: int = Field(gt=0)

    sku_code: str = Field(min_length=1, max_length=128)
    code_type: PmsExportSkuCodeType
    is_primary: bool

    item_sku: str = Field(min_length=1, max_length=128)
    item_name: str = Field(min_length=1, max_length=128)

    item_uom_id: int = Field(gt=0)
    uom: str = Field(min_length=1, max_length=16)
    display_name: str | None = Field(default=None, max_length=32)
    uom_name: str = Field(min_length=1, max_length=32)
    ratio_to_base: int = Field(ge=1)


__all__ = [
    "BarcodeProbeError",
    "BarcodeProbeIn",
    "BarcodeProbeOut",
    "BarcodeProbeStatus",
    "ExpiryPolicy",
    "ItemBasic",
    "ItemPolicy",
    "ItemReadQuery",
    "LotSourcePolicy",
    "PmsExportBarcode",
    "PmsExportSkuCode",
    "PmsExportSkuCodeResolution",
    "PmsExportSkuCodeType",
    "PmsExportUom",
    "ShelfLifeUnit",
]
