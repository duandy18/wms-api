# app/shipping_assist/records/sync/client.py
from __future__ import annotations

import os
from typing import Any

import httpx


class LogisticsShippingFactsClientError(RuntimeError):
    pass


def _logistics_base_url() -> str:
    return (os.getenv("LOGISTICS_API_BASE_URL") or "http://127.0.0.1:8002").rstrip("/")


def _logistics_api_token() -> str | None:
    token = (os.getenv("LOGISTICS_API_TOKEN") or "").strip()
    return token or None


def _logistics_timeout_seconds() -> float:
    raw = (os.getenv("LOGISTICS_API_TIMEOUT_SECONDS") or "10").strip()
    try:
        return max(float(raw), 1.0)
    except ValueError:
        return 10.0


async def fetch_logistics_shipping_record_facts(
    *,
    after_id: int,
    limit: int,
    platform: str | None = None,
    store_code: str | None = None,
) -> dict[str, Any]:
    params: dict[str, object] = {
        "after_id": int(after_id),
        "limit": int(limit),
    }
    if platform:
        params["platform"] = platform.strip().upper()
    if store_code:
        params["store_code"] = store_code.strip()

    headers: dict[str, str] = {}
    token = _logistics_api_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{_logistics_base_url()}/logistics/shipping/records/facts/export"

    try:
        async with httpx.AsyncClient(timeout=_logistics_timeout_seconds()) as client:
            resp = await client.get(url, params=params, headers=headers)
    except httpx.RequestError as exc:
        raise LogisticsShippingFactsClientError(
            f"logistics shipping facts request failed: {exc}"
        ) from exc

    if resp.status_code >= 400:
        raise LogisticsShippingFactsClientError(
            f"logistics shipping facts request failed: status={resp.status_code} body={resp.text}"
        )

    data = resp.json()
    if not isinstance(data, dict):
        raise LogisticsShippingFactsClientError("logistics shipping facts response is not an object")
    if not isinstance(data.get("rows"), list):
        raise LogisticsShippingFactsClientError("logistics shipping facts response missing rows array")
    return data
