from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.pms_projection.models.projection import WmsPmsItemProjection
from app.wms.pms_projection.services.rebuild_service import WmsPmsProjectionRebuildService
from app.wms.pms_projection.services.sync_service import (
    SOURCE_NAME,
    WmsPmsProjectionSyncService,
)


async def _insert_scalar_int(
    session: AsyncSession,
    sql: str,
    params: dict[str, object],
) -> int:
    result = await session.execute(text(sql), params)
    return int(result.scalar_one())


async def _insert_owner_item_bundle(
    session: AsyncSession,
    *,
    prefix: str,
    updated_at: datetime,
) -> dict[str, int | str]:
    item_id = await _insert_scalar_int(
        session,
        """
        INSERT INTO items (
          sku,
          name,
          spec,
          enabled,
          lot_source_policy,
          expiry_policy,
          derivation_allowed,
          uom_governance_enabled,
          updated_at
        )
        VALUES (
          :sku,
          :name,
          :spec,
          true,
          'INTERNAL_ONLY',
          'NONE',
          false,
          true,
          :updated_at
        )
        RETURNING id
        """,
        {
            "sku": f"{prefix}-SKU",
            "name": f"{prefix} item before",
            "spec": "before",
            "updated_at": updated_at,
        },
    )

    item_uom_id = await _insert_scalar_int(
        session,
        """
        INSERT INTO item_uoms (
          item_id,
          uom,
          ratio_to_base,
          display_name,
          net_weight_kg,
          is_base,
          is_purchase_default,
          is_inbound_default,
          is_outbound_default,
          updated_at
        )
        VALUES (
          :item_id,
          'PCS',
          1,
          :display_name,
          0.125,
          true,
          true,
          true,
          true,
          :updated_at
        )
        RETURNING id
        """,
        {
            "item_id": item_id,
            "display_name": f"{prefix} 件",
            "updated_at": updated_at,
        },
    )

    sku_code_id = await _insert_scalar_int(
        session,
        """
        INSERT INTO item_sku_codes (
          item_id,
          code,
          code_type,
          is_primary,
          is_active,
          remark,
          updated_at
        )
        VALUES (
          :item_id,
          :code,
          'PRIMARY',
          true,
          true,
          'before',
          :updated_at
        )
        RETURNING id
        """,
        {
            "item_id": item_id,
            "code": f"{prefix}-CODE",
            "updated_at": updated_at,
        },
    )

    barcode_id = await _insert_scalar_int(
        session,
        """
        INSERT INTO item_barcodes (
          item_id,
          item_uom_id,
          barcode,
          symbology,
          active,
          is_primary,
          updated_at
        )
        VALUES (
          :item_id,
          :item_uom_id,
          :barcode,
          'CUSTOM',
          true,
          true,
          :updated_at
        )
        RETURNING id
        """,
        {
            "item_id": item_id,
            "item_uom_id": item_uom_id,
            "barcode": f"{prefix}-BAR",
            "updated_at": updated_at,
        },
    )

    return {
        "item_id": item_id,
        "item_uom_id": item_uom_id,
        "sku_code_id": sku_code_id,
        "barcode_id": barcode_id,
    }


async def _cursor_row(session: AsyncSession) -> dict[str, object] | None:
    row = (
        await session.execute(
            text(
                """
                SELECT
                  source_name,
                  last_source_updated_at,
                  last_status,
                  last_error,
                  retry_count
                FROM wms_pms_projection_sync_cursors
                WHERE source_name = :source_name
                LIMIT 1
                """
            ),
            {"source_name": SOURCE_NAME},
        )
    ).mappings().first()
    return dict(row) if row is not None else None



async def _reset_sync_cursor(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            DELETE FROM wms_pms_projection_sync_cursors
            WHERE source_name = :source_name
            """
        ),
        {"source_name": SOURCE_NAME},
    )


async def test_sync_once_initializes_cursor_and_rebuilds_projection(
    session: AsyncSession,
) -> None:
    await _reset_sync_cursor(session)

    suffix = uuid4().hex[:10]
    ts = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    bundle = await _insert_owner_item_bundle(
        session,
        prefix=f"SYNC-I-{suffix}",
        updated_at=ts,
    )

    result = await WmsPmsProjectionSyncService(session).sync_once()

    assert result.initialized is True
    assert result.changed_items >= 1
    assert result.source_items >= 1
    assert result.last_source_updated_at >= ts

    projection = await session.get(WmsPmsItemProjection, int(bundle["item_id"]))
    assert projection is not None
    assert projection.name == f"SYNC-I-{suffix} item before"

    cursor = await _cursor_row(session)
    assert cursor is not None
    assert cursor["source_name"] == SOURCE_NAME
    assert cursor["last_status"] == "SUCCESS"
    assert int(cursor["retry_count"]) == 0


async def test_sync_once_rebuilds_only_changed_items_and_advances_cursor(
    session: AsyncSession,
) -> None:
    await _reset_sync_cursor(session)

    suffix = uuid4().hex[:10]
    base_ts = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    target = await _insert_owner_item_bundle(
        session,
        prefix=f"SYNC-T-{suffix}",
        updated_at=base_ts,
    )
    other = await _insert_owner_item_bundle(
        session,
        prefix=f"SYNC-O-{suffix}",
        updated_at=base_ts,
    )

    service = WmsPmsProjectionSyncService(session)
    first = await service.sync_once()
    assert first.initialized is True
    target_ts = first.last_source_updated_at + timedelta(seconds=10)

    target_item_id = int(target["item_id"])
    other_item_id = int(other["item_id"])

    await session.execute(
        text(
            """
            UPDATE items
            SET
              name = :name,
              spec = 'after',
              enabled = false,
              updated_at = :updated_at
            WHERE id = :item_id
            """
        ),
        {
            "item_id": target_item_id,
            "name": f"SYNC-T-{suffix} item after",
            "updated_at": target_ts,
        },
    )
    await session.execute(
        text(
            """
            UPDATE item_uoms
            SET updated_at = :updated_at
            WHERE item_id = :item_id
            """
        ),
        {"item_id": target_item_id, "updated_at": target_ts},
    )
    await session.execute(
        text(
            """
            UPDATE wms_pms_item_projection
            SET name = 'non-target projection marker'
            WHERE item_id = :item_id
            """
        ),
        {"item_id": other_item_id},
    )

    second = await service.sync_once()

    assert second.initialized is False
    assert second.changed_items == 1
    assert second.source_items == 1
    assert second.last_source_updated_at >= target_ts

    session.expire_all()

    target_projection = await session.get(WmsPmsItemProjection, target_item_id)
    assert target_projection is not None
    assert target_projection.name == f"SYNC-T-{suffix} item after"
    assert target_projection.spec == "after"
    assert target_projection.enabled is False

    other_projection = await session.get(WmsPmsItemProjection, other_item_id)
    assert other_projection is not None
    assert other_projection.name == "non-target projection marker"

    cursor = await _cursor_row(session)
    assert cursor is not None
    assert cursor["last_status"] == "SUCCESS"
    assert cursor["last_source_updated_at"] >= target_ts


async def test_sync_once_records_failure_without_advancing_cursor(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _reset_sync_cursor(session)

    suffix = uuid4().hex[:10]
    base_ts = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    bundle = await _insert_owner_item_bundle(
        session,
        prefix=f"SYNC-F-{suffix}",
        updated_at=base_ts,
    )

    service = WmsPmsProjectionSyncService(session)
    first = await service.sync_once()
    assert first.initialized is True
    target_ts = first.last_source_updated_at + timedelta(seconds=10)

    cursor_before = await _cursor_row(session)
    assert cursor_before is not None
    previous_cursor = cursor_before["last_source_updated_at"]

    await session.execute(
        text(
            """
            UPDATE items
            SET updated_at = :updated_at
            WHERE id = :item_id
            """
        ),
        {
            "item_id": int(bundle["item_id"]),
            "updated_at": target_ts,
        },
    )

    async def _raise_on_rebuild_items(self: WmsPmsProjectionRebuildService, item_ids: list[int]):
        raise RuntimeError("forced sync failure")

    monkeypatch.setattr(
        WmsPmsProjectionRebuildService,
        "rebuild_items",
        _raise_on_rebuild_items,
    )

    with pytest.raises(RuntimeError, match="forced sync failure"):
        await WmsPmsProjectionSyncService(session).sync_once()

    cursor_after = await _cursor_row(session)
    assert cursor_after is not None
    assert cursor_after["last_status"] == "FAILED"
    assert cursor_after["last_source_updated_at"] == previous_cursor
    assert "forced sync failure" in str(cursor_after["last_error"])
    assert int(cursor_after["retry_count"]) == 1
