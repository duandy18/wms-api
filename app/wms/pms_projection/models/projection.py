# app/wms/pms_projection/models/projection.py
# Split note:
# WMS PMS projection 是 PMS 商品主数据在 WMS 执行侧的本地镜像。
# 库存事务后续只能读取这些本地 projection，不应在事务内远程依赖 PMS owner API。
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WmsPmsItemProjection(Base):
    """
    PMS item 在 WMS 的本地投影。

    注意：
    - item_id 保留 PMS owner item id，用作逻辑外键。
    - 不对 items 表建立数据库外键，避免 PMS 物理独立时再次被跨库 FK 绑住。
    """

    __tablename__ = "wms_pms_item_projection"

    item_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=False)
    sku: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    spec: Mapped[Optional[str]] = mapped_column(sa.String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)

    brand_id: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)

    source_updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    source_version: Mapped[Optional[int]] = mapped_column(sa.BigInteger, nullable=True)

    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    __table_args__ = (
        sa.Index("ix_wms_pms_item_projection_enabled", "enabled"),
        sa.Index("ix_wms_pms_item_projection_brand_id", "brand_id"),
        sa.Index("ix_wms_pms_item_projection_category_id", "category_id"),
    )


class WmsPmsItemUomProjection(Base):
    """
    PMS item_uoms 在 WMS 的本地投影。

    ratio_to_base 是 WMS 执行期换算 qty_base 的本地读取值。
    一旦形成库存事实，必须冻结为对应 *_ratio_to_base_snapshot。
    """

    __tablename__ = "wms_pms_item_uom_projection"

    item_uom_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=False)
    item_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("wms_pms_item_projection.item_id", ondelete="RESTRICT"),
        nullable=False,
    )

    uom: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(sa.String(32), nullable=True)
    ratio_to_base: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    is_base: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    is_purchase_default: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    is_inbound_default: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    is_outbound_default: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)

    net_weight_kg: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(10, 3), nullable=True)

    source_updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    source_version: Mapped[Optional[int]] = mapped_column(sa.BigInteger, nullable=True)

    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    __table_args__ = (
        sa.UniqueConstraint("item_uom_id", "item_id", name="uq_wms_pms_item_uom_id_item_id"),
        sa.UniqueConstraint("item_id", "uom", name="uq_wms_pms_item_uom_item_uom"),
        sa.CheckConstraint("ratio_to_base >= 1", name="ck_wms_pms_item_uom_ratio_ge_1"),
        sa.Index("ix_wms_pms_item_uom_item_id", "item_id"),
        sa.Index(
            "uq_wms_pms_item_uom_one_base",
            "item_id",
            unique=True,
            postgresql_where=sa.text("is_base = true"),
        ),
        sa.Index(
            "uq_wms_pms_item_uom_one_purchase_default",
            "item_id",
            unique=True,
            postgresql_where=sa.text("is_purchase_default = true"),
        ),
        sa.Index(
            "uq_wms_pms_item_uom_one_inbound_default",
            "item_id",
            unique=True,
            postgresql_where=sa.text("is_inbound_default = true"),
        ),
        sa.Index(
            "uq_wms_pms_item_uom_one_outbound_default",
            "item_id",
            unique=True,
            postgresql_where=sa.text("is_outbound_default = true"),
        ),
    )


class WmsPmsItemPolicyProjection(Base):
    """
    PMS item policy 在 WMS 的本地投影。

    后续 lot 创建、效期判断、批次来源判断应读取本表，
    不应直接读取 PMS owner items 表。
    """

    __tablename__ = "wms_pms_item_policy_projection"

    item_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("wms_pms_item_projection.item_id", ondelete="RESTRICT"),
        primary_key=True,
    )

    lot_source_policy: Mapped[str] = mapped_column(
        sa.Enum("INTERNAL_ONLY", "SUPPLIER_ONLY", name="lot_source_policy"),
        nullable=False,
    )
    expiry_policy: Mapped[str] = mapped_column(
        sa.Enum("NONE", "REQUIRED", name="expiry_policy"),
        nullable=False,
    )
    shelf_life_value: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    shelf_life_unit: Mapped[Optional[str]] = mapped_column(sa.String(16), nullable=True)

    derivation_allowed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    uom_governance_enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)

    source_updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    source_version: Mapped[Optional[int]] = mapped_column(sa.BigInteger, nullable=True)

    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    __table_args__ = (
        sa.CheckConstraint(
            "expiry_policy = 'REQUIRED' OR "
            "(shelf_life_value IS NULL AND shelf_life_unit IS NULL)",
            name="ck_wms_pms_policy_shelf_life_by_expiry",
        ),
        sa.CheckConstraint(
            "(shelf_life_value IS NULL) = (shelf_life_unit IS NULL)",
            name="ck_wms_pms_policy_shelf_life_pair",
        ),
        sa.CheckConstraint(
            "shelf_life_unit IS NULL OR shelf_life_unit IN ('DAY','WEEK','MONTH','YEAR')",
            name="ck_wms_pms_policy_shelf_life_unit",
        ),
        sa.CheckConstraint(
            "shelf_life_value IS NULL OR shelf_life_value > 0",
            name="ck_wms_pms_policy_shelf_life_value_pos",
        ),
    )


class WmsPmsItemSkuCodeProjection(Base):
    """
    PMS item_sku_codes 在 WMS 的本地投影。

    用于后续 WMS scan / 查询中的 SKU 文本解析。
    """

    __tablename__ = "wms_pms_item_sku_code_projection"

    sku_code_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=False)
    item_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("wms_pms_item_projection.item_id", ondelete="RESTRICT"),
        nullable=False,
    )

    code: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    code_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    is_primary: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)

    effective_from: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    effective_to: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)

    source_updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    source_version: Mapped[Optional[int]] = mapped_column(sa.BigInteger, nullable=True)

    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "sku_code_id",
            "item_id",
            name="uq_wms_pms_item_sku_code_id_item_id",
        ),
        sa.CheckConstraint(
            "length(trim(code)) > 0",
            name="ck_wms_pms_sku_code_non_empty",
        ),
        sa.CheckConstraint(
            "code_type IN ('PRIMARY','ALIAS','LEGACY','MANUAL')",
            name="ck_wms_pms_sku_code_type",
        ),
        sa.CheckConstraint(
            "is_primary = false OR is_active = true",
            name="ck_wms_pms_sku_primary_active",
        ),
        sa.CheckConstraint(
            "is_primary = false OR effective_to IS NULL",
            name="ck_wms_pms_sku_primary_no_effective_to",
        ),
        sa.CheckConstraint(
            "(code_type = 'PRIMARY') = (is_primary = true)",
            name="ck_wms_pms_sku_primary_type",
        ),
        sa.Index("ix_wms_pms_item_sku_code_item_id", "item_id"),
        sa.Index(
            "uq_wms_pms_item_sku_code_one_primary",
            "item_id",
            unique=True,
            postgresql_where=sa.text("is_primary = true"),
        ),
    )


class WmsPmsItemBarcodeProjection(Base):
    """
    PMS item_barcodes 在 WMS 的本地投影。

    用于后续 WMS scan / inbound barcode resolve / return inbound probe。
    """

    __tablename__ = "wms_pms_item_barcode_projection"

    barcode_id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=False)

    item_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("wms_pms_item_projection.item_id", ondelete="RESTRICT"),
        nullable=False,
    )
    item_uom_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    barcode: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    is_primary: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    symbology: Mapped[str] = mapped_column(sa.Text, nullable=False)

    source_updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    source_event_id: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    source_version: Mapped[Optional[int]] = mapped_column(sa.BigInteger, nullable=True)

    synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["item_uom_id", "item_id"],
            ["wms_pms_item_uom_projection.item_uom_id", "wms_pms_item_uom_projection.item_id"],
            name="fk_wms_pms_item_barcode_projection_uom_pair",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "NOT is_primary OR active",
            name="ck_wms_pms_barcode_primary_active",
        ),
        sa.Index("ix_wms_pms_item_barcode_item_id", "item_id"),
        sa.Index("ix_wms_pms_item_barcode_item_uom_id", "item_uom_id"),
        sa.Index(
            "uq_wms_pms_item_barcode_one_primary",
            "item_id",
            unique=True,
            postgresql_where=sa.text("is_primary = true"),
        ),
    )
