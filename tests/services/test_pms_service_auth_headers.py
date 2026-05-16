# tests/services/test_pms_service_auth_headers.py
from __future__ import annotations

import httpx

from app.integrations.pms.contracts import PmsExportSkuCodeResolution
from app.integrations.pms.service_auth import (
    PMS_SERVICE_CLIENT_CODE,
    PMS_SERVICE_CLIENT_HEADER,
    pms_service_auth_headers,
)
from app.integrations.pms.sync_http_client import SyncHttpPmsReadClient


def test_pms_service_auth_headers_force_wms_service_client() -> None:
    headers = pms_service_auth_headers(
        {
            "Authorization": "Bearer token",
            PMS_SERVICE_CLIENT_HEADER: "wrong-service",
        }
    )

    assert headers["Authorization"] == "Bearer token"
    assert headers[PMS_SERVICE_CLIENT_HEADER] == PMS_SERVICE_CLIENT_CODE


def test_sync_http_pms_read_client_sends_wms_service_client_header() -> None:
    seen_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers.get(PMS_SERVICE_CLIENT_HEADER))
        return httpx.Response(
            200,
            json={
                "sku_code_id": 10,
                "item_id": 1,
                "sku_code": "SKU-0001",
                "code_type": "PRIMARY",
                "is_primary": True,
                "item_sku": "SKU-0001",
                "item_name": "笔记本",
                "item_uom_id": 7,
                "uom": "PCS",
                "display_name": "件",
                "uom_name": "件",
                "ratio_to_base": 1,
            },
        )

    client = SyncHttpPmsReadClient(
        base_url="http://pms-api.test",
        transport=httpx.MockTransport(handler),
    )
    result = client.resolve_active_code_for_outbound_default(code="SKU-0001")

    assert isinstance(result, PmsExportSkuCodeResolution)
    assert seen_headers == [PMS_SERVICE_CLIENT_CODE]
