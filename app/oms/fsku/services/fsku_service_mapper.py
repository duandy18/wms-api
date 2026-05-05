# app/oms/fsku/services/fsku_service_mapper.py
from __future__ import annotations

from app.oms.fsku.contracts.fsku import FskuComponentOut, FskuDetailOut
from app.oms.fsku.models.fsku import Fsku, FskuComponent


def to_detail(f: Fsku, components: list[FskuComponent]) -> FskuDetailOut:
    out_components = [
        FskuComponentOut(
            component_sku_code=str(c.component_sku_code),
            qty_per_fsku=c.qty_per_fsku,
            alloc_unit_price=c.alloc_unit_price,
            resolved_item_id=int(c.resolved_item_id),
            resolved_item_sku_code_id=int(c.resolved_item_sku_code_id),
            resolved_item_uom_id=int(c.resolved_item_uom_id),
            sku_code_snapshot=str(c.sku_code_snapshot),
            item_name_snapshot=str(c.item_name_snapshot),
            uom_snapshot=str(c.uom_snapshot),
            sort_order=int(c.sort_order),
        )
        for c in sorted(components, key=lambda x: int(x.sort_order))
    ]

    return FskuDetailOut(
        id=int(f.id),
        code=str(f.code),
        name=str(f.name),
        shape=str(f.shape),
        status=str(f.status),
        fsku_expr=str(f.fsku_expr),
        normalized_expr=str(f.normalized_expr),
        expr_type=str(f.expr_type),
        component_count=int(f.component_count),
        published_at=f.published_at,
        retired_at=f.retired_at,
        created_at=f.created_at,
        updated_at=f.updated_at,
        components=out_components,
    )
