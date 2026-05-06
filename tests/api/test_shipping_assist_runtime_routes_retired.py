from __future__ import annotations

from app.main import app


def _mounted_paths() -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_retired_shipping_assist_runtime_routes_are_not_mounted() -> None:
    paths = _mounted_paths()

    retired_prefixes = (
        "/shipping-assist/pricing",
        "/shipping-assist/billing",
        "/shipping-assist/reports",
    )

    for path in paths:
        for prefix in retired_prefixes:
            assert not path.startswith(prefix), f"{path} should not be mounted in WMS"


def test_shipping_assist_records_routes_remain_mounted() -> None:
    paths = _mounted_paths()

    assert "/shipping-assist/records" in paths
    assert "/shipping-assist/records/export" in paths
    assert "/shipping-assist/records/options" in paths
    assert "/shipping-assist/records/cost-analysis" in paths
    assert "/shipping-assist/records/sync-from-logistics" in paths
