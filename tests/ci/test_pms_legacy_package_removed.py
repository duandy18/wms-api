# tests/ci/test_pms_legacy_package_removed.py
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_legacy_app_pms_package_is_removed() -> None:
    assert not (ROOT / "app" / "pms").exists()


def test_runtime_code_does_not_import_app_pms() -> None:
    violations: list[str] = []

    for base_name in ("app", "tests", "scripts"):
        base = ROOT / base_name
        if not base.exists():
            continue

        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith(("from app.pms", "import app.pms")):
                    violations.append(f"{rel}:{line_no}: {stripped}")

    assert violations == []
