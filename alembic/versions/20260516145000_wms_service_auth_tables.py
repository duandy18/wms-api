"""wms service auth execution tables

Revision ID: 20260516145000_wms_svc_auth
Revises: 20260515123000_retire_wms_procurement_nav
Create Date: 2026-05-16 14:50:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260516145000_wms_svc_auth"
down_revision: str | Sequence[str] | None = "20260515123000_retire_wms_procurement_nav"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wms_service_clients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_code", sa.String(length=64), nullable=False),
        sa.Column("client_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wms_service_clients"),
        sa.UniqueConstraint("client_code", name="uq_wms_service_clients_client_code"),
        sa.CheckConstraint(
            "btrim(client_code) <> ''",
            name="ck_wms_service_clients_client_code_not_blank",
        ),
        sa.CheckConstraint(
            "btrim(client_name) <> ''",
            name="ck_wms_service_clients_client_name_not_blank",
        ),
    )

    op.create_table(
        "wms_service_capabilities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("capability_code", sa.String(length=128), nullable=False),
        sa.Column("capability_name", sa.String(length=128), nullable=False),
        sa.Column("resource_code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wms_service_capabilities"),
        sa.UniqueConstraint(
            "capability_code",
            name="uq_wms_service_capabilities_capability_code",
        ),
        sa.CheckConstraint(
            "btrim(capability_code) <> ''",
            name="ck_wms_service_capabilities_capability_code_not_blank",
        ),
        sa.CheckConstraint(
            "btrim(capability_name) <> ''",
            name="ck_wms_service_capabilities_capability_name_not_blank",
        ),
        sa.CheckConstraint(
            "btrim(resource_code) <> ''",
            name="ck_wms_service_capabilities_resource_code_not_blank",
        ),
    )
    op.create_index(
        "ix_wms_service_capabilities_resource_code",
        "wms_service_capabilities",
        ["resource_code"],
    )

    op.create_table(
        "wms_service_capability_routes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("capability_code", sa.String(length=128), nullable=False),
        sa.Column("http_method", sa.String(length=16), nullable=False),
        sa.Column("route_path", sa.String(length=255), nullable=False),
        sa.Column("route_name", sa.String(length=128), nullable=False),
        sa.Column("auth_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["capability_code"],
            ["wms_service_capabilities.capability_code"],
            name="fk_wms_service_capability_routes_capability_code",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wms_service_capability_routes"),
        sa.UniqueConstraint(
            "http_method",
            "route_path",
            name="uq_wms_service_capability_routes_method_path",
        ),
        sa.CheckConstraint(
            "btrim(capability_code) <> ''",
            name="ck_wms_service_capability_routes_capability_code_not_blank",
        ),
        sa.CheckConstraint(
            "btrim(http_method) <> ''",
            name="ck_wms_service_capability_routes_http_method_not_blank",
        ),
        sa.CheckConstraint(
            "btrim(route_path) <> ''",
            name="ck_wms_service_capability_routes_route_path_not_blank",
        ),
        sa.CheckConstraint(
            "btrim(route_name) <> ''",
            name="ck_wms_service_capability_routes_route_name_not_blank",
        ),
    )
    op.create_index(
        "ix_wms_service_capability_routes_capability_code",
        "wms_service_capability_routes",
        ["capability_code"],
    )

    op.create_table(
        "wms_service_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("capability_code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["wms_service_clients.id"],
            name="fk_wms_service_permissions_client_id_wms_service_clients",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["capability_code"],
            ["wms_service_capabilities.capability_code"],
            name="fk_wms_service_permissions_capability_code",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wms_service_permissions"),
        sa.UniqueConstraint(
            "client_id",
            "capability_code",
            name="uq_wms_service_permissions_client_capability",
        ),
        sa.CheckConstraint(
            "btrim(capability_code) <> ''",
            name="ck_wms_service_permissions_capability_code_not_blank",
        ),
    )
    op.create_index(
        "ix_wms_service_permissions_client_id",
        "wms_service_permissions",
        ["client_id"],
    )
    op.create_index(
        "ix_wms_service_permissions_capability_code",
        "wms_service_permissions",
        ["capability_code"],
    )

    op.execute(
        """
        INSERT INTO wms_service_clients (
          client_code,
          client_name,
          description,
          is_active
        )
        VALUES
          (
            'procurement-service',
            'Procurement Service',
            'Procurement 调用 WMS 仓库和采购收货结果能力',
            TRUE
          ),
          (
            'logistics-service',
            'Logistics Service',
            'Logistics 调用 WMS 发货交接能力',
            TRUE
          ),
          (
            'oms-service',
            'OMS Service',
            'OMS 调用 WMS 能力的预留调用方',
            TRUE
          ),
          (
            'erp-service',
            'ERP Service',
            'ERP 调用 WMS 配置/治理能力的预留调用方',
            TRUE
          )
        ON CONFLICT (client_code) DO UPDATE
        SET
          client_name = EXCLUDED.client_name,
          description = EXCLUDED.description,
          is_active = EXCLUDED.is_active
        """
    )

    op.execute(
        """
        INSERT INTO wms_service_capabilities (
          capability_code,
          capability_name,
          resource_code,
          description,
          is_active
        )
        VALUES
          (
            'wms.read.warehouses',
            'Read WMS warehouses',
            'warehouses',
            '读取 WMS 仓库基础下拉能力',
            TRUE
          ),
          (
            'wms.read.procurement_receiving_results',
            'Read WMS procurement receiving results',
            'procurement_receiving_results',
            '读取 WMS 写回给采购系统的收货结果',
            TRUE
          ),
          (
            'wms.read.shipping_handoffs',
            'Read WMS shipping handoffs',
            'shipping_handoffs',
            '读取 WMS 给 Logistics 的待导入发货交接数据',
            TRUE
          ),
          (
            'wms.write.shipping_handoff_import_results',
            'Write WMS shipping handoff import results',
            'shipping_handoff_import_results',
            'Logistics 回写导入发货交接结果',
            TRUE
          ),
          (
            'wms.write.shipping_handoff_shipping_results',
            'Write WMS shipping handoff shipping results',
            'shipping_handoff_shipping_results',
            'Logistics 回写发货完成结果',
            TRUE
          )
        ON CONFLICT (capability_code) DO UPDATE
        SET
          capability_name = EXCLUDED.capability_name,
          resource_code = EXCLUDED.resource_code,
          description = EXCLUDED.description,
          is_active = EXCLUDED.is_active,
          updated_at = CURRENT_TIMESTAMP
        """
    )

    op.execute(
        """
        INSERT INTO wms_service_capability_routes (
          capability_code,
          http_method,
          route_path,
          route_name,
          auth_required,
          is_active
        )
        VALUES
          (
            'wms.read.warehouses',
            'GET',
            '/wms/read/v1/warehouses',
            'list_wms_read_warehouses',
            TRUE,
            TRUE
          ),
          (
            'wms.read.warehouses',
            'GET',
            '/wms/read/v1/warehouses/{warehouse_id}',
            'get_wms_read_warehouse',
            TRUE,
            TRUE
          ),
          (
            'wms.read.procurement_receiving_results',
            'GET',
            '/wms/inbound/procurement-receiving-results',
            'list_procurement_receiving_results_endpoint',
            TRUE,
            TRUE
          ),
          (
            'wms.read.procurement_receiving_results',
            'GET',
            '/wms/inbound/procurement-receiving-results/{event_id}',
            'get_procurement_receiving_result_detail_endpoint',
            TRUE,
            TRUE
          ),
          (
            'wms.read.shipping_handoffs',
            'GET',
            '/shipping-assist/handoffs/ready',
            'list_shipping_assist_handoff_ready',
            TRUE,
            TRUE
          ),
          (
            'wms.write.shipping_handoff_import_results',
            'POST',
            '/shipping-assist/handoffs/import-results',
            'record_shipping_assist_handoff_import_result',
            TRUE,
            TRUE
          ),
          (
            'wms.write.shipping_handoff_shipping_results',
            'POST',
            '/shipping-assist/handoffs/shipping-results',
            'record_shipping_assist_handoff_shipping_result',
            TRUE,
            TRUE
          )
        ON CONFLICT (http_method, route_path) DO UPDATE
        SET
          capability_code = EXCLUDED.capability_code,
          route_name = EXCLUDED.route_name,
          auth_required = EXCLUDED.auth_required,
          is_active = EXCLUDED.is_active
        """
    )

    op.execute(
        """
        WITH desired_permissions AS (
          SELECT
            'procurement-service' AS client_code,
            'wms.read.warehouses' AS capability_code,
            'Procurement 读取 WMS 仓库下拉' AS description
          UNION ALL
          SELECT
            'procurement-service',
            'wms.read.procurement_receiving_results',
            'Procurement 读取 WMS 采购收货结果'
          UNION ALL
          SELECT
            'logistics-service',
            'wms.read.shipping_handoffs',
            'Logistics 拉取 WMS 待导入发货交接数据'
          UNION ALL
          SELECT
            'logistics-service',
            'wms.write.shipping_handoff_import_results',
            'Logistics 回写发货交接导入结果'
          UNION ALL
          SELECT
            'logistics-service',
            'wms.write.shipping_handoff_shipping_results',
            'Logistics 回写发货完成结果'
        )
        INSERT INTO wms_service_permissions (
          client_id,
          capability_code,
          description,
          is_active
        )
        SELECT
          c.id,
          p.capability_code,
          p.description,
          TRUE
        FROM desired_permissions p
        JOIN wms_service_clients c
          ON c.client_code = p.client_code
        ON CONFLICT (client_id, capability_code) DO UPDATE
        SET
          description = EXCLUDED.description,
          is_active = EXCLUDED.is_active
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wms_service_permissions_capability_code",
        table_name="wms_service_permissions",
    )
    op.drop_index(
        "ix_wms_service_permissions_client_id",
        table_name="wms_service_permissions",
    )
    op.drop_table("wms_service_permissions")

    op.drop_index(
        "ix_wms_service_capability_routes_capability_code",
        table_name="wms_service_capability_routes",
    )
    op.drop_table("wms_service_capability_routes")

    op.drop_index(
        "ix_wms_service_capabilities_resource_code",
        table_name="wms_service_capabilities",
    )
    op.drop_table("wms_service_capabilities")

    op.drop_table("wms_service_clients")
