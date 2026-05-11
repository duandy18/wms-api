# tests/utils/ensure_minimal.py
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.wms.inventory_adjustment.count.repos.count_doc_repo as count_doc_repo_module
import app.wms.shared.services.expiry_resolver as expiry_resolver_module
import app.wms.shared.services.lot_code_contract as lot_code_contract_module
import app.wms.stock.repos.inventory_explain_repo as inventory_explain_repo_module
import app.wms.stock.repos.inventory_read_repo as inventory_read_repo_module
import app.wms.stock.services.lots as lots_module
import app.wms.stock.services.stock_adjust.db_items as db_items_module
from app.wms.stock.services.lot_service import ensure_internal_lot_singleton as ensure_internal_lot_singleton_svc
from app.wms.stock.services.lot_service import ensure_lot_full as ensure_lot_full_svc
from app.wms.stock.services.stock_adjust import adjust_lot_impl
from tests.helpers.pms_projection import seed_pms_projection_item_with_base_uom
from tests.helpers.pms_read_client_fake import projection_backed_pms_read_client_factory

UTC = timezone.utc


def _as_lot_id(v: object) -> int:
    """
    lot_service 的 ensure_* 可能返回 int(lot_id) 或 ORM 对象（带 .id）。
    tests 侧用这个函数统一兼容，避免类型漂移导致的 AttributeError。
    """
    return int(getattr(v, "id", v))


def _stable_required_dates_from_code(code_raw: str, *, days: int) -> tuple[date, date]:
    """
    REQUIRED lot helper：按 lot_code 稳定生成日期，避免不同批次都撞到同一天 production_date。
    """
    code = str(code_raw).strip()
    if not code:
        raise ValueError("lot_code empty")

    digest = hashlib.sha1(code.encode("utf-8")).hexdigest()
    offset_days = int(digest[:8], 16) % 73000  # ~200 years range
    production_date = date(2000, 1, 1) + timedelta(days=offset_days)
    expiry_date = production_date + timedelta(days=int(days))
    return production_date, expiry_date


def _install_projection_pms_client(session: AsyncSession) -> None:
    """
    Test-only PMS client patch for ensure_minimal helpers.

    Boundary:
    - tests only;
    - fake reads WMS PMS projection tables only;
    - does not alter app.integrations.pms.factory;
    - does not reintroduce in-process PMS owner reads;
    - keeps runtime hard HTTP-only.
    """
    factory = projection_backed_pms_read_client_factory(session)

    lots_module.create_pms_read_client = factory
    db_items_module.create_pms_read_client = factory
    expiry_resolver_module.create_pms_read_client = factory
    lot_code_contract_module.create_pms_read_client = factory
    count_doc_repo_module.create_pms_read_client = factory
    inventory_read_repo_module.create_pms_read_client = factory
    inventory_explain_repo_module.create_pms_read_client = factory


async def _current_projection_expiry_policy(
    session: AsyncSession,
    *,
    item_id: int,
) -> str | None:
    row = await session.execute(
        text(
            """
            SELECT expiry_policy
              FROM wms_pms_item_projection
             WHERE item_id = :item_id
             LIMIT 1
            """
        ),
        {"item_id": int(item_id)},
    )
    value = row.scalar_one_or_none()
    return str(value).upper() if value is not None else None


async def _projection_uom_id_for_seed(
    session: AsyncSession,
    *,
    item_id: int,
    uom: str,
    fallback_id: int,
) -> int:
    row = await session.execute(
        text(
            """
            SELECT item_uom_id
              FROM wms_pms_uom_projection
             WHERE item_id = :item_id
               AND uom = :uom
             ORDER BY is_base DESC, item_uom_id ASC
             LIMIT 1
            """
        ),
        {
            "item_id": int(item_id),
            "uom": str(uom),
        },
    )
    value = row.scalar_one_or_none()
    return int(value) if value is not None else int(fallback_id)


async def _projection_sku_code_id_for_seed(
    session: AsyncSession,
    *,
    item_id: int,
    sku_code: str,
    fallback_id: int,
) -> int:
    row = await session.execute(
        text(
            """
            SELECT sku_code_id
              FROM wms_pms_sku_code_projection
             WHERE item_id = :item_id
               AND sku_code = :sku_code
             ORDER BY is_primary DESC, sku_code_id ASC
             LIMIT 1
            """
        ),
        {
            "item_id": int(item_id),
            "sku_code": str(sku_code).strip().upper(),
        },
    )
    value = row.scalar_one_or_none()
    return int(value) if value is not None else int(fallback_id)


# ---------- warehouses ----------
async def ensure_warehouse(session: AsyncSession, *, id: int, name: Optional[str] = None) -> None:
    name = name or f"WH-{id}"
    await session.execute(
        text(
            """
            INSERT INTO warehouses (id, name)
            VALUES (:id, :name)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": int(id), "name": str(name)},
    )


# ---------- items ----------
async def ensure_item(
    session: AsyncSession,
    *,
    id: int,
    sku: Optional[str] = None,
    name: Optional[str] = None,
    uom: Optional[str] = None,
    expiry_required: bool = False,
) -> None:
    """
    PMS 已拆库后，tests 侧不再写旧 items / item_sku_codes。

    当前终态：
    - PMS owner 真相在 pms-api / pms DB；
    - WMS 测试造数只写 wms_pms_*_projection；
    - runtime PMS client 仍保持 HTTP-only；
    - 单元/服务测试通过 projection-backed fake PMS client 读取 projection。

    参数 uom：历史兼容参数，保留以避免旧测试调用报错。
    """
    _ = uom

    _install_projection_pms_client(session)

    item_id = int(id)
    sku_value = str(sku or f"SKU-{item_id}").strip()
    name_value = str(name or f"ITEM-{item_id}").strip()

    existing_policy = await _current_projection_expiry_policy(session, item_id=item_id)
    final_expiry_policy = (
        "REQUIRED"
        if bool(expiry_required) or existing_policy == "REQUIRED"
        else "NONE"
    )
    final_lot_source_policy = (
        "SUPPLIER_ONLY" if final_expiry_policy == "REQUIRED" else "INTERNAL_ONLY"
    )

    item_uom_id = await _projection_uom_id_for_seed(
        session,
        item_id=item_id,
        uom="PCS",
        fallback_id=item_id,
    )
    sku_code_id = await _projection_sku_code_id_for_seed(
        session,
        item_id=item_id,
        sku_code=sku_value,
        fallback_id=item_id,
    )

    await seed_pms_projection_item_with_base_uom(
        session,
        item_id=item_id,
        item_uom_id=item_uom_id,
        sku_code_id=sku_code_id,
        sku=sku_value,
        name=name_value,
        expiry_policy=final_expiry_policy,
        lot_source_policy=final_lot_source_policy,
    )


def _norm_lot_key(code_raw: str) -> str:
    # tests baseline normalize: trim + lower
    return str(code_raw).strip().lower()


async def _load_item_expiry_policy(session: AsyncSession, *, item_id: int) -> str:
    value = await _current_projection_expiry_policy(session, item_id=int(item_id))
    if value is None:
        raise ValueError(f"item_not_found: {item_id}")
    return str(value)


# ---------- lots / stocks_lot ----------
async def ensure_supplier_lot(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
    lot_code: str,
) -> int:
    """
    Phase M-5：创建/获取一个最小合法 SUPPLIER lot，并返回 lot_id。

    ✅ 工程收口：
    - PMS current-state seed 写 wms_pms_*_projection；
    - lot 创建仍走 app.wms.stock.services.lot_service.ensure_lot_full；
    - 禁止 tests 直接 INSERT INTO lots；
    - 禁止 tests 写旧 PMS owner 表。
    """
    code_raw = str(lot_code).strip()
    if not code_raw:
        raise ValueError("lot_code empty")

    _install_projection_pms_client(session)

    await ensure_item(
        session,
        id=int(item_id),
        sku=f"SKU-{item_id}",
        name=f"ITEM-{item_id}",
        expiry_required=True,
    )

    expiry_policy = await _load_item_expiry_policy(session, item_id=int(item_id))
    if expiry_policy != "REQUIRED":
        raise RuntimeError(
            f"ensure_supplier_lot expected REQUIRED expiry_policy, got: {expiry_policy}"
        )

    production_date, expiry_date = _stable_required_dates_from_code(code_raw, days=365)

    got = await ensure_lot_full_svc(
        session,
        warehouse_id=int(warehouse_id),
        item_id=int(item_id),
        lot_code=code_raw,
        production_date=production_date,
        expiry_date=expiry_date,
    )
    return _as_lot_id(got)


async def ensure_internal_lot_singleton(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
) -> int:
    _install_projection_pms_client(session)

    await ensure_item(
        session,
        id=int(item_id),
        sku=f"SKU-{item_id}",
        name=f"ITEM-{item_id}",
        expiry_required=False,
    )

    got = await ensure_internal_lot_singleton_svc(
        session,
        warehouse_id=int(warehouse_id),
        item_id=int(item_id),
    )
    return _as_lot_id(got)


async def _get_stock_qty(session: AsyncSession, *, item_id: int, warehouse_id: int, lot_id: int) -> int:
    r = await session.execute(
        text(
            """
            SELECT qty
              FROM stocks_lot
             WHERE item_id = :i
               AND warehouse_id = :w
               AND lot_id = :lot
             LIMIT 1
            """
        ),
        {"i": int(item_id), "w": int(warehouse_id), "lot": int(lot_id)},
    )
    v = r.scalar_one_or_none()
    return int(v) if v is not None else 0


async def ensure_stock_slot(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
    lot_code: str | None,
) -> None:
    """
    Phase 4D+：创建 stocks_lot 槽位（测试工具）。

    ✅ 工程收口：禁止 tests 里直接 INSERT INTO stocks_lot
    -> 统一走 adjust_lot_impl（writer 自己 ensure 槽位）
    """
    await set_stock_qty(
        session,
        item_id=int(item_id),
        warehouse_id=int(warehouse_id),
        lot_code=lot_code,
        qty=0,
    )


async def set_stock_qty(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
    lot_code: str | None,
    qty: int,
) -> None:
    """
    Phase 4D+：把 stocks_lot 槽位的 qty 设置为特定值（幂等重置，用于测试）。

    ✅ 工程收口：
    - PMS current-state seed 写 wms_pms_*_projection；
    - 禁止 tests 里 UPDATE stocks_lot / INSERT stocks_lot；
    - 读当前 qty -> 计算 delta -> 走 adjust_lot_impl 写入（ledger + balance 一致）。
    """
    _install_projection_pms_client(session)

    if lot_code is None:
        bc_norm: Optional[str] = None
        await ensure_item(
            session,
            id=int(item_id),
            sku=f"SKU-{item_id}",
            name=f"ITEM-{item_id}",
            expiry_required=False,
        )
        lot_id = await ensure_internal_lot_singleton(
            session,
            item_id=int(item_id),
            warehouse_id=int(warehouse_id),
        )
    else:
        bc_norm = str(lot_code).strip() or None
        if bc_norm is None:
            await ensure_item(
                session,
                id=int(item_id),
                sku=f"SKU-{item_id}",
                name=f"ITEM-{item_id}",
                expiry_required=False,
            )
            lot_id = await ensure_internal_lot_singleton(
                session,
                item_id=int(item_id),
                warehouse_id=int(warehouse_id),
            )
        else:
            lot_id = await ensure_supplier_lot(
                session,
                item_id=int(item_id),
                warehouse_id=int(warehouse_id),
                lot_code=bc_norm,
            )

    cur = await _get_stock_qty(
        session,
        item_id=int(item_id),
        warehouse_id=int(warehouse_id),
        lot_id=int(lot_id),
    )
    target = int(qty)
    delta = target - int(cur)
    if delta == 0:
        return

    expiry_policy = await _load_item_expiry_policy(session, item_id=int(item_id))
    if expiry_policy == "REQUIRED" and int(delta) > 0:
        if bc_norm is None:
            raise RuntimeError(
                f"set_stock_qty requires lot_code for REQUIRED item: item_id={int(item_id)}"
            )
        production_date, expiry_date = _stable_required_dates_from_code(bc_norm, days=365)
    else:
        expiry_date = None
        production_date = None

    await adjust_lot_impl(
        session=session,
        item_id=int(item_id),
        warehouse_id=int(warehouse_id),
        lot_id=int(lot_id),
        delta=int(delta),
        reason="UT_SET_STOCK_QTY",
        ref="ut:set_stock_qty",
        ref_line=1,
        occurred_at=None,
        meta=None,
        lot_code=bc_norm,
        production_date=production_date,
        expiry_date=expiry_date,
        trace_id=None,
        utc_now=lambda: datetime.now(UTC),
    )


# ---------- lot-code-named test helpers ----------
async def ensure_supplier_lot_with_stock(
    session: AsyncSession,
    *,
    item_id: int,
    warehouse_id: int,
    lot_code: str,
    qty: int,
) -> None:
    """
    Test helper: create a SUPPLIER lot by display lot_code and set its stocks_lot qty.

    lot_code is display/input text only; stock identity remains lot_id.
    """
    code_raw = str(lot_code).strip()
    if not code_raw:
        raise ValueError("lot_code empty")

    _install_projection_pms_client(session)

    await ensure_warehouse(session, id=int(warehouse_id))
    await ensure_item(
        session,
        id=int(item_id),
        sku=f"SKU-{item_id}",
        name=f"ITEM-{item_id}",
        expiry_required=True,
    )
    _ = await ensure_supplier_lot(
        session,
        item_id=int(item_id),
        warehouse_id=int(warehouse_id),
        lot_code=code_raw,
    )
    await ensure_stock_slot(
        session,
        item_id=int(item_id),
        warehouse_id=int(warehouse_id),
        lot_code=code_raw,
    )
    await set_stock_qty(
        session,
        item_id=int(item_id),
        warehouse_id=int(warehouse_id),
        lot_code=code_raw,
        qty=int(qty),
    )


__all__ = [
    "ensure_item",
    "ensure_internal_lot_singleton",
    "ensure_stock_slot",
    "ensure_supplier_lot",
    "ensure_supplier_lot_with_stock",
    "ensure_warehouse",
    "set_stock_qty",
]
