# tests/ci/test_pms_owner_routes_not_mounted.py
from __future__ import annotations

from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_ROUTE_PREFIXES = (
    "/pms",
    "/items",
    "/item-uoms",
    "/item-barcodes",
)


def test_wms_api_does_not_mount_pms_routes() -> None:
    mounted = sorted(
        {
            getattr(route, "path", "")
            for route in app.routes
            if any(
                getattr(route, "path", "") == prefix
                or getattr(route, "path", "").startswith(prefix + "/")
                for prefix in FORBIDDEN_ROUTE_PREFIXES
            )
        }
    )

    assert mounted == []


def test_router_mount_does_not_import_pms_routers() -> None:
    text = (ROOT / "app" / "router_mount.py").read_text(encoding="utf-8")

    assert "from app.pms." not in text
