# app/oms/fulfillment_projection/contracts/fulfillment_projection.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

OmsProjectionResource = Literal["orders", "lines", "components"]
OmsProjectionSyncResource = Literal["fulfillment-ready-orders"]
OmsProjectionPlatform = Literal["pdd", "taobao", "jd"]
SyncRunStatus = Literal["RUNNING", "SUCCESS", "FAILED"]


class OmsProjectionSyncRunOut(BaseModel):
    id: int
    resource: OmsProjectionSyncResource
    platform: OmsProjectionPlatform | None = None
    store_code: str | None = None
    status: SyncRunStatus
    fetched: int = 0
    upserted_orders: int = 0
    upserted_lines: int = 0
    upserted_components: int = 0
    pages: int = 0
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    triggered_by_user_id: int | None = None
    oms_api_base_url_snapshot: str | None = None
    sync_version: str | None = None


class OmsProjectionResourceStatusOut(BaseModel):
    resource: OmsProjectionResource
    table_name: str
    row_count: int
    max_synced_at: datetime | None = None
    last_sync_run: OmsProjectionSyncRunOut | None = None


class OmsProjectionStatusOut(BaseModel):
    oms_api_base_url_configured: bool
    resources: list[OmsProjectionResourceStatusOut] = Field(default_factory=list)


class OmsProjectionListOut(BaseModel):
    resource: OmsProjectionResource
    table_name: str
    limit: int
    offset: int
    total: int
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class OmsProjectionSyncOut(BaseModel):
    run: OmsProjectionSyncRunOut


class OmsProjectionCheckIssueOut(BaseModel):
    issue_type: str
    resource: OmsProjectionResource
    source_id: str
    message: str
    ready_order_id: str | None = None
    ready_line_id: str | None = None
    ready_component_id: str | None = None
    expected_value: str | None = None
    actual_value: str | None = None


class OmsProjectionCheckOut(BaseModel):
    resource: OmsProjectionResource
    ok: bool
    issue_count: int
    issues: list[OmsProjectionCheckIssueOut] = Field(default_factory=list)


class OmsProjectionSyncRunsOut(BaseModel):
    resource: OmsProjectionSyncResource | None = None
    platform: OmsProjectionPlatform | None = None
    limit: int
    runs: list[OmsProjectionSyncRunOut] = Field(default_factory=list)


__all__ = [
    "OmsProjectionCheckIssueOut",
    "OmsProjectionCheckOut",
    "OmsProjectionListOut",
    "OmsProjectionPlatform",
    "OmsProjectionResource",
    "OmsProjectionResourceStatusOut",
    "OmsProjectionStatusOut",
    "OmsProjectionSyncOut",
    "OmsProjectionSyncResource",
    "OmsProjectionSyncRunOut",
    "OmsProjectionSyncRunsOut",
    "SyncRunStatus",
]
