# tests/ci/test_no_legacy_pms_owner_tests.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALLOWED_TEST_IMPORTS: set[str] = set()


def test_tests_do_not_import_legacy_pms_owner_runtime() -> None:
    violations: list[str] = []

    for path in sorted((ROOT / "tests").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED_TEST_IMPORTS:
            continue

        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("from app.pms", "import app.pms")):
                violations.append(f"{rel}:{line_no}: {stripped}")

    assert violations == []
