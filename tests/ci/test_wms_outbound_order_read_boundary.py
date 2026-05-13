# tests/ci/test_wms_outbound_order_read_boundary.py
from __future__ import annotations

from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def _runtime_paths() -> list[str]:
    return sorted(str(getattr(route, "path", "")) for route in app.routes)


def test_wms_outbound_order_read_routes_are_mounted_under_wms_outbound() -> None:
    paths = _runtime_paths()

    assert "/wms/outbound/orders/options" in paths
    assert "/wms/outbound/orders/{order_id}/view" in paths

    assert "/oms/orders/outbound-options" not in paths
    assert all(not path.startswith("/oms/orders") for path in paths)


def test_legacy_oms_order_outbound_read_source_files_are_removed() -> None:
    retired_paths = (
        "app/oms/orders/contracts/order_outbound_options.py",
        "app/oms/orders/contracts/order_outbound_view.py",
        "app/oms/orders/repos/order_outbound_options_repo.py",
        "app/oms/orders/repos/order_outbound_view_repo.py",
        "app/oms/orders/routers/order_outbound_options.py",
        "app/oms/orders/routers/order_outbound_view.py",
    )

    existing = [path for path in retired_paths if (ROOT / path).exists()]
    assert existing == []


def test_outbound_submit_service_uses_wms_order_read_repo() -> None:
    text = (ROOT / "app/wms/outbound/services/outbound_event_submit_service.py").read_text(
        encoding="utf-8"
    )

    assert "app.wms.outbound.repos.order_read_view_repo" in text
    assert "app.oms.orders.repos.order_outbound_view_repo" not in text


def test_procurement_pms_projection_helper_does_not_patch_retired_oms_runtime_modules() -> None:
    text = (ROOT / "tests/helpers/procurement_pms_projection.py").read_text(
        encoding="utf-8"
    )

    assert "app.oms.services.platform_order_resolve_loaders" not in text
    assert "app.oms.orders.repos.order_outbound_view_repo" not in text


def test_procurement_pms_projection_helper_does_not_patch_retired_oms_resolve_service() -> None:
    text = (ROOT / "tests/helpers/procurement_pms_projection.py").read_text(
        encoding="utf-8"
    )

    assert "app.oms.services.platform_order_resolve_service" not in text


def test_procurement_pms_projection_helper_patch_targets_exist() -> None:
    import re

    root = ROOT
    text = (ROOT / "tests/helpers/procurement_pms_projection.py").read_text(
        encoding="utf-8"
    )

    missing: list[str] = []
    for module in re.findall(r'"(app\.[^"]+)"', text):
        module_path = root / (module.replace(".", "/") + ".py")
        package_path = root / module.replace(".", "/") / "__init__.py"
        if not module_path.exists() and not package_path.exists():
            missing.append(module)

    assert missing == []
