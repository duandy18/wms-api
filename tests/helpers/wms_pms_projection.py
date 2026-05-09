from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def sync_wms_pms_projection_for_item(
    session: AsyncSession,
    *,
    item_id: int,
) -> None:
    """
    测试专用：把单个 owner item 当前状态同步到 WMS PMS projection。

    适用场景：
    - 测试内直接 INSERT / UPDATE items、item_uoms、item_barcodes、item_sku_codes；
    - 随后调用 WMS lot / receiving / inbound commit / stock adjust 等只读 projection 的执行链。
    """
    item_id = int(item_id)

    for table_name in (
        "wms_pms_item_barcode_projection",
        "wms_pms_item_sku_code_projection",
        "wms_pms_item_policy_projection",
        "wms_pms_item_uom_projection",
        "wms_pms_item_projection",
    ):
        await session.execute(
            text(f"DELETE FROM {table_name} WHERE item_id = :item_id"),
            {"item_id": item_id},
        )

    await session.execute(
        text(
            """
            INSERT INTO wms_pms_item_projection (
              item_id,
              sku,
              name,
              spec,
              enabled,
              brand_id,
              category_id,
              source_updated_at
            )
            SELECT
              i.id,
              i.sku,
              i.name,
              i.spec,
              i.enabled,
              i.brand_id,
              i.category_id,
              COALESCE(i.updated_at, now())
            FROM items i
            WHERE i.id = :item_id
            """
        ),
        {"item_id": item_id},
    )

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
              net_weight_kg,
              source_updated_at
            )
            SELECT
              u.id,
              u.item_id,
              u.uom,
              u.display_name,
              u.ratio_to_base,
              u.is_base,
              u.is_purchase_default,
              u.is_inbound_default,
              u.is_outbound_default,
              u.net_weight_kg,
              COALESCE(u.updated_at, now())
            FROM item_uoms u
            JOIN wms_pms_item_projection p
              ON p.item_id = u.item_id
            WHERE u.item_id = :item_id
            ORDER BY u.id ASC
            """
        ),
        {"item_id": item_id},
    )

    await session.execute(
        text(
            """
            INSERT INTO wms_pms_item_policy_projection (
              item_id,
              lot_source_policy,
              expiry_policy,
              shelf_life_value,
              shelf_life_unit,
              derivation_allowed,
              uom_governance_enabled,
              source_updated_at
            )
            SELECT
              i.id,
              i.lot_source_policy,
              i.expiry_policy,
              i.shelf_life_value,
              i.shelf_life_unit,
              i.derivation_allowed,
              i.uom_governance_enabled,
              COALESCE(i.updated_at, now())
            FROM items i
            JOIN wms_pms_item_projection p
              ON p.item_id = i.id
            WHERE i.id = :item_id
            """
        ),
        {"item_id": item_id},
    )

    await session.execute(
        text(
            """
            INSERT INTO wms_pms_item_sku_code_projection (
              sku_code_id,
              item_id,
              code,
              code_type,
              is_primary,
              is_active,
              effective_from,
              effective_to,
              remark,
              source_updated_at
            )
            SELECT
              sc.id,
              sc.item_id,
              sc.code,
              sc.code_type,
              sc.is_primary,
              sc.is_active,
              sc.effective_from,
              sc.effective_to,
              sc.remark,
              COALESCE(sc.updated_at, now())
            FROM item_sku_codes sc
            JOIN wms_pms_item_projection p
              ON p.item_id = sc.item_id
            WHERE sc.item_id = :item_id
            ORDER BY sc.id ASC
            """
        ),
        {"item_id": item_id},
    )

    await session.execute(
        text(
            """
            INSERT INTO wms_pms_item_barcode_projection (
              barcode_id,
              item_id,
              item_uom_id,
              barcode,
              active,
              is_primary,
              symbology,
              source_updated_at
            )
            SELECT
              b.id,
              b.item_id,
              b.item_uom_id,
              b.barcode,
              b.active,
              b.is_primary,
              COALESCE(NULLIF(b.symbology, ''), 'CUSTOM'),
              COALESCE(b.updated_at, now())
            FROM item_barcodes b
            JOIN wms_pms_item_uom_projection u
              ON u.item_uom_id = b.item_uom_id
             AND u.item_id = b.item_id
            WHERE b.item_id = :item_id
            ORDER BY b.id ASC
            """
        ),
        {"item_id": item_id},
    )

    await session.flush()


async def force_wms_pms_projection_supplier_required_item(
    session: AsyncSession,
    *,
    item_id: int,
) -> None:
    """
    测试专用：把测试 item 提升为可创建 SUPPLIER lot 的策略，并同步 projection。
    """
    item_id = int(item_id)
    await session.execute(
        text(
            """
            UPDATE items
               SET lot_source_policy = 'SUPPLIER_ONLY'::lot_source_policy,
                   expiry_policy = 'REQUIRED'::expiry_policy,
                   derivation_allowed = TRUE,
                   uom_governance_enabled = TRUE,
                   updated_at = now()
             WHERE id = :item_id
            """
        ),
        {"item_id": item_id},
    )
    await sync_wms_pms_projection_for_item(session, item_id=item_id)
