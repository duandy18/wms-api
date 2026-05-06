from __future__ import annotations

from app.main import app


def _mounted_paths() -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_warehouse_shipping_provider_routes_are_not_mounted() -> None:
    paths = _mounted_paths()

    retired_paths = {
        "/shipping-providers",
        "/warehouses/{warehouse_id}/shipping-providers",
        "/warehouses/{warehouse_id}/shipping-providers/bind",
        "/warehouses/{warehouse_id}/shipping-providers/{shipping_provider_id}",
    }

    for path in retired_paths:
        assert path not in paths, f"{path} should not be mounted in WMS"
