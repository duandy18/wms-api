# app/oms/fsku/models/platform_code_fsku_mapping.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlatformCodeFskuMapping(Base):
    """
    平台订单行身份 → OMS FSKU 的映射表。

    identity_kind:
    - merchant_code: 平台/商家填写的外部编码
    - platform_sku_id: 平台规格 ID
    - platform_item_sku: platform_item_id + platform_sku_id 组合身份
    """

    __tablename__ = "platform_code_fsku_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    store_code: Mapped[str] = mapped_column(Text, nullable=False)

    identity_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    identity_value: Mapped[str] = mapped_column(String(256), nullable=False)

    fsku_id: Mapped[int] = mapped_column(
        ForeignKey(
            "oms_fskus.id",
            name="platform_code_fsku_mappings_oms_fsku_id_fkey",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "store_code",
            "identity_kind",
            "identity_value",
            name="ux_platform_code_fsku_mappings_unique",
        ),
        Index(
            "ix_platform_code_fsku_mappings_lookup",
            "platform",
            "store_code",
            "identity_kind",
            "identity_value",
        ),
    )
