# tests/ci/test_wms_oms_fulfillment_projection_ops_boundary.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_OWNER_SQL_RE = re.compile(
    r"\bFROM\s+(orders|order_lines|oms_fskus|oms_fsku_components|platform_code_fsku_mappings)\b"
    r"|\bJOIN\s+(orders|order_lines|oms_fskus|oms_fsku_components|platform_code_fsku_mappings)\b"
    r"|\bINSERT\s+INTO\s+(orders|order_lines|oms_fskus|oms_fsku_components|platform_code_fsku_mappings)\b"
    r"|\bUPDATE\s+(orders|order_lines|oms_fskus|oms_fsku_components|platform_code_fsku_mappings)\b"
    r"|\bDELETE\s+FROM\s+(orders|order_lines|oms_fskus|oms_fsku_components|platform_code_fsku_mappings)\b",
    re.IGNORECASE,
)


def test_oms_fulfillment_projection_module_uses_wms_directory_style() -> None:
    base = ROOT / "app/oms/fulfillment_projection"

    assert (base / "contracts/fulfillment_projection.py").is_file()
    assert (base / "repos/fulfillment_projection_repo.py").is_file()
    assert (base / "routers/fulfillment_projection.py").is_file()
    assert (base / "services/fulfillment_projection_service.py").is_file()

    assert not (base / "contracts.py").exists()
    assert not (base / "service.py").exists()
    assert not (base / "router.py").exists()

    assert not (base / "contract").exists()
    assert not (base / "repo").exists()
    assert not (base / "router").exists()
    assert not (base / "service").exists()


def test_oms_fulfillment_projection_repo_uses_projection_tables_only() -> None:
    text = (ROOT / "app/oms/fulfillment_projection/repos/fulfillment_projection_repo.py").read_text(
        encoding="utf-8"
    )

    assert "wms_oms_fulfillment_order_projection" in text
    assert "wms_oms_fulfillment_line_projection" in text
    assert "wms_oms_fulfillment_component_projection" in text
    assert "wms_oms_fulfillment_projection_sync_runs" in text

    assert FORBIDDEN_OWNER_SQL_RE.search(text) is None
    assert "wms_logistics_" not in text
    assert "outbound_event" not in text
    assert "wms_pms_" not in text


def test_oms_fulfillment_projection_router_uses_oms_permissions_and_business_prefix() -> None:
    text = (ROOT / "app/oms/fulfillment_projection/routers/fulfillment_projection.py").read_text(
        encoding="utf-8"
    )

    assert 'prefix="/fulfillment-projection"' in text
    assert "page.oms.read" in text
    assert "page.oms.write" in text
    assert "/projections/fulfillment-ready-orders/sync" in text

    assert "page.admin.read" not in text
    assert "page.admin.write" not in text
    assert "/admin" not in text
    assert "/collector" not in text
    assert "/connection" not in text


def test_oms_router_mounts_fulfillment_projection_router() -> None:
    text = (ROOT / "app/oms/router.py").read_text(encoding="utf-8")

    assert "fulfillment_projection_router" in text
    assert "router.include_router(fulfillment_projection_router)" in text
    assert "app.oms.fulfillment_projection.routers.fulfillment_projection" in text
