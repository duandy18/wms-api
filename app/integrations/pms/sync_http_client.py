# app/integrations/pms/sync_http_client.py
"""
Synchronous HTTP PMS read client.

Current use case:
- synchronous service paths that call create_sync_pms_read_client.
- first supported method mirrors the sync boundary:
  resolve_active_code_for_outbound_default.

No fallback:
- PMS_API_BASE_URL must be configured explicitly.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, TypeVar

import httpx

from app.integrations.pms.contracts import PmsExportSkuCodeResolution
from app.integrations.pms.service_auth import pms_service_auth_headers

ModelT = TypeVar("ModelT")


def _base_url(value: str | None) -> str:
    raw = (value or os.getenv("PMS_API_BASE_URL") or "").strip()
    if not raw:
        raise RuntimeError("PMS_API_BASE_URL is required for SyncHttpPmsReadClient")
    return raw.rstrip("/")


def _parse_model(model_type: type[ModelT], data: Mapping[str, Any]) -> ModelT:
    validator = getattr(model_type, "model_validate", None)
    if callable(validator):
        return validator(data)
    return model_type(**data)  # type: ignore[misc]


class SyncHttpPmsReadClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.base_url = _base_url(base_url)
        self.timeout = httpx.Timeout(timeout_seconds)
        self.transport = transport
        self.headers = pms_service_auth_headers(headers)

    def resolve_active_code_for_outbound_default(
        self,
        *,
        code: str,
        enabled_only: bool = True,
    ) -> PmsExportSkuCodeResolution | None:
        with httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self.transport,
            headers=self.headers,
        ) as client:
            response = client.get(
                "/pms/read/v1/sku-codes/resolve-outbound-default",
                params={"code": str(code), "enabled_only": bool(enabled_only)},
            )

        if response.status_code in {404, 409, 422}:
            return None

        response.raise_for_status()
        data = response.json()
        if not isinstance(data, Mapping):
            raise ValueError("pms-api resolve response must be object")
        return _parse_model(PmsExportSkuCodeResolution, data)


__all__ = ["SyncHttpPmsReadClient"]
