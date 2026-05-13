# tests/ci/test_wms_oms_legacy_runtime_retired.py
from __future__ import annotations

from app.main import app


ALLOWED_OMS_RUNTIME_PREFIXES = (
    "/oms/fulfillment-projection",
)

FORBIDDEN_OMS_RUNTIME_PREFIXES = (
    "/oms/fskus",
    "/oms/platform-code-mappings",
    "/oms/platform-orders",
    "/oms/stores",
    "/oms/pdd",
    "/oms/taobao",
    "/oms/jd",
    "/oms/orders/outbound-options",
    "/oms/orders/",
)


def test_wms_runtime_exposes_only_oms_projection_ops() -> None:
    paths = sorted(
        str(getattr(route, "path", ""))
        for route in app.routes
        if str(getattr(route, "path", "")).startswith("/oms")
    )

    assert paths, "expected OMS projection routes to be mounted"

    forbidden = [
        path
        for path in paths
        if path.startswith(FORBIDDEN_OMS_RUNTIME_PREFIXES)
    ]
    assert forbidden == []

    assert all(path.startswith(ALLOWED_OMS_RUNTIME_PREFIXES) for path in paths)

    assert "/oms/fulfillment-projection/status" in paths
    assert "/oms/fulfillment-projection/sync-runs" in paths
    assert "/oms/fulfillment-projection/projections/{resource}" in paths
    assert "/oms/fulfillment-projection/projections/{resource}/check" in paths
    assert "/oms/fulfillment-projection/projections/fulfillment-ready-orders/sync" in paths
