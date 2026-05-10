# tests/ci/test_pms_integration_client_boundary_contract.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _py_files(*roots: str) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        base = ROOT / root
        if not base.exists():
            continue
        out.extend(sorted(base.rglob("*.py")))
    return out


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_non_pms_domains_do_not_import_legacy_pms_owner_runtime() -> None:
    """
    WMS / OMS / Procurement / Finance may only consume PMS through
    app.integrations.pms.

    Direct imports from app.pms.* are forbidden outside the legacy app/pms
    package itself.
    """
    violations: list[str] = []

    for path in _py_files("app/wms", "app/oms", "app/procurement", "app/finance"):
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("from app.pms", "import app.pms")):
                violations.append(f"{_rel(path)}:{line_no}: {stripped}")

    assert violations == []


def test_pms_integration_runtime_does_not_import_legacy_pms_owner_runtime() -> None:
    """
    PMS integration runtime must use HTTP clients only.
    """
    violations: list[str] = []

    for path in _py_files("app/integrations/pms"):
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("from app.pms", "import app.pms")):
                violations.append(f"{_rel(path)}:{line_no}: {stripped}")

    assert violations == []


def test_legacy_inprocess_clients_are_retired() -> None:
    assert not (ROOT / "app" / "integrations" / "pms" / "inprocess_client.py").exists()
    assert not (ROOT / "app" / "integrations" / "pms" / "sync_client.py").exists()
