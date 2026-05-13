# tests/ci/test_wms_oms_projection_order_import_boundary.py
from __future__ import annotations

from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def _runtime_paths() -> list[str]:
    return sorted(str(getattr(route, "path", "")) for route in app.routes)


def test_oms_projection_import_route_lives_under_wms_outbound() -> None:
    paths = _runtime_paths()

    assert "/wms/outbound/orders/import-from-oms-projection" in paths
    assert all(not path.startswith("/oms/orders") for path in paths)


def test_oms_projection_import_service_uses_projection_as_source_and_execution_as_target() -> None:
    text = (
        ROOT / "app/wms/outbound/services/oms_projection_order_import_service.py"
    ).read_text(encoding="utf-8")

    assert "FROM wms_oms_fulfillment_order_projection" in text
    assert "FROM wms_oms_fulfillment_component_projection" in text
    assert "INSERT INTO orders" in text
    assert "INSERT INTO order_lines" in text
    assert "INSERT INTO order_items" in text
    assert "INSERT INTO order_address" in text
    assert "UPDATE wms_oms_fulfillment_order_projection" not in text
    assert "UPDATE wms_oms_fulfillment_component_projection" not in text


def test_oms_projection_import_audit_tables_are_registered_in_orm_metadata() -> None:
    from app.db.base import Base, init_models

    init_models(force=True)

    assert "wms_oms_fulfillment_order_imports" in Base.metadata.tables
    assert "wms_oms_fulfillment_component_imports" in Base.metadata.tables
