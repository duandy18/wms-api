from __future__ import annotations

import os

import httpx

from app.integrations.procurement.http_client import HttpProcurementReadClient


DEFAULT_PROCUREMENT_API_BASE_URL = "http://127.0.0.1:8015"


def create_procurement_read_client(
    *,
    base_url: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> HttpProcurementReadClient:
    normalized_base_url = (
        base_url
        or os.getenv("PROCUREMENT_API_BASE_URL")
        or DEFAULT_PROCUREMENT_API_BASE_URL
    ).strip()

    return HttpProcurementReadClient(
        base_url=normalized_base_url,
        transport=transport,
    )
