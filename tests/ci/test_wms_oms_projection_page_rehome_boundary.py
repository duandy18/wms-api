# tests/ci/test_wms_oms_projection_page_rehome_boundary.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_oms_fulfillment_projection_pages_are_registered_under_order_management() -> None:
    migration_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "alembic/versions").glob("*rehome_projection_pages.py")
    )

    assert "oms.fulfillment_projection" in migration_text
    assert "oms.fulfillment_projection.orders" in migration_text
    assert "oms.fulfillment_projection.lines" in migration_text
    assert "oms.fulfillment_projection.components" in migration_text

    assert "/oms/fulfillment-projection" in migration_text
    assert "/oms/fulfillment-projection/orders" in migration_text
    assert "/oms/fulfillment-projection/lines" in migration_text
    assert "/oms/fulfillment-projection/components" in migration_text

    assert "domain_code\", \"oms\"" not in migration_text
    assert "page.oms.read" not in migration_text
    assert "page.oms.write" not in migration_text
