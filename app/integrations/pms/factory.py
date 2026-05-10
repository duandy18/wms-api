# app/integrations/pms/factory.py
"""
PMS read client factory.

This is the explicit cutover point between:
- in-process PMS reads inside wms-api
- HTTP PMS reads through the independent pms-api process

No fallback:
- PMS_CLIENT_MODE=inprocess requires an AsyncSession
- PMS_CLIENT_MODE=http requires PMS_API_BASE_URL or explicit pms_api_base_url
"""

from __future__ import annotations

import os
from typing import Literal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.client import PmsReadClient
from app.integrations.pms.http_client import HttpPmsReadClient
from app.integrations.pms.inprocess_client import InProcessPmsReadClient

PmsClientMode = Literal["inprocess", "http"]


def get_pms_client_mode(value: str | None = None) -> PmsClientMode:
    raw = (value or os.getenv("PMS_CLIENT_MODE") or "inprocess").strip().lower()

    if raw in {"inprocess", "http"}:
        return raw  # type: ignore[return-value]

    raise RuntimeError(
        "Invalid PMS_CLIENT_MODE. Expected one of: inprocess, http"
    )


def create_pms_read_client(
    *,
    session: AsyncSession | None = None,
    mode: str | None = None,
    pms_api_base_url: str | None = None,
    timeout_seconds: float = 10.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> PmsReadClient:
    selected = get_pms_client_mode(mode)

    if selected == "inprocess":
        if session is None:
            raise RuntimeError(
                "PMS_CLIENT_MODE=inprocess requires an AsyncSession"
            )
        return InProcessPmsReadClient(session)

    if selected == "http":
        return HttpPmsReadClient(
            base_url=pms_api_base_url,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )

    raise RuntimeError(f"Unsupported PMS client mode: {selected}")


__all__ = [
    "PmsClientMode",
    "create_pms_read_client",
    "get_pms_client_mode",
]
