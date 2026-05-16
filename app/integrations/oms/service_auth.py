# app/integrations/oms/service_auth.py
from __future__ import annotations

from collections.abc import Mapping

OMS_SERVICE_CLIENT_HEADER = "X-Service-Client"
WMS_SERVICE_CLIENT_CODE = "wms-service"


def oms_service_auth_headers(headers: Mapping[str, str] | None = None) -> dict[str, str]:
    """
    Build service-to-service headers for WMS -> OMS calls.

    Boundary:
    - WMS calls OMS as the fixed service client: wms-service.
    - Caller-supplied headers are preserved.
    - X-Service-Client is owned by WMS and cannot be overridden by callers.
    """

    merged = dict(headers or {})
    merged[OMS_SERVICE_CLIENT_HEADER] = WMS_SERVICE_CLIENT_CODE
    return merged


__all__ = [
    "OMS_SERVICE_CLIENT_HEADER",
    "WMS_SERVICE_CLIENT_CODE",
    "oms_service_auth_headers",
]
