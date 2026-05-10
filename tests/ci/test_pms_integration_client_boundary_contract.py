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
    }

    for rel in expected:
        assert (ROOT / rel).is_file(), rel


def test_migrated_non_pms_consumers_no_longer_import_pms_export_directly() -> None:
    for rel in sorted(MIGRATED_NON_PMS_CONSUMERS):
        path = ROOT / rel
        assert path.is_file(), rel
        assert _import_violations(path) == []


def test_migrated_non_pms_consumers_use_integration_client() -> None:
    for rel in sorted(MIGRATED_NON_PMS_CONSUMERS):
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        assert "InProcessPmsReadClient" in text


def test_only_pms_integration_bridge_imports_pms_export_inside_integrations() -> None:
    allowed = {
        "app/integrations/pms/contracts.py",
        "app/integrations/pms/inprocess_client.py",
    }

    violations: list[str] = []
    for path in sorted((ROOT / "app/integrations").rglob("*.py")):
        rel = _rel(path)
        if rel in allowed:
            continue
        violations.extend(_import_violations(path))

    assert violations == []
