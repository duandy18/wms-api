# tests/helpers/pms_projection.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


async def seed_pms_item_projection(
    session: AsyncSession,
    *,
    item_id: int,
    sku: str | None = None,
    name: str | None = None,
    spec: str | None = None,
    enabled: bool = True,
    supplier_id: int | None = None,
    brand: str | None = None,
    category: str | None = None,
    expiry_policy: str = "NONE",
    shelf_life_value: int | None = None,
    shelf_life_unit: str | None = None,
    lot_source_policy: str = "INTERNAL_ONLY",
    derivation_allowed: bool = True,
    uom_governance_enabled: bool = False,
    sync_version: str = "ut-pms-projection-seed",
) -> None:
    item_id = int(item_id)
    sku_value = str(sku or f"SKU-{item_id}").strip()
    name_value = str(name or f"ITEM-{item_id}").strip()

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
                :item_id,
                :sku,
                :name,
                :spec,
                :enabled,
                :supplier_id,
                :brand,
                :category,
                :expiry_policy,
                :shelf_life_value,
                :shelf_life_unit,
                :lot_source_policy,
                :derivation_allowed,
                :uom_governance_enabled,
                :pms_updated_at,
                :source_hash,
                :sync_version,
                now()
            )
            ON CONFLICT (item_id) DO UPDATE SET
                sku = EXCLUDED.sku,
                name = EXCLUDED.name,
                spec = EXCLUDED.spec,
                enabled = EXCLUDED.enabled,
                supplier_id = EXCLUDED.supplier_id,
                brand = EXCLUDED.brand,
                category = EXCLUDED.category,
                expiry_policy = EXCLUDED.expiry_policy,
                shelf_life_value = EXCLUDED.shelf_life_value,
                shelf_life_unit = EXCLUDED.shelf_life_unit,
                lot_source_policy = EXCLUDED.lot_source_policy,
                derivation_allowed = EXCLUDED.derivation_allowed,
                uom_governance_enabled = EXCLUDED.uom_governance_enabled,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        ),
        {
            "item_id": item_id,
            "sku": sku_value,
            "name": name_value,
            "spec": spec,
            "enabled": bool(enabled),
            "supplier_id": int(supplier_id) if supplier_id is not None else None,
            "brand": brand,
            "category": category,
            "expiry_policy": str(expiry_policy).strip().upper(),
            "shelf_life_value": int(shelf_life_value) if shelf_life_value is not None else None,
            "shelf_life_unit": str(shelf_life_unit).strip().upper() if shelf_life_unit is not None else None,
            "lot_source_policy": str(lot_source_policy).strip().upper(),
            "derivation_allowed": bool(derivation_allowed),
            "uom_governance_enabled": bool(uom_governance_enabled),
            "pms_updated_at": _now(),
            "source_hash": f"{sync_version}:item:{item_id}:{sku_value}",
            "sync_version": sync_version,
        },
    )


async def seed_pms_uom_projection(
    session: AsyncSession,
    *,
    item_uom_id: int,
    item_id: int,
    uom: str = "PCS",
    display_name: str | None = "PCS",
    uom_name: str | None = None,
    ratio_to_base: int = 1,
    net_weight_kg: Decimal | str | float | None = None,
    is_base: bool = True,
    is_purchase_default: bool = True,
    is_inbound_default: bool = True,
    is_outbound_default: bool = True,
    sync_version: str = "ut-pms-projection-seed",
) -> None:
    item_uom_id = int(item_uom_id)
    item_id = int(item_id)
    uom_value = str(uom).strip()
    display_value = str(display_name).strip() if display_name is not None else None
    uom_name_value = str(uom_name or display_value or uom_value).strip()

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
            VALUES (
                :item_uom_id,
                :item_id,
                :uom,
                :display_name,
                :uom_name,
                :ratio_to_base,
                :net_weight_kg,
                :is_base,
                :is_purchase_default,
                :is_inbound_default,
                :is_outbound_default,
                :pms_updated_at,
                :source_hash,
                :sync_version,
                now()
            )
            ON CONFLICT (item_uom_id) DO UPDATE SET
                item_id = EXCLUDED.item_id,
                uom = EXCLUDED.uom,
                display_name = EXCLUDED.display_name,
                uom_name = EXCLUDED.uom_name,
                ratio_to_base = EXCLUDED.ratio_to_base,
                net_weight_kg = EXCLUDED.net_weight_kg,
                is_base = EXCLUDED.is_base,
                is_purchase_default = EXCLUDED.is_purchase_default,
                is_inbound_default = EXCLUDED.is_inbound_default,
                is_outbound_default = EXCLUDED.is_outbound_default,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        ),
        {
            "item_uom_id": item_uom_id,
            "item_id": item_id,
            "uom": uom_value,
            "display_name": display_value,
            "uom_name": uom_name_value,
            "ratio_to_base": int(ratio_to_base),
            "net_weight_kg": (
                Decimal(str(net_weight_kg)) if net_weight_kg is not None else None
            ),
            "is_base": bool(is_base),
            "is_purchase_default": bool(is_purchase_default),
            "is_inbound_default": bool(is_inbound_default),
            "is_outbound_default": bool(is_outbound_default),
            "pms_updated_at": _now(),
            "source_hash": f"{sync_version}:uom:{item_uom_id}:{item_id}:{uom_value}",
            "sync_version": sync_version,
        },
    )


async def seed_pms_sku_code_projection(
    session: AsyncSession,
    *,
    sku_code_id: int,
    item_id: int,
    sku_code: str,
    code_type: str = "PRIMARY",
    is_primary: bool = True,
    is_active: bool = True,
    sync_version: str = "ut-pms-projection-seed",
) -> None:
    sku_code_id = int(sku_code_id)
    item_id = int(item_id)
    sku_code_value = str(sku_code).strip().upper()

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
            VALUES (
                :sku_code_id,
                :item_id,
                :sku_code,
                :code_type,
                :is_primary,
                :is_active,
                :effective_from,
                NULL,
                :pms_updated_at,
                :source_hash,
                :sync_version,
                now()
            )
            ON CONFLICT (sku_code_id) DO UPDATE SET
                item_id = EXCLUDED.item_id,
                sku_code = EXCLUDED.sku_code,
                code_type = EXCLUDED.code_type,
                is_primary = EXCLUDED.is_primary,
                is_active = EXCLUDED.is_active,
                effective_from = EXCLUDED.effective_from,
                effective_to = EXCLUDED.effective_to,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        ),
        {
            "sku_code_id": sku_code_id,
            "item_id": item_id,
            "sku_code": sku_code_value,
            "code_type": str(code_type).strip().upper(),
            "is_primary": bool(is_primary),
            "is_active": bool(is_active),
            "effective_from": _now(),
            "pms_updated_at": _now(),
            "source_hash": f"{sync_version}:sku-code:{sku_code_id}:{sku_code_value}",
            "sync_version": sync_version,
        },
    )


async def seed_pms_barcode_projection(
    session: AsyncSession,
    *,
    barcode_id: int,
    item_id: int,
    item_uom_id: int,
    barcode: str,
    symbology: str = "CUSTOM",
    active: bool = True,
    is_primary: bool = True,
    sync_version: str = "ut-pms-projection-seed",
) -> None:
    barcode_id = int(barcode_id)
    item_id = int(item_id)
    item_uom_id = int(item_uom_id)
    barcode_value = str(barcode).strip()

    await session.execute(
        text(
            """
            INSERT INTO wms_pms_barcode_projection (
                barcode_id,
                item_id,
                item_uom_id,
                barcode,
                symbology,
                active,
                is_primary,
                pms_updated_at,
                source_hash,
                sync_version,
                synced_at
            )
            VALUES (
                :barcode_id,
                :item_id,
                :item_uom_id,
                :barcode,
                :symbology,
                :active,
                :is_primary,
                :pms_updated_at,
                :source_hash,
                :sync_version,
                now()
            )
            ON CONFLICT (barcode_id) DO UPDATE SET
                item_id = EXCLUDED.item_id,
                item_uom_id = EXCLUDED.item_uom_id,
                barcode = EXCLUDED.barcode,
                symbology = EXCLUDED.symbology,
                active = EXCLUDED.active,
                is_primary = EXCLUDED.is_primary,
                pms_updated_at = EXCLUDED.pms_updated_at,
                source_hash = EXCLUDED.source_hash,
                sync_version = EXCLUDED.sync_version,
                synced_at = now()
            """
        ),
        {
            "barcode_id": barcode_id,
            "item_id": item_id,
            "item_uom_id": item_uom_id,
            "barcode": barcode_value,
            "symbology": str(symbology).strip().upper(),
            "active": bool(active),
            "is_primary": bool(is_primary),
            "pms_updated_at": _now(),
            "source_hash": f"{sync_version}:barcode:{barcode_id}:{barcode_value}",
            "sync_version": sync_version,
        },
    )


async def seed_pms_projection_item_with_base_uom(
    session: AsyncSession,
    *,
    item_id: int,
    item_uom_id: int | None = None,
    sku_code_id: int | None = None,
    barcode_id: int | None = None,
    sku: str | None = None,
    name: str | None = None,
    barcode: str | None = None,
    expiry_policy: str = "NONE",
    lot_source_policy: str | None = None,
    supplier_id: int | None = None,
    ratio_to_base: int = 1,
    uom: str = "PCS",
    display_name: str = "PCS",
    sync_version: str = "ut-pms-projection-seed",
) -> dict[str, Any]:
    item_id = int(item_id)
    item_uom_id = int(item_uom_id or item_id)
    sku_code_id = int(sku_code_id or item_id)
    sku_value = str(sku or f"SKU-{item_id}").strip().upper()
    name_value = str(name or f"ITEM-{item_id}").strip()
    expiry = str(expiry_policy).strip().upper()
    lot_source = (
        str(lot_source_policy).strip().upper()
        if lot_source_policy is not None
        else ("SUPPLIER_ONLY" if expiry == "REQUIRED" else "INTERNAL_ONLY")
    )

    await seed_pms_item_projection(
        session,
        item_id=item_id,
        sku=sku_value,
        name=name_value,
        supplier_id=supplier_id,
        expiry_policy=expiry,
        shelf_life_value=30 if expiry == "REQUIRED" else None,
        shelf_life_unit="DAY" if expiry == "REQUIRED" else None,
        lot_source_policy=lot_source,
        derivation_allowed=True,
        uom_governance_enabled=True,
        sync_version=sync_version,
    )
    await seed_pms_uom_projection(
        session,
        item_uom_id=item_uom_id,
        item_id=item_id,
        uom=uom,
        display_name=display_name,
        ratio_to_base=ratio_to_base,
        is_base=True,
        is_purchase_default=True,
        is_inbound_default=True,
        is_outbound_default=True,
        sync_version=sync_version,
    )
    await seed_pms_sku_code_projection(
        session,
        sku_code_id=sku_code_id,
        item_id=item_id,
        sku_code=sku_value,
        is_primary=True,
        is_active=True,
        sync_version=sync_version,
    )

    out: dict[str, Any] = {
        "item_id": item_id,
        "item_uom_id": item_uom_id,
        "sku_code_id": sku_code_id,
        "sku": sku_value,
        "name": name_value,
        "expiry_policy": expiry,
        "lot_source_policy": lot_source,
    }

    if barcode is not None:
        resolved_barcode_id = int(barcode_id or item_id)
        await seed_pms_barcode_projection(
            session,
            barcode_id=resolved_barcode_id,
            item_id=item_id,
            item_uom_id=item_uom_id,
            barcode=str(barcode),
            sync_version=sync_version,
        )
        out["barcode_id"] = resolved_barcode_id
        out["barcode"] = str(barcode)

    return out


__all__ = [
    "seed_pms_barcode_projection",
    "seed_pms_item_projection",
    "seed_pms_projection_item_with_base_uom",
    "seed_pms_sku_code_projection",
    "seed_pms_uom_projection",
]
