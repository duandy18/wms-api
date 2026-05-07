
from __future__ import annotations

from app.main import app


def test_handoffs_machine_api_routes_moved_from_wms_outbound_to_shipping_assist() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    retired_paths = {
        "/wms/outbound/logistics-ready",
        "/wms/outbound/logistics-import-results",
        "/wms/outbound/logistics-shipping-results",
    }
    expected_paths = {
        "/shipping-assist/handoffs",
        "/shipping-assist/handoffs/ready",
        "/shipping-assist/handoffs/import-results",
        "/shipping-assist/handoffs/shipping-results",
    }

    assert retired_paths.isdisjoint(paths)
    assert expected_paths.issubset(paths)
