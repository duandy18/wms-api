from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic/versions/20260515123000_retire_wms_procurement_management_navigation.py"


def test_wms_procurement_management_navigation_is_retired_by_migration() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "DELETE FROM page_route_prefixes" in text
    assert "DELETE FROM page_registry" in text

    assert "procurement.purchase_orders" in text
    assert "procurement.purchase_orders_new" in text
    assert "procurement.purchase_order_detail" in text
    assert "procurement.purchase_reports" in text
    assert "WHERE code = 'procurement'" in text

    assert "'/purchase-orders'" in text
    assert "'/purchase-orders/new'" in text
    assert "'/purchase-orders/' || chr(58) || 'poId'" in text
    assert "'/purchase-reports'" in text


def test_wms_procurement_execution_navigation_is_not_retired_by_migration() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "/inbound-receipts/purchase" in text
    assert "/receiving/purchase" in text
    assert "/finance/purchase-costs" in text

    # These routes must only appear in comments, never inside DELETE filters.
    destructive_sections = [
        part
        for part in text.split("op.execute(")
        if "DELETE FROM page_route_prefixes" in part or "DELETE FROM page_registry" in part
    ]
    destructive_sql = "\n".join(destructive_sections)

    assert "/inbound-receipts/purchase" not in destructive_sql
    assert "/receiving/purchase" not in destructive_sql
    assert "/finance/purchase-costs" not in destructive_sql


def test_wms_procurement_page_permissions_are_removed_only_after_page_unlink() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "'page.procurement.read'" in text
    assert "'page.procurement.write'" in text
    assert "NOT EXISTS" in text
    assert "pr.read_permission_id = permissions.id" in text
    assert "pr.write_permission_id = permissions.id" in text
