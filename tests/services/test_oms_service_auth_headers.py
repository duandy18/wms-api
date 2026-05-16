# tests/services/test_oms_service_auth_headers.py
from __future__ import annotations

from app.integrations.oms.service_auth import (
    OMS_SERVICE_CLIENT_HEADER,
    WMS_SERVICE_CLIENT_CODE,
    oms_service_auth_headers,
)


def test_oms_service_auth_headers_force_wms_service_client() -> None:
    headers = oms_service_auth_headers(
        {
            OMS_SERVICE_CLIENT_HEADER: "wrong-service",
            "Authorization": "Bearer token",
        }
    )

    assert headers["Authorization"] == "Bearer token"
    assert headers[OMS_SERVICE_CLIENT_HEADER] == WMS_SERVICE_CLIENT_CODE
