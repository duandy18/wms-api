# tests/ci/test_no_pms_owner_route_requests.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

OWNER_ROUTE_RE = re.compile(
    r"""client\.(get|post|patch|put|delete)\(\s*f?["']"""
    r"""(/items\b|/items/|/item-uoms\b|/item-uoms/|/item-barcodes\b|/item-barcodes/|/pms/brands\b|/pms/brands/|/pms/categories\b|/pms/categories/|/pms/item-attribute|/pms/sku-coding)"""
)

TEMP_ALLOWED: set[str] = set()


def test_tests_do_not_call_retired_pms_owner_routes() -> None:
    violations: list[str] = []

    for path in sorted((ROOT / "tests").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in TEMP_ALLOWED:
            continue

        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if OWNER_ROUTE_RE.search(line):
                violations.append(f"{rel}:{line_no}: {line.strip()}")

    assert violations == []
