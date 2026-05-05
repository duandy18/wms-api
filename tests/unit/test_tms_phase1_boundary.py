# tests/unit/test_tms_phase1_boundary.py
from __future__ import annotations

import pytest

from app.shipping_assist.phase1_boundary import (
    DomainOwner,
    TmsSubdomain,
    find_file_ownership,
    get_frozen_ownership,
)


def test_shipping_record_owned_by_shipping_assist_records() -> None:
    ownership = get_frozen_ownership("shipping_record")

    assert ownership.owner_domain == DomainOwner.TMS
    assert ownership.owner_subdomain == TmsSubdomain.SHIPPING_ASSIST_RECORDS


def test_order_owned_by_oms() -> None:
    ownership = get_frozen_ownership("order")

    assert ownership.owner_domain == DomainOwner.OMS
    assert ownership.owner_subdomain is None


def test_tms_alerts_service_is_frozen_as_shipping_assist_quote() -> None:
    rule = find_file_ownership("app/shipping_assist/alerts/service.py")

    assert rule is not None
    assert rule.owner_domain == DomainOwner.TMS
    assert rule.owner_subdomain == TmsSubdomain.SHIPPING_ASSIST_QUOTE


def test_tms_records_router_is_frozen_as_shipping_assist_records() -> None:
    rule = find_file_ownership("app/shipping_assist/records/router.py")

    assert rule is not None
    assert rule.owner_domain == DomainOwner.TMS
    assert rule.owner_subdomain == TmsSubdomain.SHIPPING_ASSIST_RECORDS


def test_tms_reports_router_is_frozen_as_shipping_assist_reports() -> None:
    rule = find_file_ownership("app/shipping_assist/reports/router.py")

    assert rule is not None
    assert rule.owner_domain == DomainOwner.TMS
    assert rule.owner_subdomain == TmsSubdomain.SHIPPING_ASSIST_REPORTS


def test_shipping_reports_routes_are_frozen_as_shipping_assist_reports() -> None:
    rule = find_file_ownership("app/api/routers/shipping_reports_routes_by_carrier.py")

    assert rule is not None
    assert rule.owner_domain == DomainOwner.TMS
    assert rule.owner_subdomain == TmsSubdomain.SHIPPING_ASSIST_REPORTS


@pytest.mark.parametrize(
    "code",
    [
        "quote",
        "quote_snapshot",
        "shipment_execution",
        "waybill_request",
        "tracking_number",
        "shipping_record_write",
    ],
)
def test_logistics_migrated_objects_are_no_longer_owned_by_wms_shipping_assist(code: str) -> None:
    with pytest.raises(KeyError):
        get_frozen_ownership(code)


@pytest.mark.parametrize(
    "path",
    [
        "app/shipping_assist/quote/router.py",
        "app/shipping_assist/quote/calc_quote.py",
        "app/shipping_assist/quote_snapshot/builder.py",
        "app/shipping_assist/shipment/waybill_service.py",
        "app/shipping_assist/shipment/orders_v2_router.py",
        "app/shipping_assist/shipment/contracts_calc.py",
        "app/shipping_assist/shipment/contracts_prepare.py",
        "app/shipping_assist/shipment/router.py",
        "app/shipping_assist/shipment/routes_calc.py",
        "app/shipping_assist/shipment/routes_prepare.py",
        "app/shipping_assist/shipment/routes_ship_with_waybill.py",
        "app/shipping_assist/shipment/api_contracts.py",
        "app/shipping_assist/shipment/service.py",
    ],
)
def test_logistics_migrated_paths_are_no_longer_owned_by_wms_shipping_assist(path: str) -> None:
    assert find_file_ownership(path) is None


def test_deleted_legacy_shipping_quote_router_returns_none() -> None:
    rule = find_file_ownership("app/api/routers/shipping_quote.py")
    assert rule is None


def test_deleted_legacy_shipping_quote_recommend_route_returns_none() -> None:
    rule = find_file_ownership("app/api/routers/shipping_quote_routes_recommend.py")
    assert rule is None


def test_deleted_legacy_shipping_records_router_returns_none() -> None:
    rule = find_file_ownership("app/api/routers/shipping_records.py")
    assert rule is None


def test_deleted_legacy_shipping_reports_router_returns_none() -> None:
    rule = find_file_ownership("app/api/routers/shipping_reports.py")
    assert rule is None


def test_unknown_path_returns_none() -> None:
    rule = find_file_ownership("app/services/not_related_domain.py")
    assert rule is None
