# tests/ci/test_wms_oms_projection_navigation_boundary.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_oms_projection_navigation_is_level_two_only() -> None:
    migration_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "alembic/versions").glob("*oms_projection_pages_level2_only.py")
    )

    assert "oms.order_projection" in migration_text
    assert "oms.line_projection" in migration_text
    assert "oms.component_projection" in migration_text

    assert "/oms/order-projection" in migration_text
    assert "/oms/line-projection" in migration_text
    assert "/oms/component-projection" in migration_text

    assert "DELETE FROM page_registry" in migration_text
    assert "code LIKE 'oms.%.%'" in migration_text
    assert "code LIKE 'oms.%'" in migration_text

    assert "oms.fulfillment_projection" in migration_text
    assert "oms.fsku_rules" in migration_text
    assert "oms.pdd" in migration_text
    assert "oms.taobao" in migration_text
    assert "oms.jd" in migration_text
