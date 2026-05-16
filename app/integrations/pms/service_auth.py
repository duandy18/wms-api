# app/integrations/pms/service_auth.py
from __future__ import annotations

from collections.abc import Mapping

PMS_SERVICE_CLIENT_HEADER = "X-Service-Client"
PMS_SERVICE_CLIENT_CODE = "wms-service"


def pms_service_auth_headers(headers: Mapping[str, str] | None = None) -> dict[str, str]:
    """
    Build WMS -> PMS service authorization headers.

    Boundary:
    - WMS calls PMS as the fixed service client: wms-service.
    - This is system-to-system authorization metadata, not user authorization.
    - Caller-supplied headers are preserved, but X-Service-Client is owned by WMS.
    """

    merged = dict(headers or {})
    merged[PMS_SERVICE_CLIENT_HEADER] = PMS_SERVICE_CLIENT_CODE
    return merged


__all__ = [
    "PMS_SERVICE_CLIENT_CODE",
    "PMS_SERVICE_CLIENT_HEADER",
    "pms_service_auth_headers",
]
