# tests/ci/test_pms_orm_fk_relationship_retired.py
from __future__ import annotations

import re
from pathlib import Path

from app.db.base import Base, init_models
from app.db.external_pms_models import PMS_OWNED_TABLES

ROOT = Path(__file__).resolve().parents[2]

PMS_OWNER_TABLES = {
    "items",
    "item_uoms",
    "item_sku_codes",
    "item_barcodes",
}

FORBIDDEN_TEXT_RE = re.compile(
    r"ForeignKey\(\s*[\"'](?:items|item_uoms|item_sku_codes|item_barcodes)\."
    r"|ForeignKeyConstraint\([\s\S]*?\[(?:[^\]]*[\"'](?:items|item_uoms|item_sku_codes|item_barcodes)\.)"
    r"|relationship\(\s*[\"'](?:Item|ItemUOM|ItemSkuCode|ItemBarcode)[\"']",
    re.MULTILINE,
)


def _runtime_model_files() -> list[Path]:
    roots = [
        ROOT / "app" / "wms",
        ROOT / "app" / "oms",
        ROOT / "app" / "procurement",
        ROOT / "app" / "finance",
    ]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(sorted(root.rglob("models/*.py")))
    return files


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_runtime_models_do_not_declare_pms_owner_orm_foreign_keys_or_relationships() -> None:
    violations: list[str] = []

    for path in _runtime_model_files():
        text = path.read_text(encoding="utf-8")
        for match in FORBIDDEN_TEXT_RE.finditer(text):
            snippet = " ".join(match.group(0).split())
            violations.append(f"{_rel(path)}: {snippet}")

    assert violations == []


def test_runtime_metadata_has_no_foreign_keys_to_pms_owner_tables() -> None:
    init_models(force=True)

    violations: list[str] = []
    for table in Base.metadata.tables.values():
        if table.name in PMS_OWNED_TABLES:
            continue

        for fk in table.foreign_keys:
            if fk.column.table.name in PMS_OWNER_TABLES:
                violations.append(
                    f"{table.name}.{fk.parent.name} -> "
                    f"{fk.column.table.name}.{fk.column.name}"
                )

    assert violations == []
