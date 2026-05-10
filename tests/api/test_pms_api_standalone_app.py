# tests/api/test_pms_api_standalone_app.py
from __future__ import annotations

from fastapi.testclient import TestClient

from app.pms_api.main import app


def _paths() -> set[str]:
    return {
        str(getattr(route, "path", ""))
        for route in app.routes
        if isinstance(getattr(route, "path", ""), str)
    }


def test_pms_api_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "pms-api"


def test_pms_api_mounts_pms_and_supplier_routes() -> None:
    paths = _paths()

    assert "/pms/export/items" in paths
    assert "/pms/export/items/barcode-probe" in paths
    assert "/pms/export/uoms" in paths
    assert "/pms/export/sku-codes" in paths
    assert "/pms/export/barcodes" in paths

    assert "/items" in paths
    assert "/items/list-rows" in paths
    assert "/item-uoms" in paths
    assert "/item-barcodes" in paths
    assert "/pms/brands" in paths
    assert "/pms/categories" in paths
    assert "/pms/sku-coding/generate" in paths

    assert "/partners/export/suppliers" in paths


def test_pms_api_does_not_mount_non_pms_runtime_domains() -> None:
    paths = _paths()

    forbidden_prefixes = (
        "/admin",
        "/users",
        "/oms",
        "/finance",
        "/purchase-orders",
        "/purchase-reports",
        "/shipping-assist",
        "/stock",
        "/wms/inbound",
        "/wms/outbound",
        "/return-tasks",
        "/count",
        "/count-docs",
        "/print-jobs",
    )

    violations = [
        path
        for path in sorted(paths)
        for prefix in forbidden_prefixes
        if path == prefix or path.startswith(f"{prefix}/")
    ]

    assert violations == []
