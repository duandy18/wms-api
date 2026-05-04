# app/oms/fsku/models/merchant_code_fsku_binding.py
# OMS owns platform merchant_code / filled_code -> PMS FSKU bindings.
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MerchantCodeFskuBinding(Base):
    """
    商家规格编码（merchant_code / filled_code）→ PMS FSKU 的绑定表。

    唯一域：
    - platform + store_code + merchant_code

    规则：
    - bind = upsert（同码覆盖）
    - unbind = delete
    - FSKU 主数据归 PMS，OMS 这里只保存平台绑定关系
    """

    __tablename__ = "merchant_code_fsku_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    store_code: Mapped[str] = mapped_column(Text, nullable=False)
    merchant_code: Mapped[str] = mapped_column(String(128), nullable=False)

    fsku_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "pms_fskus.id",
            name="merchant_code_fsku_bindings_pms_fsku_id_fkey",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("platform", "store_code", "merchant_code", name="ux_mc_fsku_bindings_store_unique"),
        Index("ix_mc_fsku_bindings_store_lookup", "platform", "store_code", "merchant_code"),
        Index("ix_mc_fsku_bindings_fsku_id", "fsku_id"),
    )
