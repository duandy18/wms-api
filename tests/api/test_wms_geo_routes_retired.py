from __future__ import annotations

from app.main import app


def _mounted_paths() -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_wms_local_geo_routes_are_retired() -> None:
    paths = _mounted_paths()

    assert "/geo/provinces" not in paths
    assert "/geo/provinces/{province_code}/cities" not in paths
