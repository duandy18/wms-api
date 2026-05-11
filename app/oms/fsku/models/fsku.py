# app/oms/fsku/models/fsku.py
# Domain move: FSKU master data belongs to PMS.
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Fsku(Base):
    """
    OMS FSKU 组合规则主表。

    终态语义：
    - FSKU 是基于仓库 SKU 的销售组合表达式；
    - code 是 FSKU 业务编码；
    - fsku_expr / normalized_expr 是表达式真相；
    - components 是表达式解析后的结构化组件结果。
    """

    __tablename__ = "oms_fskus"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)

    code: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)

    shape: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="bundle")
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False)

    fsku_expr: Mapped[str] = mapped_column(sa.Text, nullable=False)
    normalized_expr: Mapped[str] = mapped_column(sa.Text, nullable=False)
    expr_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    component_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    components: Mapped[list["FskuComponent"]] = relationship(
        back_populates="fsku",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        sa.CheckConstraint("shape in ('single', 'bundle')", name="ck_oms_fskus_shape"),
        sa.CheckConstraint("status in ('draft', 'published', 'retired')", name="ck_oms_fskus_status"),
        sa.CheckConstraint("expr_type in ('DIRECT', 'SEGMENT_GROUP')", name="ck_oms_fskus_expr_type"),
        sa.CheckConstraint("component_count >= 0", name="ck_oms_fskus_component_count_nonnegative"),
        sa.Index("ix_oms_fskus_status", "status"),
        sa.Index("ux_oms_fskus_code", "code", unique=True),
        sa.Index("ix_oms_fskus_normalized_expr", "normalized_expr"),
    )


class FskuComponent(Base):
    """
    OMS FSKU 组件表。

    注意：
    - 该表不是人工主维护真相；
    - 真相来自 oms_fskus.normalized_expr；
    - 本表是表达式展开后的 SKU 组件缓存 / 执行索引。
    """

    __tablename__ = "oms_fsku_components"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)

    fsku_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    component_sku_code: Mapped[str] = mapped_column(sa.String(128), nullable=False)

    qty_per_fsku: Mapped[Decimal] = mapped_column(sa.Numeric(18, 6), nullable=False)
    alloc_unit_price: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 6),
        nullable=False,
        server_default=sa.text("1"),
    )

    resolved_item_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    resolved_item_sku_code_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    resolved_item_uom_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    sku_code_snapshot: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    item_name_snapshot: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    uom_snapshot: Mapped[str] = mapped_column(sa.String(32), nullable=False)

    sort_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    fsku: Mapped["Fsku"] = relationship(back_populates="components")

    __table_args__ = (
        sa.CheckConstraint("qty_per_fsku > 0", name="ck_oms_fsku_components_qty_positive"),
        sa.CheckConstraint(
            "alloc_unit_price > 0",
            name="ck_oms_fsku_components_alloc_unit_price_positive",
        ),
        sa.ForeignKeyConstraint(
            ["fsku_id"],
            ["oms_fskus.id"],
            name="fk_oms_fsku_components_fsku",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "fsku_id",
            "component_sku_code",
            name="uq_oms_fsku_components_fsku_component_sku",
        ),
        sa.UniqueConstraint(
            "fsku_id",
            "sort_order",
            name="uq_oms_fsku_components_fsku_sort",
        ),
        sa.Index("ix_oms_fsku_components_fsku_id", "fsku_id"),
        sa.Index("ix_oms_fsku_components_resolved_item_id", "resolved_item_id"),
        sa.Index("ix_oms_fsku_components_resolved_sku_code_id", "resolved_item_sku_code_id"),
        sa.Index("ix_oms_fsku_components_resolved_uom_id", "resolved_item_uom_id"),
    )
