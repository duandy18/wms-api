from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.wms.pms_projection.models.projection import (
    WmsPmsItemBarcodeProjection,
    WmsPmsItemPolicyProjection,
    WmsPmsItemProjection,
    WmsPmsItemSkuCodeProjection,
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


async def test_wms_pms_projection_rebuild_is_idempotent_and_updates_source_rows(
    session: AsyncSession,
) -> None:
    suffix = uuid4().hex[:10]
    sku = f"PRJ2-SKU-{suffix}"
    sku_code = f"PRJ2-CODE-{suffix}"
    barcode = f"PRJ2-BAR-{suffix}"
    stale_item_id = 900_000_000

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
            "sku": sku,
            "name": f"Projection Test Item {suffix}",
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
            "display_name": "件",
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
            "code": sku_code,
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
            "barcode": barcode,
        },
    )

    await session.execute(
        text(
            """
            INSERT INTO wms_pms_item_projection (
              item_id,
              sku,
              name,
              enabled,
              source_updated_at
            )
            VALUES (
              :item_id,
              :sku,
              :name,
              true,
              now()
            )
            """
        ),
        {
            "item_id": stale_item_id,
            "sku": f"STALE-{suffix}",
            "name": "stale projection row",
        },
    )

    service = WmsPmsProjectionRebuildService(session)
    first_result = await service.rebuild_all()

    assert first_result.source_items >= 1
    assert first_result.source_uoms >= 1
    assert first_result.source_policies >= 1
    assert first_result.source_sku_codes >= 1
    assert first_result.source_barcodes >= 1
    assert first_result.deleted_items >= 1

    session.expire_all()

    item_projection = await session.get(WmsPmsItemProjection, item_id)
    assert item_projection is not None
    assert item_projection.sku == sku
    assert item_projection.name == f"Projection Test Item {suffix}"
    assert item_projection.spec == "before"
    assert item_projection.enabled is True
    assert item_projection.source_event_id is None
    assert item_projection.source_version is None

    policy_projection = await session.get(WmsPmsItemPolicyProjection, item_id)
    assert policy_projection is not None
    assert policy_projection.lot_source_policy == "INTERNAL_ONLY"
    assert policy_projection.expiry_policy == "NONE"
    assert policy_projection.shelf_life_value is None
    assert policy_projection.shelf_life_unit is None
    assert policy_projection.derivation_allowed is False
    assert policy_projection.uom_governance_enabled is True

    uom_projection = await session.get(WmsPmsItemUomProjection, item_uom_id)
    assert uom_projection is not None
    assert uom_projection.item_id == item_id
    assert uom_projection.uom == "PCS"
    assert uom_projection.display_name == "件"
    assert uom_projection.ratio_to_base == 1
    assert uom_projection.is_base is True

    sku_projection = await session.get(WmsPmsItemSkuCodeProjection, sku_code_id)
    assert sku_projection is not None
    assert sku_projection.item_id == item_id
    assert sku_projection.code == sku_code
    assert sku_projection.code_type == "PRIMARY"
    assert sku_projection.is_primary is True
    assert sku_projection.is_active is True
    assert sku_projection.remark == "before"

    barcode_projection = await session.get(WmsPmsItemBarcodeProjection, barcode_id)
    assert barcode_projection is not None
    assert barcode_projection.item_id == item_id
    assert barcode_projection.item_uom_id == item_uom_id
    assert barcode_projection.barcode == barcode
    assert barcode_projection.active is True
    assert barcode_projection.is_primary is True
    assert barcode_projection.symbology == "CUSTOM"

    stale_projection = await session.get(WmsPmsItemProjection, stale_item_id)
    assert stale_projection is None

    second_result = await service.rebuild_all()
    assert second_result.source_items == first_result.source_items
    assert second_result.source_uoms == first_result.source_uoms
    assert second_result.source_policies == first_result.source_policies
    assert second_result.source_sku_codes == first_result.source_sku_codes
    assert second_result.source_barcodes == first_result.source_barcodes

    await session.execute(
        text(
            """
            UPDATE items
            SET
              name = :name,
              spec = :spec,
              enabled = false,
              updated_at = now()
            WHERE id = :item_id
            """
        ),
        {
            "item_id": item_id,
            "name": f"Projection Test Item Updated {suffix}",
            "spec": "after",
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
            "item_uom_id": item_uom_id,
            "display_name": "单件",
        },
    )
    await session.execute(
        text(
            """
            UPDATE item_sku_codes
            SET
              remark = :remark,
              updated_at = now()
            WHERE id = :sku_code_id
            """
        ),
        {
            "sku_code_id": sku_code_id,
            "remark": "after",
        },
    )
    await session.execute(
        text(
            """
            UPDATE item_barcodes
            SET
              symbology = :symbology,
              updated_at = now()
            WHERE id = :barcode_id
            """
        ),
        {
            "barcode_id": barcode_id,
            "symbology": "GS1",
        },
    )

    await service.rebuild_all()
    session.expire_all()

    item_projection = await session.get(WmsPmsItemProjection, item_id)
    assert item_projection is not None
    assert item_projection.name == f"Projection Test Item Updated {suffix}"
    assert item_projection.spec == "after"
    assert item_projection.enabled is False

    uom_projection = await session.get(WmsPmsItemUomProjection, item_uom_id)
    assert uom_projection is not None
    assert uom_projection.display_name == "单件"

    sku_projection = await session.get(WmsPmsItemSkuCodeProjection, sku_code_id)
    assert sku_projection is not None
    assert sku_projection.remark == "after"

    barcode_projection = await session.get(WmsPmsItemBarcodeProjection, barcode_id)
    assert barcode_projection is not None
    assert barcode_projection.symbology == "GS1"

    item_count = await session.scalar(sa.select(sa.func.count(WmsPmsItemProjection.item_id)))
    uom_count = await session.scalar(sa.select(sa.func.count(WmsPmsItemUomProjection.item_uom_id)))
    policy_count = await session.scalar(sa.select(sa.func.count(WmsPmsItemPolicyProjection.item_id)))
    sku_code_count = await session.scalar(
        sa.select(sa.func.count(WmsPmsItemSkuCodeProjection.sku_code_id))
    )
    barcode_count = await session.scalar(
        sa.select(sa.func.count(WmsPmsItemBarcodeProjection.barcode_id))
    )

    assert int(item_count or 0) == second_result.source_items
    assert int(uom_count or 0) == second_result.source_uoms
    assert int(policy_count or 0) == second_result.source_policies
    assert int(sku_code_count or 0) == second_result.source_sku_codes
    assert int(barcode_count or 0) == second_result.source_barcodes
