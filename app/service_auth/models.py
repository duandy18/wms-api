# app/service_auth/models.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import relationship

from app.db.base import Base


class WmsServiceClient(Base):
    """
    WMS 本地系统间调用方。

    Boundary:
    - 这不是用户表。
    - 这不是页面权限表。
    - 这张表只表示“哪个系统服务可以调用 WMS”。
    """

    __tablename__ = "wms_service_clients"

    __table_args__ = (
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

    id = sa.Column(sa.Integer, autoincrement=True)
    client_code = sa.Column(sa.String(64), nullable=False)
    client_name = sa.Column(sa.String(128), nullable=False)
    description = sa.Column(sa.String(255), nullable=True)
    is_active = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    permissions = relationship(
        "WmsServicePermission",
        back_populates="client",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class WmsServiceCapability(Base):
    """
    WMS 本地系统间调用能力目录。

    Boundary:
    - WMS 自己声明自己暴露哪些 capability。
    - ERP 后续只能读取 WMS 声明的 capability，不猜测 WMS 能力。
    - capability 是系统间调用授权的能力粒度，不是用户页面权限。
    """

    __tablename__ = "wms_service_capabilities"

    __table_args__ = (
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
        sa.Index("ix_wms_service_capabilities_resource_code", "resource_code"),
    )

    id = sa.Column(sa.Integer, autoincrement=True)
    capability_code = sa.Column(sa.String(128), nullable=False)
    capability_name = sa.Column(sa.String(128), nullable=False)
    resource_code = sa.Column(sa.String(64), nullable=False)
    description = sa.Column(sa.String(255), nullable=True)
    is_active = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    permissions = relationship(
        "WmsServicePermission",
        back_populates="capability",
        lazy="selectin",
    )
    routes = relationship(
        "WmsServiceCapabilityRoute",
        back_populates="capability",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class WmsServiceCapabilityRoute(Base):
    """
    WMS capability 与 API 路由的本地映射合同。

    Boundary:
    - 用于说明 WMS 哪些 route 归属于哪个 capability。
    - route mapping 是 WMS 自己声明的执行合同，不由 ERP 猜测。
    - auth_required 表示该路由是否应纳入 service permission 校验。
    """

    __tablename__ = "wms_service_capability_routes"

    __table_args__ = (
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
        sa.Index("ix_wms_service_capability_routes_capability_code", "capability_code"),
    )

    id = sa.Column(sa.Integer, autoincrement=True)
    capability_code = sa.Column(
        sa.String(128),
        sa.ForeignKey(
            "wms_service_capabilities.capability_code",
            name="fk_wms_service_capability_routes_capability_code",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    http_method = sa.Column(sa.String(16), nullable=False)
    route_path = sa.Column(sa.String(255), nullable=False)
    route_name = sa.Column(sa.String(128), nullable=False)
    auth_required = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    is_active = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    capability = relationship(
        "WmsServiceCapability",
        back_populates="routes",
        lazy="joined",
    )


class WmsServicePermission(Base):
    """
    WMS 本地系统间调用权限。

    Boundary:
    - capability_code 表示 WMS 暴露给其他系统的能力。
    - 不复用 users / permissions / user_permissions。
    - 运行时是否放行由 WMS 自己查这张表决定。
    """

    __tablename__ = "wms_service_permissions"

    __table_args__ = (
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
        sa.Index("ix_wms_service_permissions_client_id", "client_id"),
        sa.Index("ix_wms_service_permissions_capability_code", "capability_code"),
    )

    id = sa.Column(sa.Integer, autoincrement=True)
    client_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            "wms_service_clients.id",
            name="fk_wms_service_permissions_client_id_wms_service_clients",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    capability_code = sa.Column(
        sa.String(128),
        sa.ForeignKey(
            "wms_service_capabilities.capability_code",
            name="fk_wms_service_permissions_capability_code",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    description = sa.Column(sa.String(255), nullable=True)
    is_active = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    granted_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    client = relationship(
        "WmsServiceClient",
        back_populates="permissions",
        lazy="joined",
    )
    capability = relationship(
        "WmsServiceCapability",
        back_populates="permissions",
        lazy="joined",
    )


__all__ = [
    "WmsServiceCapability",
    "WmsServiceCapabilityRoute",
    "WmsServiceClient",
    "WmsServicePermission",
]
