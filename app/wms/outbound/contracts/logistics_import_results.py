# app/wms/outbound/contracts/logistics_import_results.py
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


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
