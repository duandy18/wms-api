# tests/ci/test_pms_integration_client_boundary_contract.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PMS_EXPORT_IMPORT_RE = re.compile(
    r"^\s*from\s+app\.pms\.export\b"
    r"|^\s*import\s+app\.pms\.export\b"
)

MIGRATED_NON_PMS_CONSUMERS = {
    "app/wms/scan/services/scan_orchestrator_item_resolver.py",
    "app/wms/inbound/repos/barcode_resolve_repo.py",
    "app/wms/inventory_adjustment/return_inbound/services/inbound_task_probe_service.py",
    "app/wms/inventory_adjustment/return_inbound/repos/inbound_operation_write_repo.py",
    "app/procurement/repos/purchase_order_create_repo.py",
    "app/procurement/repos/receive_po_line_repo.py",
    "app/procurement/services/purchase_order_create.py",
    "app/procurement/services/purchase_order_update.py",
    "app/procurement/helpers/purchase_reports.py",
    "app/procurement/routers/purchase_reports_routes_items.py",
    "app/wms/stock/repos/inventory_options_repo.py",
    "app/wms/stock/repos/inventory_read_repo.py",
    "app/wms/stock/repos/inventory_explain_repo.py",
    "app/wms/stock/services/lot_service.py",
    "app/wms/stock/services/lot_resolver.py",
    "app/wms/stock/services/lots.py",
    "app/wms/stock/services/stock_adjust/db_items.py",
    "app/wms/shared/services/expiry_resolver.py",
    "app/wms/shared/services/lot_code_contract.py",
    "app/wms/inbound/repos/item_lookup_repo.py",
    "app/wms/inbound/repos/lot_resolve_repo.py",
    "app/wms/inbound/services/inbound_commit_service.py",
    "app/wms/inventory_adjustment/count/repos/count_doc_repo.py",
    "app/wms/inventory_adjustment/summary/repos/summary_repo.py",
    "app/wms/inventory_adjustment/return_inbound/contracts/inbound_task_read.py",
    "app/wms/inventory_adjustment/return_inbound/repos/inbound_receipt_read_repo.py",
    "app/wms/inventory_adjustment/return_inbound/repos/inbound_receipt_write_repo.py",
    "app/wms/inventory_adjustment/return_inbound/routers/order_refs.py",
    "app/wms/ledger/helpers/stock_ledger.py",
    "app/oms/services/platform_order_resolve_loaders.py",
    "app/oms/fsku/services/fsku_service_write.py",
    "app/oms/orders/repos/order_outbound_view_repo.py",
}


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _import_violations(path: Path) -> list[str]:
    violations: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if PMS_EXPORT_IMPORT_RE.search(stripped):
            violations.append(f"{_rel(path)}:{line_no}: {stripped}")
    return violations


def test_pms_integration_client_boundary_files_exist() -> None:
    expected = {
        "app/integrations/__init__.py",
        "app/integrations/pms/__init__.py",
        "app/integrations/pms/contracts.py",
        "app/integrations/pms/client.py",
        "app/integrations/pms/inprocess_client.py",
        "app/integrations/pms/sync_client.py",
    }

    for rel in expected:
        assert (ROOT / rel).is_file(), rel


def test_migrated_non_pms_consumers_no_longer_import_pms_export_directly() -> None:
    for rel in sorted(MIGRATED_NON_PMS_CONSUMERS):
        path = ROOT / rel
        assert path.is_file(), rel
        assert _import_violations(path) == []


def test_migrated_non_pms_consumers_use_integration_boundary() -> None:
    for rel in sorted(MIGRATED_NON_PMS_CONSUMERS):
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        assert "app.integrations.pms" in text


def test_only_pms_integration_bridge_imports_pms_export_inside_integrations() -> None:
    allowed = {
        "app/integrations/pms/contracts.py",
        "app/integrations/pms/inprocess_client.py",
        "app/integrations/pms/sync_client.py",
    }

    violations: list[str] = []
    for path in sorted((ROOT / "app/integrations").rglob("*.py")):
        rel = _rel(path)
        if rel in allowed:
            continue
        violations.extend(_import_violations(path))

    assert violations == []
