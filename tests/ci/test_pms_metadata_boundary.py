# tests/ci/test_pms_metadata_boundary.py
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from app.db.external_pms_models import PMS_EXTERNAL_ANCHOR_TABLES, PMS_OWNED_TABLES

ROOT = Path(__file__).resolve().parents[2]


def test_db_base_does_not_load_pms_owner_orm_modules() -> None:
    text = (ROOT / "app" / "db" / "base.py").read_text(encoding="utf-8")

    assert "app.pms.items.models" not in text
    assert "app.pms.sku_coding.models" not in text
    assert "app.db.external_pms_models" in text


def test_fresh_init_models_registers_only_external_pms_anchors() -> None:
    code = """
import json
from app.db.base import Base, init_models
from app.db.external_pms_models import PMS_OWNED_TABLES

init_models(force=True)
print("PMS_TABLES=" + json.dumps(sorted(set(Base.metadata.tables) & set(PMS_OWNED_TABLES))))
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = "."

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    marker = "PMS_TABLES="
    lines = [line for line in result.stdout.splitlines() if line.startswith(marker)]
    assert lines, result.stdout + result.stderr

    assert set(json.loads(lines[-1][len(marker) :])) == set(PMS_EXTERNAL_ANCHOR_TABLES)


def test_external_pms_anchor_tables_are_minimal() -> None:
    from app.db.base import Base, init_models

    init_models(force=True)

    items = Base.metadata.tables["items"]
    item_uoms = Base.metadata.tables["item_uoms"]
    item_sku_codes = Base.metadata.tables["item_sku_codes"]

    assert items.info["external_owner"] == "pms-api"
    assert item_uoms.info["external_owner"] == "pms-api"
    assert item_sku_codes.info["external_owner"] == "pms-api"

    assert set(items.c.keys()) == {"id"}
    assert set(item_uoms.c.keys()) == {"id", "item_id"}
    assert set(item_sku_codes.c.keys()) == {"id", "item_id"}


def test_non_anchor_pms_owner_tables_are_not_registered() -> None:
    from app.db.base import Base, init_models

    init_models(force=True)

    forbidden = set(PMS_OWNED_TABLES) - set(PMS_EXTERNAL_ANCHOR_TABLES)
    assert sorted(set(Base.metadata.tables) & forbidden) == []


def test_alembic_env_excludes_pms_owned_tables() -> None:
    text = (ROOT / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "PMS_OWNED_TABLES" in text
    assert "PMS-owned tables are managed by pms-api" in text
    assert "_object_table_name(obj, name, type_) in PMS_OWNED_TABLES" in text



def test_alembic_env_keeps_external_anchors_for_fk_resolution() -> None:
    text = (ROOT / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "PMS_EXTERNAL_ANCHOR_TABLES" in text
    assert "t.name in PMS_OWNED_TABLES and t.name not in PMS_EXTERNAL_ANCHOR_TABLES" in text
