# app/oms/fsku/services/fsku_service_write.py
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.oms.fsku.contracts.fsku import FskuDetailOut
from app.oms.fsku.models.fsku import Fsku, FskuComponent
from app.oms.fsku.services.fsku_service_errors import FskuBadInput, FskuConflict, FskuNotFound
from app.oms.fsku.services.fsku_service_mapper import to_detail
from app.oms.fsku.services.fsku_service_utils import normalize_code, normalize_shape, utc_now
from app.integrations.pms.sync_client import SyncInProcessPmsReadClient


_SKU_TOKEN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,127}$")


@dataclass(frozen=True)
class ParsedComponent:
    component_sku_code: str
    qty_per_fsku: Decimal
    alloc_unit_price: Decimal
    sort_order: int


@dataclass(frozen=True)
class ParsedExpression:
    normalized_expr: str
    expr_type: str
    components: list[ParsedComponent]


@dataclass(frozen=True)
class ResolvedComponent:
    parsed: ParsedComponent
    resolved_item_id: int
    resolved_item_sku_code_id: int
    resolved_item_uom_id: int
    sku_code_snapshot: str
    item_name_snapshot: str
    uom_snapshot: str


def _norm_expr_text(v: object) -> str:
    s = str(v or "").strip().upper()
    s = s.replace("×", "*").replace("＋", "+")
    s = re.sub(r"\s+", "", s)
    if not s:
        raise ValueError("fsku_expr 不能为空")
    return s


def _dec(v: str, *, path: str) -> Decimal:
    try:
        d = Decimal(v)
    except InvalidOperation as e:
        raise ValueError(f"{path} 不是合法数字") from e
    if d <= 0:
        raise ValueError(f"{path} 必须大于 0")
    return d


def _format_decimal(d: Decimal) -> str:
    if d == d.to_integral_value():
        return str(int(d))
    s = format(d.normalize(), "f")
    return s.rstrip("0").rstrip(".")


def _parse_piece(piece: str, *, prefix: str, suffix: str, sort_order: int) -> ParsedComponent:
    parts = piece.split("*")
    if len(parts) > 3:
        raise ValueError(f"组件表达式不合法：{piece}")

    token = parts[0].strip()
    if not token:
        raise ValueError("组件 SKU 不能为空")

    qty = _dec(parts[1], path=f"{token}.qty") if len(parts) >= 2 and parts[1] else Decimal("1")
    alloc_price = _dec(parts[2], path=f"{token}.alloc_unit_price") if len(parts) >= 3 and parts[2] else Decimal("1")

    sku = f"{prefix}{token}{suffix}"
    if not _SKU_TOKEN.fullmatch(sku):
        raise ValueError(f"展开后的 SKU 编码不合法：{sku}")

    return ParsedComponent(
        component_sku_code=sku,
        qty_per_fsku=qty,
        alloc_unit_price=alloc_price,
        sort_order=sort_order,
    )


def parse_fsku_expr(expr: object) -> ParsedExpression:
    raw = _norm_expr_text(expr)

    if raw.count("{") != raw.count("}") or raw.count("{") > 1:
        raise ValueError("段级压缩表达式只允许一个花括号组")

    prefix = ""
    suffix = ""
    body = raw
    expr_type = "DIRECT"

    if "{" in raw:
        expr_type = "SEGMENT_GROUP"
        left, rest = raw.split("{", 1)
        inside, right = rest.split("}", 1)
        prefix = left
        suffix = right
        body = inside
        if not prefix or not suffix:
            raise ValueError("段级压缩表达式必须包含公共前缀和公共后缀")

    pieces = [x for x in body.split("+") if x]
    if not pieces:
        raise ValueError("FSKU 表达式没有任何组件")
    if len(pieces) > 10:
        raise ValueError("一个 FSKU 最多允许 10 个组件")

    components: list[ParsedComponent] = []
    seen: set[str] = set()
    for idx, piece in enumerate(pieces, start=1):
        parsed = _parse_piece(piece, prefix=prefix, suffix=suffix, sort_order=idx)
        if parsed.component_sku_code in seen:
            raise ValueError(f"重复组件 SKU：{parsed.component_sku_code}")
        seen.add(parsed.component_sku_code)
        components.append(parsed)

    normalized_parts = [
        f"{c.component_sku_code}*{_format_decimal(c.qty_per_fsku)}*{_format_decimal(c.alloc_unit_price)}"
        for c in components
    ]
    normalized_expr = "+".join(normalized_parts)

    return ParsedExpression(
        normalized_expr=normalized_expr,
        expr_type=expr_type,
        components=components,
    )


def _resolve_component(db: Session, parsed: ParsedComponent) -> ResolvedComponent:
    resolved = SyncInProcessPmsReadClient(
        db
    ).resolve_active_code_for_outbound_default(
        code=parsed.component_sku_code,
        enabled_only=True,
    )

    if resolved is None:
        raise ValueError(f"组件 SKU 未命中启用商品编码或缺少出库/基础包装：{parsed.component_sku_code}")

    return ResolvedComponent(
        parsed=parsed,
        resolved_item_id=int(resolved.item_id),
        resolved_item_sku_code_id=int(resolved.sku_code_id),
        resolved_item_uom_id=int(resolved.item_uom_id),
        sku_code_snapshot=str(resolved.sku_code),
        item_name_snapshot=str(resolved.item_name),
        uom_snapshot=str(resolved.uom_name),
    )



def _parse_and_resolve(db: Session, *, fsku_expr: object) -> tuple[ParsedExpression, list[ResolvedComponent]]:
    parsed = parse_fsku_expr(fsku_expr)
    resolved = [_resolve_component(db, c) for c in parsed.components]
    return parsed, resolved


def _load_components(db: Session, fsku_id: int) -> list[FskuComponent]:
    return (
        db.scalars(
            select(FskuComponent)
            .where(FskuComponent.fsku_id == int(fsku_id))
            .order_by(FskuComponent.sort_order.asc(), FskuComponent.id.asc())
        )
        .all()
    )


def _is_bound_by_merchant_codes(db: Session, fsku_id: int) -> bool:
    row = db.execute(
        text("SELECT 1 FROM platform_code_fsku_mappings WHERE fsku_id = :id LIMIT 1"),
        {"id": int(fsku_id)},
    ).first()
    return row is not None


def _replace_components_in_tx(db: Session, *, fsku: Fsku, resolved: list[ResolvedComponent]) -> None:
    now = utc_now()
    db.execute(delete(FskuComponent).where(FskuComponent.fsku_id == int(fsku.id)))

    for item in resolved:
        c = item.parsed
        db.add(
            FskuComponent(
                fsku_id=int(fsku.id),
                component_sku_code=c.component_sku_code,
                qty_per_fsku=c.qty_per_fsku,
                alloc_unit_price=c.alloc_unit_price,
                resolved_item_id=item.resolved_item_id,
                resolved_item_sku_code_id=item.resolved_item_sku_code_id,
                resolved_item_uom_id=item.resolved_item_uom_id,
                sku_code_snapshot=item.sku_code_snapshot,
                item_name_snapshot=item.item_name_snapshot,
                uom_snapshot=item.uom_snapshot,
                sort_order=c.sort_order,
                created_at=now,
                updated_at=now,
            )
        )


def create_draft(db: Session, *, name: str, code: str | None, shape: str | None, fsku_expr: str) -> FskuDetailOut:
    now = utc_now()
    shp = normalize_shape(shape)
    parsed, resolved = _parse_and_resolve(db, fsku_expr=fsku_expr)

    obj = Fsku(
        name=name.strip(),
        code="__PENDING__",
        shape=shp,
        status="draft",
        fsku_expr=str(fsku_expr).strip(),
        normalized_expr=parsed.normalized_expr,
        expr_type=parsed.expr_type,
        component_count=len(resolved),
        created_at=now,
        updated_at=now,
    )
    db.add(obj)
    db.flush()

    cd = normalize_code(code)
    obj.code = cd or (parsed.normalized_expr if len(parsed.normalized_expr) <= 128 else f"FSKU-{obj.id}")

    _replace_components_in_tx(db, fsku=obj, resolved=resolved)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise FskuConflict("FSKU code 或 normalized_expr 冲突（必须全局唯一）") from None

    db.refresh(obj)
    return to_detail(obj, _load_components(db, int(obj.id)))


def update_name(db: Session, *, fsku_id: int, name: str) -> FskuDetailOut:
    obj = db.get(Fsku, int(fsku_id))
    if obj is None:
        raise FskuNotFound("FSKU 不存在")
    if obj.status == "retired":
        raise FskuConflict("FSKU 已退休，名称不可修改")

    nm = name.strip()
    if not nm:
        raise FskuBadInput(details=[{"type": "validation", "path": "name", "reason": "name 不能为空"}])

    obj.name = nm
    obj.updated_at = utc_now()
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return to_detail(obj, _load_components(db, int(fsku_id)))


def replace_expression_draft(db: Session, *, fsku_id: int, fsku_expr: str) -> FskuDetailOut:
    obj = db.get(Fsku, int(fsku_id))
    if obj is None:
        raise FskuNotFound("FSKU 不存在")
    if obj.status != "draft":
        raise FskuConflict("FSKU 非草稿态，表达式已冻结；如需改动请新建 FSKU")

    parsed, resolved = _parse_and_resolve(db, fsku_expr=fsku_expr)

    obj.fsku_expr = fsku_expr.strip()
    obj.normalized_expr = parsed.normalized_expr
    obj.expr_type = parsed.expr_type
    obj.component_count = len(resolved)
    obj.updated_at = utc_now()

    _replace_components_in_tx(db, fsku=obj, resolved=resolved)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise FskuConflict("FSKU 表达式写入冲突，请检查是否重复") from None

    db.refresh(obj)
    return to_detail(obj, _load_components(db, int(fsku_id)))


def publish(db: Session, fsku_id: int) -> FskuDetailOut:
    obj = db.get(Fsku, int(fsku_id))
    if obj is None:
        raise FskuNotFound("FSKU 不存在")
    if obj.status != "draft":
        raise FskuConflict("仅草稿态允许发布")

    total = int(db.scalar(select(func.count()).select_from(FskuComponent).where(FskuComponent.fsku_id == int(fsku_id))) or 0)
    if total <= 0:
        raise FskuConflict("发布前必须至少有 1 个表达式组件")

    now = utc_now()
    obj.status = "published"
    obj.published_at = now
    obj.updated_at = now
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return to_detail(obj, _load_components(db, int(fsku_id)))


def retire(db: Session, fsku_id: int) -> FskuDetailOut:
    obj = db.get(Fsku, int(fsku_id))
    if obj is None:
        raise FskuNotFound("FSKU 不存在")
    if obj.status != "published":
        raise FskuConflict("仅已发布的 FSKU 允许停用")
    if _is_bound_by_merchant_codes(db, int(fsku_id)):
        raise FskuConflict("该 FSKU 正在被店铺商品代码引用（存在映射），请先改绑/解绑后再退休")

    now = utc_now()
    obj.status = "retired"
    obj.retired_at = now
    obj.updated_at = now
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return to_detail(obj, _load_components(db, int(fsku_id)))


def unretire(db: Session, fsku_id: int) -> FskuDetailOut:
    _ = fsku_id
    raise FskuConflict("系统不支持取消归档：FSKU 生命周期单向（draft → published → retired）")
