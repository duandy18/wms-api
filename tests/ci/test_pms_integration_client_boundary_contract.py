# tests/ci/test_pms_integration_client_boundary_contract.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PMS_EXPORT_IMPORT_RE = re.compile(
    r"^\s*from\s+app\.pms\.export\b"
    r"|^\s*import\s+app\.pms\.export\b"
)

NON_PMS_BUSINESS_APP_DIRS = {
    "app/wms",
    "app/oms",
    "app/procurement",
    "app/finance",
}

PMS_INTEGRATION_BOUNDARY_FILES = {
    "app/integrations/__init__.py",
    "app/integrations/pms/__init__.py",
    "app/integrations/pms/contracts.py",
    "app/integrations/pms/factory.py",
    "app/integrations/pms/http_client.py",
    "app/integrations/pms/client.py",
    "app/integrations/pms/inprocess_client.py",
    "app/integrations/pms/sync_client.py",
    "app/integrations/pms/sync_http_client.py",
}

PMS_EXPORT_BRIDGE_ALLOWLIST = {
    "app/integrations/pms/contracts.py",
    "app/integrations/pms/factory.py",
    "app/integrations/pms/http_client.py",
    "app/integrations/pms/inprocess_client.py",
    "app/integrations/pms/sync_client.py",
    "app/integrations/pms/sync_http_client.py",
}


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _python_files_under(rel_dir: str) -> list[Path]:
    base = ROOT / rel_dir
    if not base.exists():
        return []
    return sorted(path for path in base.rglob("*.py") if path.is_file())


def _import_violations(path: Path) -> list[str]:
    violations: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if PMS_EXPORT_IMPORT_RE.search(stripped):
            violations.append(f"{_rel(path)}:{line_no}: {stripped}")
    return violations


def test_pms_integration_client_boundary_files_exist() -> None:
    for rel in sorted(PMS_INTEGRATION_BOUNDARY_FILES):
        assert (ROOT / rel).is_file(), rel


def test_non_pms_business_domains_do_not_import_pms_export_directly() -> None:
    """
    PMS 独立化准备合同：

    WMS / OMS / Procurement / Finance 不允许直接 import app.pms.export。
    这些业务域只能通过 app.integrations.pms 读取 PMS export 能力。

    允许 direct import app.pms.export 的位置：
    - PMS 自己的 export 实现；
    - app.integrations.pms 桥接实现；
    - PMS export 自身合同/服务测试。
    """
    violations: list[str] = []

    for rel_dir in sorted(NON_PMS_BUSINESS_APP_DIRS):
        for path in _python_files_under(rel_dir):
            violations.extend(_import_violations(path))

    assert violations == []


def test_only_pms_integration_bridge_imports_pms_export_inside_integrations() -> None:
    violations: list[str] = []

    for path in sorted((ROOT / "app/integrations").rglob("*.py")):
        rel = _rel(path)
        if rel in PMS_EXPORT_BRIDGE_ALLOWLIST:
            continue
        violations.extend(_import_violations(path))

    assert violations == []
