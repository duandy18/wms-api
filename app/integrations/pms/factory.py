# app/integrations/pms/factory.py
"""
PMS read client factory.

PMS owner runtime has moved to the independent pms-api process.

wms-api is now a PMS consumer only:
- async reads use HttpPmsReadClient
- sync reads use SyncHttpPmsReadClient
- PMS_CLIENT_MODE must resolve to http
- PMS_API_BASE_URL is required unless an explicit base URL is passed
- no in-process fallback
"""

from __future__ import annotations

import os
from typing import Literal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.client import PmsReadClient
from app.integrations.pms.http_client import HttpPmsReadClient
from app.integrations.pms.sync_http_client import SyncHttpPmsReadClient

PmsClientMode = Literal["http"]


def get_pms_client_mode(value: str | None = None) -> PmsClientMode:
    raw = (value or os.getenv("PMS_CLIENT_MODE") or "http").strip().lower()

    if raw == "http":
        return "http"

    raise RuntimeError("Invalid PMS_CLIENT_MODE. Expected: http")


def create_pms_read_client(
    *,
    session: AsyncSession | None = None,
    mode: str | None = None,
    pms_api_base_url: str | None = None,
    timeout_seconds: float = 10.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> PmsReadClient:
    _ = session
    selected = get_pms_client_mode(mode)

    if selected == "http":
        return HttpPmsReadClient(
            base_url=pms_api_base_url,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )

    raise RuntimeError(f"Unsupported PMS client mode: {selected}")


def create_sync_pms_read_client(
    *,
    session=None,
    mode: str | None = None,
    pms_api_base_url: str | None = None,
    timeout_seconds: float = 10.0,
    transport: httpx.BaseTransport | None = None,
):
    _ = session
    selected = get_pms_client_mode(mode)

    if selected == "http":
        return SyncHttpPmsReadClient(
            base_url=pms_api_base_url,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )

    raise RuntimeError(f"Unsupported PMS client mode: {selected}")


__all__ = [
    "PmsClientMode",
    "create_pms_read_client",
    "create_sync_pms_read_client",
    "get_pms_client_mode",
]
