# tests/services/test_pms_projection_reconciliation.py
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.projection_reconciliation import (
    ItemReference,
    SkuCodeReference,
    UomReference,
    reconcile_pms_projection_references,
)

pytestmark = pytest.mark.asyncio


async def _seed_projection(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            INSERT INTO wms_pms_item_projection (
                item_id,
                sku,
                name,
                spec,
                enabled,
                supplier_id,
                brand,
                category,
                expiry_policy,
                shelf_life_value,
                shelf_life_unit,
                lot_source_policy,
                derivation_allowed,
                uom_governance_enabled,
                pms_updated_at,
                source_hash,
                sync_version,
                synced_at
            )
            VALUES (
                980001,
                'UT-RECON-ITEM-980001',
                '对账商品980001',
                NULL,
                TRUE,
                NULL,
                NULL,
                NULL,
                'NONE',
                NULL,
                NULL,
                'INTERNAL_ONLY',
                TRUE,
                FALSE,
                now(),
                'ut-recon-item-980001',
                'ut-recon-projection',
                now()
            )
            ON CONFLICT (item_id) DO UPDATE SET
                sku = EXCLUDED.sku,
                name = EXCLUDED.name,
                enabled = EXCLUDED.enabled,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        )
    )

    await session.execute(
        text(
            """
            INSERT INTO wms_pms_uom_projection (
                item_uom_id,
                item_id,
                uom,
                display_name,
                uom_name,
                ratio_to_base,
                net_weight_kg,
                is_base,
                is_purchase_default,
                is_inbound_default,
                is_outbound_default,
                pms_updated_at,
                source_hash,
                sync_version,
                synced_at
            )
            VALUES
              (
                980011,
                980001,
                'PCS',
                '件',
                '件',
                1,
                NULL,
                TRUE,
                TRUE,
                TRUE,
                TRUE,
                now(),
                'ut-recon-uom-980011',
                'ut-recon-projection',
                now()
              ),
              (
                980012,
                980002,
                'BOX',
                '箱',
                '箱',
                10,
                NULL,
                FALSE,
                FALSE,
                FALSE,
                FALSE,
                now(),
                'ut-recon-uom-980012',
                'ut-recon-projection',
                now()
              )
            ON CONFLICT (item_uom_id) DO UPDATE SET
                item_id = EXCLUDED.item_id,
                uom = EXCLUDED.uom,
                display_name = EXCLUDED.display_name,
                uom_name = EXCLUDED.uom_name,
                ratio_to_base = EXCLUDED.ratio_to_base,
                is_base = EXCLUDED.is_base,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        )
    )

    await session.execute(
        text(
            """
            INSERT INTO wms_pms_sku_code_projection (
                sku_code_id,
                item_id,
                sku_code,
                code_type,
                is_primary,
                is_active,
                effective_from,
                effective_to,
                pms_updated_at,
                source_hash,
                sync_version,
                synced_at
            )
            VALUES
              (
                980021,
                980001,
                'UT-RECON-ITEM-980001',
                'PRIMARY',
                TRUE,
                TRUE,
                now(),
                NULL,
                now(),
                'ut-recon-sku-980021',
                'ut-recon-projection',
                now()
              ),
              (
                980022,
                980002,
                'UT-RECON-ITEM-980002',
                'PRIMARY',
                TRUE,
                TRUE,
                now(),
                NULL,
                now(),
                'ut-recon-sku-980022',
                'ut-recon-projection',
                now()
              )
            ON CONFLICT (sku_code_id) DO UPDATE SET
                item_id = EXCLUDED.item_id,
                sku_code = EXCLUDED.sku_code,
                code_type = EXCLUDED.code_type,
                is_primary = EXCLUDED.is_primary,
                is_active = EXCLUDED.is_active,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        )
    )


async def _seed_temp_refs(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            CREATE TEMP TABLE tmp_pms_reconcile_item_refs (
                id INTEGER NOT NULL,
                item_id INTEGER
            ) ON COMMIT DROP
            """
        )
    )
    await session.execute(
        text(
            """
            CREATE TEMP TABLE tmp_pms_reconcile_uom_refs (
                id INTEGER NOT NULL,
                item_id INTEGER,
                item_uom_id INTEGER
            ) ON COMMIT DROP
            """
        )
    )
    await session.execute(
        text(
            """
            CREATE TEMP TABLE tmp_pms_reconcile_sku_refs (
                id INTEGER NOT NULL,
                item_id INTEGER,
                sku_code_id INTEGER
            ) ON COMMIT DROP
            """
        )
    )

    await session.execute(
        text(
            """
            INSERT INTO tmp_pms_reconcile_item_refs (id, item_id)
            VALUES
              (1, 980001),
              (2, 980099)
            """
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO tmp_pms_reconcile_uom_refs (id, item_id, item_uom_id)
            VALUES
              (1, 980001, 980011),
              (2, 980001, 980099),
              (3, 980001, 980012)
            """
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO tmp_pms_reconcile_sku_refs (id, item_id, sku_code_id)
            VALUES
              (1, 980001, 980021),
              (2, 980001, 980099),
              (3, 980001, 980022)
            """
        )
    )


async def test_pms_projection_reconciliation_reports_missing_and_mismatch(
    session: AsyncSession,
) -> None:
    await _seed_projection(session)
    await _seed_temp_refs(session)

    result = await reconcile_pms_projection_references(
        session,
        item_references=(
            ItemReference("pg_temp.tmp_pms_reconcile_item_refs", "id", "item_id"),
        ),
        uom_references=(
            UomReference(
                "pg_temp.tmp_pms_reconcile_uom_refs",
                "id",
                "item_id",
                "item_uom_id",
            ),
        ),
        sku_code_references=(
            SkuCodeReference(
                "pg_temp.tmp_pms_reconcile_sku_refs",
                "id",
                "item_id",
                "sku_code_id",
            ),
        ),
        supplier_references=(),
    )

    assert result.ok is False
    assert result.issue_count == 5
    assert result.summary_by_type() == {
        "ITEM_MISSING_IN_PROJECTION": 1,
        "SKU_CODE_ITEM_MISMATCH": 1,
        "SKU_CODE_MISSING_IN_PROJECTION": 1,
        "UOM_ITEM_MISMATCH": 1,
        "UOM_MISSING_IN_PROJECTION": 1,
    }

    payload = result.to_dict()
    assert payload["ok"] is False
    assert payload["issue_count"] == 5


async def test_pms_projection_reconciliation_returns_ok_for_clean_refs(
    session: AsyncSession,
) -> None:
    await _seed_projection(session)

    await session.execute(
        text(
            """
            CREATE TEMP TABLE tmp_pms_reconcile_clean_refs (
                id INTEGER NOT NULL,
                item_id INTEGER,
                item_uom_id INTEGER,
                sku_code_id INTEGER
            ) ON COMMIT DROP
            """
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO tmp_pms_reconcile_clean_refs (
                id,
                item_id,
                item_uom_id,
                sku_code_id
            )
            VALUES (1, 980001, 980011, 980021)
            """
        )
    )

    result = await reconcile_pms_projection_references(
        session,
        item_references=(
            ItemReference("pg_temp.tmp_pms_reconcile_clean_refs", "id", "item_id"),
        ),
        uom_references=(
            UomReference(
                "pg_temp.tmp_pms_reconcile_clean_refs",
                "id",
                "item_id",
                "item_uom_id",
            ),
        ),
        sku_code_references=(
            SkuCodeReference(
                "pg_temp.tmp_pms_reconcile_clean_refs",
                "id",
                "item_id",
                "sku_code_id",
            ),
        ),
        supplier_references=(),
    )

    assert result.ok is True
    assert result.issue_count == 0
    assert result.summary_by_type() == {}

async def test_pms_projection_reconciliation_supports_reference_table_without_id_column(
    session: AsyncSession,
) -> None:
    await _seed_projection(session)

    await session.execute(
        text(
            """
            CREATE TEMP TABLE tmp_pms_reconcile_no_id_refs (
                item_id INTEGER
            ) ON COMMIT DROP
            """
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO tmp_pms_reconcile_no_id_refs (item_id)
            VALUES (980099)
            """
        )
    )

    result = await reconcile_pms_projection_references(
        session,
        item_references=(
            ItemReference("pg_temp.tmp_pms_reconcile_no_id_refs", None, "item_id"),
        ),
        uom_references=(),
        sku_code_references=(),
        supplier_references=(),
    )

    assert result.ok is False
    assert result.issue_count == 1
    issue = result.issues[0]
    assert issue.issue_type == "ITEM_MISSING_IN_PROJECTION"
    assert issue.source_table == "pg_temp.tmp_pms_reconcile_no_id_refs"
    assert issue.source_id
