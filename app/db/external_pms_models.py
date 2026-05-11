# app/db/external_pms_models.py
"""
External PMS ORM anchors for the shared-database transition.

PMS owner runtime has moved to pms-api. wms-api still has WMS/OMS/Procurement
tables with database FKs and legacy SQLAlchemy relationship("Item") references
to PMS-owned tables.

These ORM classes are FK / mapper anchors only:
- do not add PMS business fields here
- do not use these classes for PMS reads/writes
- do not let Alembic manage these tables from wms-api
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


PMS_OWNED_TABLES: frozenset[str] = frozenset(
    {
        "items",
        "item_uoms",
        "item_barcodes",
        "item_sku_codes",
        "pms_brands",
        "pms_business_categories",
        "item_attribute_defs",
        "item_attribute_options",
        "item_attribute_values",
        "sku_code_templates",
        "sku_code_template_segments",
    }
)

PMS_EXTERNAL_ANCHOR_TABLES: frozenset[str] = frozenset(
    {
        "items",
        "item_uoms",
        "item_sku_codes",
    }
)


class Item(Base):
    __tablename__ = "items"
    __table_args__ = {"info": {"external_owner": "pms-api", "anchor_only": True}}

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)


class ItemUOM(Base):
    __tablename__ = "item_uoms"
    __table_args__ = (
        sa.UniqueConstraint("id", "item_id", name="uq_item_uoms_id_item_id"),
        {"info": {"external_owner": "pms-api", "anchor_only": True}},
    )

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)


class ItemSkuCode(Base):
    __tablename__ = "item_sku_codes"
    __table_args__ = (
        sa.UniqueConstraint("id", "item_id", name="uq_item_sku_codes_id_item_id"),
        {"info": {"external_owner": "pms-api", "anchor_only": True}},
    )

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)


__all__ = [
    "Item",
    "ItemSkuCode",
    "ItemUOM",
    "PMS_EXTERNAL_ANCHOR_TABLES",
    "PMS_OWNED_TABLES",
]
