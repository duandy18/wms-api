# app/wms/system/service_auth/models/wms_service_client.py
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


__all__ = ["WmsServiceClient"]
