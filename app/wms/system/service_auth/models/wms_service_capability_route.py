# app/wms/system/service_auth/models/wms_service_capability_route.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import relationship

from app.db.base import Base


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


__all__ = ["WmsServiceCapabilityRoute"]
