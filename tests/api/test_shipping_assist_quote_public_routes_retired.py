from __future__ import annotations

from app.main import app


def test_shipping_assist_quote_public_routes_are_retired_from_wms() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    assert "/shipping-assist/shipping/quote/calc" not in paths
    assert "/shipping-assist/shipping/quote/recommend" not in paths
    assert "/metrics/shipping-assist/shipping/quote/failures" not in paths
