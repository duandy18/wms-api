
# app/shipping_assist/handoffs/contracts_machine.py
#
# 分拆说明：
# - 本文件承载 Shipping Assist / Handoffs 的跨系统机器接口合同；
# - ready / import-results / shipping-results 是 WMS 与独立 Logistics 的交接资源接口；
# - 这些接口不再归属 WMS outbound 路由层，旧 /wms/outbound/logistics-* 不保留兼容。
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class LogisticsReadyShipmentItemOut(_Base):
    source_line_type: str
    source_line_id: int | None = None
    source_line_no: int | None = None
    item_id: int | None = None
    item_sku_snapshot: str | None = None
    item_name_snapshot: str | None = None
    item_spec_snapshot: str | None = None
    qty_outbound: int


class LogisticsReadyRowOut(_Base):
    source_system: str = "WMS"
    request_source: str = "API_IMPORT"

    source_doc_type: str
    source_doc_id: int
    source_doc_no: str
    source_ref: str

    export_status: str
    logistics_status: str

    platform: str | None = None
    store_code: str | None = None
    order_ref: str | None = None
    ext_order_no: str | None = None

    warehouse_id: int | None = None
    warehouse_name_snapshot: str | None = None

    receiver_name: str | None = None
    receiver_phone: str | None = None
    receiver_province: str | None = None
    receiver_city: str | None = None
    receiver_district: str | None = None
    receiver_address: str | None = None
    receiver_postcode: str | None = None

    outbound_event_id: int | None = None
    outbound_source_ref: str | None = None
    outbound_completed_at: datetime | None = None

    shipment_items: list[LogisticsReadyShipmentItemOut] = Field(default_factory=list)

    handoff_created_at: datetime
    handoff_updated_at: datetime


class LogisticsReadyListOut(_Base):
    ok: bool = True
    rows: list[LogisticsReadyRowOut] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class LogisticsImportResultIn(_Base):
    source_ref: str = Field(..., min_length=1, max_length=192)
    export_status: Literal["EXPORTED", "FAILED"]

    logistics_request_id: int | None = Field(default=None, ge=1)
    logistics_request_no: str | None = Field(default=None, min_length=1, max_length=64)

    error_message: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_result_contract(self) -> "LogisticsImportResultIn":
        if self.export_status == "EXPORTED":
            if self.logistics_request_id is None:
                raise ValueError("logistics_request_id is required when export_status=EXPORTED")
            if not self.logistics_request_no:
                raise ValueError("logistics_request_no is required when export_status=EXPORTED")
            if self.error_message:
                raise ValueError("error_message must be empty when export_status=EXPORTED")
            return self

        if self.export_status == "FAILED":
            if not self.error_message:
                raise ValueError("error_message is required when export_status=FAILED")
            if self.logistics_request_id is not None or self.logistics_request_no:
                raise ValueError("logistics request fields must be empty when export_status=FAILED")
            return self

        return self


class LogisticsImportResultOut(_Base):
    ok: bool = True
    source_ref: str
    export_status: str
    logistics_status: str

    logistics_request_id: int | None = None
    logistics_request_no: str | None = None

    exported_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_error: str | None = None
    updated_at: datetime


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
