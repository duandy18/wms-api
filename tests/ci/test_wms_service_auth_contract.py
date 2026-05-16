# tests/ci/test_wms_service_auth_contract.py
from __future__ import annotations

from pathlib import Path

from app.db.base import Base, init_models
from app.wms.system.service_auth.models import (
    WmsServiceCapability,
    WmsServiceCapabilityRoute,
    WmsServiceClient,
    WmsServicePermission,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic/versions/20260516145000_wms_service_auth_tables.py"

EXPECTED_CLIENT_CODES = {
    "procurement-service",
    "logistics-service",
    "oms-service",
    "erp-service",
}

EXPECTED_CAPABILITY_CODES = {
    "wms.read.warehouses",
    "wms.read.procurement_receiving_results",
    "wms.read.shipping_handoffs",
    "wms.write.shipping_handoff_import_results",
    "wms.write.shipping_handoff_shipping_results",
}

EXPECTED_ROUTE_MAPPINGS = {
    ("GET", "/wms/read/v1/warehouses", "wms.read.warehouses"),
    ("GET", "/wms/read/v1/warehouses/{warehouse_id}", "wms.read.warehouses"),
    (
        "GET",
        "/wms/inbound/procurement-receiving-results",
        "wms.read.procurement_receiving_results",
    ),
    (
        "GET",
        "/wms/inbound/procurement-receiving-results/{event_id}",
        "wms.read.procurement_receiving_results",
    ),
    (
        "GET",
        "/shipping-assist/handoffs/ready",
        "wms.read.shipping_handoffs",
    ),
    (
        "POST",
        "/shipping-assist/handoffs/import-results",
        "wms.write.shipping_handoff_import_results",
    ),
    (
        "POST",
        "/shipping-assist/handoffs/shipping-results",
        "wms.write.shipping_handoff_shipping_results",
    ),
}


def _constraint_names(table_name: str) -> set[str]:
    return {constraint.name for constraint in Base.metadata.tables[table_name].constraints}


def test_wms_service_auth_models_are_registered_in_metadata() -> None:
    init_models(force=True)

    assert WmsServiceClient.__tablename__ == "wms_service_clients"
    assert WmsServiceCapability.__tablename__ == "wms_service_capabilities"
    assert WmsServiceCapabilityRoute.__tablename__ == "wms_service_capability_routes"
    assert WmsServicePermission.__tablename__ == "wms_service_permissions"

    assert "wms_service_clients" in Base.metadata.tables
    assert "wms_service_capabilities" in Base.metadata.tables
    assert "wms_service_capability_routes" in Base.metadata.tables
    assert "wms_service_permissions" in Base.metadata.tables


def test_wms_service_auth_model_is_loaded_by_db_base() -> None:
    text = (ROOT / "app/db/base.py").read_text(encoding="utf-8")

    assert '"app.wms.system.service_auth.models"' in text


def test_wms_service_clients_table_contract() -> None:
    init_models(force=True)
    table = Base.metadata.tables["wms_service_clients"]

    assert {
        "id",
        "client_code",
        "client_name",
        "description",
        "is_active",
        "created_at",
    } == set(table.c.keys())

    assert table.c.client_code.type.length == 64
    assert table.c.client_name.type.length == 128
    assert table.c.description.type.length == 255
    assert str(table.c.is_active.server_default.arg) == "true"
    assert str(table.c.created_at.server_default.arg) == "CURRENT_TIMESTAMP"

    constraint_names = _constraint_names("wms_service_clients")
    assert "pk_wms_service_clients" in constraint_names
    assert "uq_wms_service_clients_client_code" in constraint_names
    assert "ck_wms_service_clients_client_code_not_blank" in constraint_names
    assert "ck_wms_service_clients_client_name_not_blank" in constraint_names


def test_wms_service_capabilities_table_contract() -> None:
    init_models(force=True)
    table = Base.metadata.tables["wms_service_capabilities"]

    assert {
        "id",
        "capability_code",
        "capability_name",
        "resource_code",
        "description",
        "is_active",
        "created_at",
        "updated_at",
    } == set(table.c.keys())

    assert table.c.capability_code.type.length == 128
    assert table.c.capability_name.type.length == 128
    assert table.c.resource_code.type.length == 64
    assert table.c.description.type.length == 255
    assert str(table.c.is_active.server_default.arg) == "true"
    assert str(table.c.created_at.server_default.arg) == "CURRENT_TIMESTAMP"
    assert str(table.c.updated_at.server_default.arg) == "CURRENT_TIMESTAMP"

    constraint_names = _constraint_names("wms_service_capabilities")
    assert "pk_wms_service_capabilities" in constraint_names
    assert "uq_wms_service_capabilities_capability_code" in constraint_names
    assert "ck_wms_service_capabilities_capability_code_not_blank" in constraint_names
    assert "ck_wms_service_capabilities_capability_name_not_blank" in constraint_names
    assert "ck_wms_service_capabilities_resource_code_not_blank" in constraint_names

    index_names = {index.name for index in table.indexes}
    assert "ix_wms_service_capabilities_resource_code" in index_names


def test_wms_service_capability_routes_table_contract() -> None:
    init_models(force=True)
    table = Base.metadata.tables["wms_service_capability_routes"]

    assert {
        "id",
        "capability_code",
        "http_method",
        "route_path",
        "route_name",
        "auth_required",
        "is_active",
        "created_at",
    } == set(table.c.keys())

    assert table.c.capability_code.type.length == 128
    assert table.c.http_method.type.length == 16
    assert table.c.route_path.type.length == 255
    assert table.c.route_name.type.length == 128
    assert str(table.c.auth_required.server_default.arg) == "true"
    assert str(table.c.is_active.server_default.arg) == "true"
    assert str(table.c.created_at.server_default.arg) == "CURRENT_TIMESTAMP"

    foreign_keys = list(table.c.capability_code.foreign_keys)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].column.table.name == "wms_service_capabilities"
    assert foreign_keys[0].column.name == "capability_code"
    assert foreign_keys[0].ondelete == "RESTRICT"
    assert foreign_keys[0].constraint.name == "fk_wms_service_capability_routes_capability_code"

    constraint_names = _constraint_names("wms_service_capability_routes")
    assert "pk_wms_service_capability_routes" in constraint_names
    assert "uq_wms_service_capability_routes_method_path" in constraint_names
    assert "ck_wms_service_capability_routes_capability_code_not_blank" in constraint_names
    assert "ck_wms_service_capability_routes_http_method_not_blank" in constraint_names
    assert "ck_wms_service_capability_routes_route_path_not_blank" in constraint_names
    assert "ck_wms_service_capability_routes_route_name_not_blank" in constraint_names

    index_names = {index.name for index in table.indexes}
    assert "ix_wms_service_capability_routes_capability_code" in index_names


def test_wms_service_permissions_table_contract() -> None:
    init_models(force=True)
    table = Base.metadata.tables["wms_service_permissions"]

    assert {
        "id",
        "client_id",
        "capability_code",
        "description",
        "is_active",
        "granted_at",
    } == set(table.c.keys())

    assert table.c.capability_code.type.length == 128
    assert table.c.description.type.length == 255
    assert str(table.c.is_active.server_default.arg) == "true"
    assert str(table.c.granted_at.server_default.arg) == "CURRENT_TIMESTAMP"

    target_tables = {foreign_key.column.table.name for foreign_key in table.foreign_keys}
    assert target_tables == {
        "wms_service_clients",
        "wms_service_capabilities",
    }

    capability_fks = [
        foreign_key
        for foreign_key in table.c.capability_code.foreign_keys
        if foreign_key.column.table.name == "wms_service_capabilities"
    ]
    assert len(capability_fks) == 1
    assert capability_fks[0].column.name == "capability_code"
    assert capability_fks[0].ondelete == "RESTRICT"
    assert capability_fks[0].constraint.name == "fk_wms_service_permissions_capability_code"

    constraint_names = _constraint_names("wms_service_permissions")
    assert "pk_wms_service_permissions" in constraint_names
    assert "uq_wms_service_permissions_client_capability" in constraint_names
    assert "ck_wms_service_permissions_capability_code_not_blank" in constraint_names

    index_names = {index.name for index in table.indexes}
    assert "ix_wms_service_permissions_client_id" in index_names
    assert "ix_wms_service_permissions_capability_code" in index_names


def test_wms_service_permissions_do_not_reuse_user_permission_tables() -> None:
    init_models(force=True)
    table = Base.metadata.tables["wms_service_permissions"]

    assert "permission_id" not in table.c
    assert "user_id" not in table.c


def test_wms_service_auth_migration_contains_catalog_routes_and_seed_data() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260516145000_wms_svc_auth"' in text
    assert (
        'down_revision: str | Sequence[str] | None = '
        '"20260515123000_retire_wms_procurement_nav"'
    ) in text

    assert '"wms_service_clients"' in text
    assert '"wms_service_capabilities"' in text
    assert '"wms_service_capability_routes"' in text
    assert '"wms_service_permissions"' in text

    assert "fk_wms_service_permissions_client_id_wms_service_clients" in text
    assert "fk_wms_service_permissions_capability_code" in text
    assert "fk_wms_service_capability_routes_capability_code" in text
    assert "uq_wms_service_capability_routes_method_path" in text

    for client_code in EXPECTED_CLIENT_CODES:
        assert client_code in text

    for capability_code in EXPECTED_CAPABILITY_CODES:
        assert capability_code in text

    for method, route_path, capability_code in EXPECTED_ROUTE_MAPPINGS:
        assert method in text
        assert route_path in text
        assert capability_code in text
