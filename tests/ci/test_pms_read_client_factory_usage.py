# tests/ci/test_pms_read_client_factory_usage.py
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BUSINESS_DIRS = (
    "app/wms",
    "app/oms",
    "app/procurement",
    "app/finance",
)

FORBIDDEN_PATTERNS = (
    re.compile(r"^\s*from\s+app\.integrations\.pms\.inprocess_client\s+import\b"),
    re.compile(r"^\s*from\s+app\.integrations\.pms\.sync_client\s+import\b"),
    re.compile(r"\bInProcessPmsReadClient\s*\("),
    re.compile(r"\bSyncInProcessPmsReadClient\s*\("),
    re.compile(r"PMS_CLIENT_MODE\s*=\s*[\"']inprocess[\"']"),
)


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_business_domains_use_pms_read_client_factory() -> None:
    violations: list[str] = []

    for rel_dir in BUSINESS_DIRS:
        base = ROOT / rel_dir
        if not base.exists():
            continue

        for path in sorted(base.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                for pattern in FORBIDDEN_PATTERNS:
                    if pattern.search(line):
                        violations.append(f"{_rel(path)}:{line_no}: {line.strip()}")

    assert violations == []
