from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


ProcurementReceivingResultEventKind = Literal["COMMIT"]


class _Base(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        str_strip_whitespace=True,
    )


class ProcurementReceivingResultLineOut(_Base):
    wms_event_id: Annotated[int, Field(ge=1)]
    wms_event_no: Annotated[str, Field(min_length=1, max_length=64)]
    trace_id: Annotated[str, Field(min_length=1, max_length=128)]
    event_kind: ProcurementReceivingResultEventKind
    event_status: Annotated[str, Field(min_length=1, max_length=16)]
    occurred_at: datetime

    receipt_no: Annotated[str, Field(min_length=1, max_length=128)]
    procurement_po_id: Annotated[int, Field(ge=1)]
    procurement_po_no: Annotated[str, Field(min_length=1, max_length=128)]
    wms_event_line_no: Annotated[int, Field(ge=1)]
    procurement_po_line_id: Annotated[int, Field(ge=1)]

    warehouse_id: Annotated[int, Field(ge=1)]
    item_id: Annotated[int, Field(ge=1)]
    qty_delta_base: int

    lot_code_input: str | None = Field(default=None, max_length=128)
    production_date: date | None = None
    expiry_date: date | None = None
    lot_id: int | None = Field(default=None, ge=1)


class ProcurementReceivingResultsOut(_Base):
    items: list[ProcurementReceivingResultLineOut] = Field(default_factory=list)
    after_event_id: int = Field(ge=0)
    next_after_event_id: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    has_more: bool


class ProcurementReceivingResultDetailOut(_Base):
    event_id: Annotated[int, Field(ge=1)]
    items: list[ProcurementReceivingResultLineOut] = Field(default_factory=list)


__all__ = [
    "ProcurementReceivingResultDetailOut",
    "ProcurementReceivingResultLineOut",
    "ProcurementReceivingResultsOut",
]
