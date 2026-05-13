# tests/ci/test_wms_oms_legacy_schema_retired.py
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app.db.base import Base, init_models
from app.db.session import SessionLocal

ROOT = Path(__file__).resolve().parents[2]

LEGACY_OMS_OWNER_TABLES = {
    "platform_order_manual_decisions",
    "platform_order_addresses",
    "platform_order_lines",
    "platform_code_fsku_mappings",
    "oms_pdd_order_mirror_lines",
    "oms_taobao_order_mirror_lines",
    "oms_jd_order_mirror_lines",
    "oms_pdd_order_mirrors",
    "oms_taobao_order_mirrors",
    "oms_jd_order_mirrors",
    "oms_fsku_components",
    "oms_fskus",
}

WMS_OMS_PROJECTION_TABLES = {
    "wms_oms_fulfillment_order_projection",
    "wms_oms_fulfillment_line_projection",
    "wms_oms_fulfillment_component_projection",
    "wms_oms_fulfillment_projection_sync_runs",
}


def test_base_metadata_has_only_wms_oms_projection_tables() -> None:
    init_models(force=True)

    table_names = set(Base.metadata.tables)
    assert LEGACY_OMS_OWNER_TABLES.isdisjoint(table_names)
    assert WMS_OMS_PROJECTION_TABLES.issubset(table_names)


def test_database_has_only_wms_oms_projection_tables() -> None:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND (
                    tablename LIKE 'oms_%'
                    OR tablename LIKE 'platform_order_%'
                    OR tablename LIKE 'platform_code_%'
                    OR tablename LIKE 'wms_oms_%'
                  )
                ORDER BY tablename
                """
            )
        ).mappings().all()

    table_names = {str(row["tablename"]) for row in rows}
    assert LEGACY_OMS_OWNER_TABLES.isdisjoint(table_names)
    assert WMS_OMS_PROJECTION_TABLES.issubset(table_names)


def test_legacy_oms_owner_orm_source_is_removed() -> None:
    retired_paths = (
        "app/oms/fsku",
        "app/oms/order_facts",
        "app/oms/orders/contracts/orders_view_facts.py",
        "app/oms/orders/repos/orders_view_facts_repo.py",
        "app/oms/orders/routers/orders_view_facts.py",
    )

    existing = [path for path in retired_paths if (ROOT / path).exists()]
    assert existing == []


def test_runtime_source_does_not_reference_legacy_oms_owner_tables() -> None:
    allowed_files = {
        "tests/ci/test_wms_oms_legacy_schema_retired.py",
        "tests/ci/test_wms_oms_fulfillment_projection_ops_boundary.py",
        "tests/ci/test_wms_oms_fulfillment_projection_sync_boundary.py",
        "tests/ci/test_wms_oms_fulfillment_projection_metadata.py",
    }

    hits: list[str] = []
    for root in ("app", "scripts", "tests"):
        for path in (ROOT / root).rglob("*.py"):
            rel = path.relative_to(ROOT).as_posix()
            if rel in allowed_files:
                continue
            text_value = path.read_text(encoding="utf-8")
            for table_name in LEGACY_OMS_OWNER_TABLES:
                if table_name in text_value:
                    hits.append(f"{rel}: {table_name}")

    assert hits == []
