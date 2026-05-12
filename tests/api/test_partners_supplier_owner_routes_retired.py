# tests/api/test_partners_supplier_owner_routes_retired.py
from __future__ import annotations

from app.main import app


def _method_paths() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or []
        for method in methods:
            if method in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
                pairs.add((method, path))
    return pairs


def test_partners_supplier_owner_routes_are_retired() -> None:
    pairs = _method_paths()

    assert ("GET", "/partners/suppliers") not in pairs
    assert ("POST", "/partners/suppliers") not in pairs
    assert ("PATCH", "/partners/suppliers/{supplier_id}") not in pairs
    assert ("POST", "/partners/suppliers/{supplier_id}/contacts") not in pairs
    assert ("PATCH", "/partners/supplier-contacts/{contact_id}") not in pairs
    assert ("DELETE", "/partners/supplier-contacts/{contact_id}") not in pairs


def test_partners_supplier_export_read_route_is_kept() -> None:
    pairs = _method_paths()

    assert ("GET", "/partners/export/suppliers") in pairs
