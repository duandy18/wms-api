from __future__ import annotations

from app.main import app


def test_shipping_assist_shipment_runtime_public_routes_are_retired_from_wms() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}

    retired_paths = {
        "/orders/{platform}/{store_code}/{ext_order_no}/ship-with-waybill",
        "/shipping-assist/shipping/calc",
        "/shipping-assist/shipping/prepare/orders",
        "/shipping-assist/shipping/prepare/orders/{platform}/{store_code}/{ext_order_no}",
        "/shipping-assist/shipping/prepare/orders/import",
        "/shipping-assist/shipping/prepare/orders/{platform}/{store_code}/{ext_order_no}/address-confirm",
        "/shipping-assist/shipping/prepare/orders/{platform}/{store_code}/{ext_order_no}/packages",
        "/shipping-assist/shipping/prepare/orders/{platform}/{store_code}/{ext_order_no}/packages/{package_no}",
        "/shipping-assist/shipping/prepare/orders/{platform}/{store_code}/{ext_order_no}/packages/{package_no}/quote",
        "/shipping-assist/shipping/prepare/orders/{platform}/{store_code}/{ext_order_no}/packages/{package_no}/quote/confirm",
        "/shipping-assist/settings/waybill-configs",
        "/shipping-assist/settings/waybill-configs/{config_id}",
    }

    assert retired_paths.isdisjoint(paths)
