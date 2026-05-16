# app/integrations/procurement/wms_procurement_service_auth.py
from __future__ import annotations

from collections.abc import Mapping

PROCUREMENT_SERVICE_CLIENT_HEADER = "X-Service-Client"
WMS_SERVICE_CLIENT_CODE = "wms-service"


def wms_to_procurement_service_auth_headers(
    headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """
    Build WMS -> Procurement service authorization headers.

    Boundary:
    - WMS calls Procurement as the fixed service client: wms-service.
    - This is system-to-system authorization metadata, not user authorization.
    - Caller-supplied headers are preserved, but X-Service-Client is owned by WMS.
    """

    merged = dict(headers or {})
    merged[PROCUREMENT_SERVICE_CLIENT_HEADER] = WMS_SERVICE_CLIENT_CODE
    return merged


__all__ = [
    "PROCUREMENT_SERVICE_CLIENT_HEADER",
    "WMS_SERVICE_CLIENT_CODE",
    "wms_to_procurement_service_auth_headers",
]
