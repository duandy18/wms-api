# tests/ci/test_pms_integration_contracts_no_owner_import.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pms_integration_contracts_do_not_import_pms_owner_runtime() -> None:
    text = (ROOT / "app" / "integrations" / "pms" / "contracts.py").read_text(
        encoding="utf-8"
    )

    forbidden_lines = [
        line
        for line in text.splitlines()
        if line.lstrip().startswith(("from app.pms", "import app.pms"))
    ]

    assert forbidden_lines == []


def test_pms_integration_contracts_export_expected_names() -> None:
    namespace: dict[str, object] = {}
    exec(
        (ROOT / "app" / "integrations" / "pms" / "contracts.py").read_text(
            encoding="utf-8"
        ),
        namespace,
    )

    exported = set(namespace["__all__"])
    expected = {
        "BarcodeProbeError",
        "BarcodeProbeIn",
        "BarcodeProbeOut",
        "BarcodeProbeStatus",
        "ExpiryPolicy",
        "ItemBasic",
        "ItemPolicy",
        "ItemReadQuery",
        "LotSourcePolicy",
        "PmsExportBarcode",
        "PmsExportSkuCode",
        "PmsExportSkuCodeResolution",
        "PmsExportSkuCodeType",
        "PmsExportUom",
        "ShelfLifeUnit",
    }

    assert expected <= exported
