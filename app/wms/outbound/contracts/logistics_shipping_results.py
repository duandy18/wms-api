# app/wms/outbound/contracts/logistics_shipping_results.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class LogisticsShippingResultPackageIn(_Base):
    package_no: int = Field(..., ge=1)

    tracking_no: str = Field(..., min_length=1, max_length=128)

    shipping_provider_code: str = Field(..., min_length=1, max_length=64)
    shipping_provider_name: str | None = Field(default=None, max_length=128)

    gross_weight_kg: Decimal | None = Field(default=None, ge=0)
    freight_estimated: Decimal | None = Field(default=None, ge=0)
    surcharge_estimated: Decimal | None = Field(default=None, ge=0)
    cost_estimated: Decimal | None = Field(default=None, ge=0)

    length_cm: Decimal | None = Field(default=None, ge=0)
    width_cm: Decimal | None = Field(default=None, ge=0)
    height_cm: Decimal | None = Field(default=None, ge=0)

    sender: str | None = Field(default=None, max_length=128)
    dest_province: str | None = Field(default=None, max_length=64)
    dest_city: str | None = Field(default=None, max_length=64)


class LogisticsShippingResultIn(_Base):
    source_ref: str = Field(..., min_length=1, max_length=192)

    logistics_request_id: int | None = Field(default=None, ge=1)
    logistics_request_no: str | None = Field(default=None, min_length=1, max_length=64)

    completed_at: datetime | None = None
    packages: list[LogisticsShippingResultPackageIn] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_unique_packages(self) -> "LogisticsShippingResultIn":
        package_numbers = [pkg.package_no for pkg in self.packages]
        if len(package_numbers) != len(set(package_numbers)):
            raise ValueError("package_no must be unique in one shipping result")
        return self


class LogisticsShippingResultOut(_Base):
    ok: bool = True
    source_ref: str
    logistics_status: str
    logistics_completed_at: datetime
    shipping_record_ids: list[int] = Field(default_factory=list)
    packages_count: int
