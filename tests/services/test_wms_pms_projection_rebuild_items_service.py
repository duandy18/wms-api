from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.pms_projection.models.projection import (
    WmsPmsItemProjection,
    WmsPmsItemUomProjection,
)
from app.wms.pms_projection.services.rebuild_service import (
    WmsPmsProjectionRebuildService,
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
          uom_governance_enabled
        )
        VALUES (
          :sku,
          :name,
          :spec,
          true,
          'INTERNAL_ONLY',
          'NONE',
          false,
          true
        )
        RETURNING id
        """,
        {
            "sku": f"{prefix}-SKU",
            "name": f"{prefix} item before",
            "spec": "before",
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
          is_outbound_default
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
          true
        )
        RETURNING id
        """,
        {
            "item_id": item_id,
            "display_name": f"{prefix} 件",
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
          remark
        )
        VALUES (
          :item_id,
          :code,
          'PRIMARY',
          true,
          true,
          'before'
        )
        RETURNING id
        """,
        {
            "item_id": item_id,
            "code": f"{prefix}-CODE",
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
          is_primary
        )
        VALUES (
          :item_id,
          :item_uom_id,
          :barcode,
          'CUSTOM',
          true,
          true
        )
        RETURNING id
        """,
        {
            "item_id": item_id,
            "item_uom_id": item_uom_id,
            "barcode": f"{prefix}-BAR",
        },
    )

    return {
        "item_id": item_id,
        "item_uom_id": item_uom_id,
        "sku_code_id": sku_code_id,
        "barcode_id": barcode_id,
        "sku": f"{prefix}-SKU",
        "code": f"{prefix}-CODE",
        "barcode": f"{prefix}-BAR",
    }


async def _insert_stale_uom_projection(
    session: AsyncSession,
    *,
    item_id: int,
    item_uom_id: int,
    uom: str,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO wms_pms_item_uom_projection (
              item_uom_id,
              item_id,
              uom,
              display_name,
              ratio_to_base,
              is_base,
              is_purchase_default,
              is_inbound_default,
              is_outbound_default,
              source_updated_at
            )
            VALUES (
              :item_uom_id,
              :item_id,
              :uom,
              :display_name,
              1,
              false,
              false,
              false,
              false,
              now()
            )
            """
        ),
        {
            "item_uom_id": item_uom_id,
            "item_id": item_id,
            "uom": uom,
            "display_name": f"{uom} stale",
        },
    )


async def test_rebuild_items_updates_target_and_preserves_non_target_projection(
    session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:10]
    target = await _insert_owner_item_bundle(session, prefix=f"RBITEM-T-{suffix}")
    other = await _insert_owner_item_bundle(session, prefix=f"RBITEM-O-{suffix}")

    service = WmsPmsProjectionRebuildService(session)
    await service.rebuild_all()

    target_item_id = int(target["item_id"])
    other_item_id = int(other["item_id"])

    target_stale_uom_id = 991_000_000
    other_stale_uom_id = 992_000_000

    await _insert_stale_uom_projection(
        session,
        item_id=target_item_id,
        item_uom_id=target_stale_uom_id,
        uom=f"TSTALE{suffix[:4]}",
    )
    await _insert_stale_uom_projection(
        session,
        item_id=other_item_id,
        item_uom_id=other_stale_uom_id,
        uom=f"OSTALE{suffix[:4]}",
    )

    await session.execute(
        text(
            """
            UPDATE items
            SET
              name = :name,
              spec = 'after',
              enabled = false,
              updated_at = now()
            WHERE id = :item_id
            """
        ),
        {
            "item_id": target_item_id,
            "name": f"RBITEM-T-{suffix} item after",
        },
    )
    await session.execute(
        text(
            """
            UPDATE item_uoms
            SET
              display_name = :display_name,
              updated_at = now()
            WHERE id = :item_uom_id
            """
        ),
        {
            "item_uom_id": int(target["item_uom_id"]),
            "display_name": f"RBITEM-T-{suffix} 单件",
        },
    )
    await session.execute(
        text(
            """
            UPDATE wms_pms_item_projection
            SET
              name = :name,
              updated_at = now()
            WHERE item_id = :item_id
            """
        ),
        {
            "item_id": other_item_id,
            "name": "non-target projection marker",
        },
    )

    result = await service.rebuild_items([target_item_id])

    assert result.source_items == 1
    assert result.source_uoms == 1
    assert result.source_policies == 1
    assert result.source_sku_codes == 1
    assert result.source_barcodes == 1
    assert result.deleted_items == 0
    assert result.deleted_policies == 0
    assert result.deleted_uoms >= 1

    session.expire_all()

    target_projection = await session.get(WmsPmsItemProjection, target_item_id)
    assert target_projection is not None
    assert target_projection.name == f"RBITEM-T-{suffix} item after"
    assert target_projection.spec == "after"
    assert target_projection.enabled is False

    target_uom_projection = await session.get(WmsPmsItemUomProjection, int(target["item_uom_id"]))
    assert target_uom_projection is not None
    assert target_uom_projection.display_name == f"RBITEM-T-{suffix} 单件"

    deleted_target_stale = await session.get(WmsPmsItemUomProjection, target_stale_uom_id)
    assert deleted_target_stale is None

    other_projection = await session.get(WmsPmsItemProjection, other_item_id)
    assert other_projection is not None
    assert other_projection.name == "non-target projection marker"

    other_stale = await session.get(WmsPmsItemUomProjection, other_stale_uom_id)
    assert other_stale is not None


async def test_rebuild_items_empty_input_is_noop(session: AsyncSession) -> None:
    result = await WmsPmsProjectionRebuildService(session).rebuild_items([])

    assert result.source_items == 0
    assert result.source_uoms == 0
    assert result.source_policies == 0
    assert result.source_sku_codes == 0
    assert result.source_barcodes == 0
    assert result.deleted_items == 0
    assert result.deleted_uoms == 0
    assert result.deleted_policies == 0
    assert result.deleted_sku_codes == 0
    assert result.deleted_barcodes == 0


async def test_rebuild_items_removes_projection_for_missing_owner_item(
    session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:10]
    bundle = await _insert_owner_item_bundle(session, prefix=f"RBITEM-D-{suffix}")

    service = WmsPmsProjectionRebuildService(session)
    await service.rebuild_all()

    item_id = int(bundle["item_id"])
    item_uom_id = int(bundle["item_uom_id"])

    assert await session.get(WmsPmsItemProjection, item_id) is not None
    assert await session.get(WmsPmsItemUomProjection, item_uom_id) is not None

    await session.execute(
        text("DELETE FROM item_barcodes WHERE item_id = :item_id"),
        {"item_id": item_id},
    )
    await session.execute(
        text("DELETE FROM item_sku_codes WHERE item_id = :item_id"),
        {"item_id": item_id},
    )
    await session.execute(
        text("DELETE FROM item_uoms WHERE item_id = :item_id"),
        {"item_id": item_id},
    )
    await session.execute(
        text("DELETE FROM items WHERE id = :item_id"),
        {"item_id": item_id},
    )

    result = await service.rebuild_items([item_id])

    assert result.source_items == 0
    assert result.source_uoms == 0
    assert result.source_policies == 0
    assert result.source_sku_codes == 0
    assert result.source_barcodes == 0
    assert result.deleted_items == 1
    assert result.deleted_policies == 1
    assert result.deleted_uoms >= 1

    session.expire_all()

    assert await session.get(WmsPmsItemProjection, item_id) is None
    assert await session.get(WmsPmsItemUomProjection, item_uom_id) is None
