# app/integrations/pms/projection_contracts.py
"""
WMS PMS projection contracts.

These contracts describe WMS-owned read projection rows. They are not PMS owner
contracts and must not depend on the legacy PMS owner package.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", populate_by_name=True)


ExpiryPolicy = Literal["NONE", "REQUIRED"]
ShelfLifeUnit = Literal["DAY", "WEEK", "MONTH", "YEAR"]
LotSourcePolicy = Literal["INTERNAL_ONLY", "SUPPLIER_ONLY"]
SkuCodeType = Literal["PRIMARY", "ALIAS", "LEGACY", "MANUAL"]


class WmsPmsItemProjectionRow(_Base):
    item_id: int = Field(gt=0)

    sku: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    spec: str | None = Field(default=None, max_length=128)
    enabled: bool = True

    supplier_id: int | None = None
    brand: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=64)

    expiry_policy: ExpiryPolicy | None = None
    shelf_life_value: int | None = Field(default=None, gt=0)
    shelf_life_unit: ShelfLifeUnit | None = None
    lot_source_policy: LotSourcePolicy | None = None
    derivation_allowed: bool | None = None
    uom_governance_enabled: bool | None = None

    pms_updated_at: datetime | None = None
    source_hash: str | None = Field(default=None, max_length=128)
    sync_version: str | None = Field(default=None, max_length=64)
    synced_at: datetime


class WmsPmsUomProjectionRow(_Base):
    item_uom_id: int = Field(gt=0)
    item_id: int = Field(gt=0)

    uom: str = Field(min_length=1, max_length=16)
    display_name: str | None = Field(default=None, max_length=32)
    uom_name: str = Field(min_length=1, max_length=32)

    ratio_to_base: int = Field(ge=1)
    net_weight_kg: Decimal | None = Field(default=None, ge=0)

    is_base: bool
    is_purchase_default: bool
    is_inbound_default: bool
    is_outbound_default: bool

    pms_updated_at: datetime | None = None
    source_hash: str | None = Field(default=None, max_length=128)
    sync_version: str | None = Field(default=None, max_length=64)
    synced_at: datetime


class WmsPmsSkuCodeProjectionRow(_Base):
    sku_code_id: int = Field(gt=0)
    item_id: int = Field(gt=0)

    sku_code: str = Field(min_length=1, max_length=128)
    code_type: SkuCodeType
    is_primary: bool
    is_active: bool

    effective_from: datetime | None = None
    effective_to: datetime | None = None

    pms_updated_at: datetime | None = None
    source_hash: str | None = Field(default=None, max_length=128)
    sync_version: str | None = Field(default=None, max_length=64)
    synced_at: datetime


class WmsPmsBarcodeProjectionRow(_Base):
    barcode_id: int = Field(gt=0)
    item_id: int = Field(gt=0)
    item_uom_id: int = Field(gt=0)

    barcode: str = Field(min_length=1, max_length=128)
    symbology: str = Field(min_length=1, max_length=32)
    active: bool
    is_primary: bool

    pms_updated_at: datetime | None = None
    source_hash: str | None = Field(default=None, max_length=128)
    sync_version: str | None = Field(default=None, max_length=64)
    synced_at: datetime


__all__ = [
    "ExpiryPolicy",
    "LotSourcePolicy",
    "ShelfLifeUnit",
    "SkuCodeType",
    "WmsPmsBarcodeProjectionRow",
    "WmsPmsItemProjectionRow",
    "WmsPmsSkuCodeProjectionRow",
    "WmsPmsUomProjectionRow",
]
