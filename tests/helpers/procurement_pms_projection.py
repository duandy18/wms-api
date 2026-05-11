# tests/helpers/procurement_pms_projection.py
from __future__ import annotations

from importlib import import_module
import sys
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.pms_projection import seed_pms_projection_item_with_base_uom
from tests.helpers.pms_read_client_fake import projection_backed_pms_read_client_factory


PMS_CLIENT_MODULE_NAMES = (
    # procurement write/read paths
    "app.procurement.services.purchase_order_create",
    "app.procurement.services.purchase_order_update",
    "app.procurement.repos.purchase_order_create_repo",
    "app.procurement.repos.receive_po_line_repo",
    "app.procurement.helpers.purchase_reports",
    "app.procurement.routers.purchase_reports_routes_items",

    # WMS inbound / lot / stock paths reached by /wms/inbound/commit
    "app.wms.shared.services.expiry_resolver",
    "app.wms.shared.services.lot_code_contract",
    "app.wms.stock.services.lots",
    "app.wms.stock.services.stock_adjust.db_items",
    "app.wms.stock.repos.inventory_read_repo",
    "app.wms.stock.repos.inventory_explain_repo",
    "app.wms.inventory_adjustment.count.repos.count_doc_repo",
)


def install_procurement_pms_projection_fake(session: AsyncSession) -> None:
    """
    Test-only PMS client patch for procurement tests.

    Boundary:
    - tests only;
    - fake reads WMS PMS projection tables only;
    - runtime factory remains hard HTTP-only;
    - no fallback to legacy PMS owner tables.

    This helper must also patch WMS inbound/lot modules because purchase tests
    commit purchase inbound facts through /wms/inbound/commit.
    """
    factory = projection_backed_pms_read_client_factory(session)

    for module_name in PMS_CLIENT_MODULE_NAMES:
        module = import_module(module_name)
        if hasattr(module, "create_pms_read_client"):
            setattr(module, "create_pms_read_client", factory)

    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith(("app.procurement.", "app.wms.")):
            continue
        if hasattr(module, "create_pms_read_client"):
            setattr(module, "create_pms_read_client", factory)


async def _next_projection_id(
    session: AsyncSession,
    *,
    table_name: str,
    column_name: str,
    floor: int,
) -> int:
    if table_name not in {
        "wms_pms_item_projection",
        "wms_pms_uom_projection",
        "wms_pms_sku_code_projection",
        "wms_pms_barcode_projection",
    }:
        raise ValueError(f"unsupported projection table: {table_name}")

    if column_name not in {"item_id", "item_uom_id", "sku_code_id", "barcode_id"}:
        raise ValueError(f"unsupported projection column: {column_name}")

    row = await session.execute(
        text(
            f"""
            SELECT GREATEST(COALESCE(MAX({column_name}), 0), :floor) + 1
              FROM {table_name}
            """
        ),
        {"floor": int(floor)},
    )
    return int(row.scalar_one())


async def seed_purchase_projection_item(
    session: AsyncSession,
    *,
    supplier_id: int,
    sku_prefix: str,
    enabled: bool = True,
    expiry_policy: str = "NONE",
    lot_source_policy: str = "INTERNAL_ONLY",
) -> dict[str, Any]:
    install_procurement_pms_projection_fake(session)

    item_id = await _next_projection_id(
        session,
        table_name="wms_pms_item_projection",
        column_name="item_id",
        floor=500000,
    )
    item_uom_id = await _next_projection_id(
        session,
        table_name="wms_pms_uom_projection",
        column_name="item_uom_id",
        floor=500000,
    )
    sku_code_id = await _next_projection_id(
        session,
        table_name="wms_pms_sku_code_projection",
        column_name="sku_code_id",
        floor=500000,
    )
    barcode_id = await _next_projection_id(
        session,
        table_name="wms_pms_barcode_projection",
        column_name="barcode_id",
        floor=500000,
    )

    sku = f"{sku_prefix}-{uuid4().hex[:10]}".upper()
    name = f"UT-{sku}"

    seeded = await seed_pms_projection_item_with_base_uom(
        session,
        item_id=item_id,
        item_uom_id=item_uom_id,
        sku_code_id=sku_code_id,
        barcode_id=barcode_id,
        sku=sku,
        name=name,
        barcode=f"UT-BC-{item_id}",
        supplier_id=int(supplier_id),
        expiry_policy=str(expiry_policy).strip().upper(),
        lot_source_policy=str(lot_source_policy).strip().upper(),
        uom="PCS",
        display_name="PCS",
        sync_version="ut-procurement-pms-projection-seed",
    )

    await session.execute(
        text(
            """
            UPDATE wms_pms_item_projection
               SET enabled = :enabled
             WHERE item_id = :item_id
            """
        ),
        {
            "enabled": bool(enabled),
            "item_id": int(item_id),
        },
    )

    seeded["supplier_id"] = int(supplier_id)
    seeded["enabled"] = bool(enabled)
    return seeded


async def pick_purchase_uom_id(session: AsyncSession, *, item_id: int) -> int:
    row = await session.execute(
        text(
            """
            SELECT item_uom_id
              FROM wms_pms_uom_projection
             WHERE item_id = :item_id
             ORDER BY is_base DESC, item_uom_id ASC
             LIMIT 1
            """
        ),
        {"item_id": int(item_id)},
    )
    value = row.scalar_one_or_none()
    assert value is not None, {"msg": "item has no PMS projection uom", "item_id": int(item_id)}
    return int(value)


async def list_purchase_projection_items(
    session: AsyncSession,
    *,
    supplier_id: int | None = None,
    enabled: bool | None = None,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if supplier_id is not None:
        conditions.append("supplier_id = :supplier_id")
        params["supplier_id"] = int(supplier_id)

    if enabled is not None:
        conditions.append("enabled = :enabled")
        params["enabled"] = bool(enabled)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = (
        await session.execute(
            text(
                f"""
                SELECT
                  item_id AS id,
                  sku,
                  name,
                  enabled,
                  supplier_id
                FROM wms_pms_item_projection
                {where_sql}
                ORDER BY item_id ASC
                """
            ),
            params,
        )
    ).mappings().all()

    return [dict(row) for row in rows]


__all__ = [
    "install_procurement_pms_projection_fake",
    "list_purchase_projection_items",
    "pick_purchase_uom_id",
    "seed_purchase_projection_item",
]
