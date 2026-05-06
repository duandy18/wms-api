# app/shipping_assist/records/models/logistics_shipping_record_sync_cursor.py
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LogisticsShippingRecordSyncCursor(Base):
    """Cursor for WMS importing Logistics shipping record facts."""

    __tablename__ = "logistics_shipping_record_sync_cursors"

    source: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    last_cursor: Mapped[int] = mapped_column(
        sa.BigInteger,
        nullable=False,
        server_default=sa.text("0"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
