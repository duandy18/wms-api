# scripts/seed_test_baseline.py
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text

from scripts.ensure_admin import ensure_admin as ensure_admin_user


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_sql(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"Fixture SQL not found: {path}")
    return path.read_text(encoding="utf-8")


async def _sync_wms_pms_projection_baseline(conn) -> None:
    """
    测试基线同步 WMS PMS projection。

    pytest 每个用例都会 TRUNCATE + seed owner PMS 表；
    WMS 执行链现在只读 wms_pms_*_projection，因此 seed 后必须同步 projection。
    这里先按 FK 顺序清空 projection，再从当前 owner 表重建测试基线。
    """
    for table_name in (
        "wms_pms_item_barcode_projection",
        "wms_pms_item_sku_code_projection",
        "wms_pms_item_policy_projection",
        "wms_pms_item_uom_projection",
        "wms_pms_item_projection",
    ):
        await conn.execute(text(f"DELETE FROM {table_name}"))

    await conn.execute(
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
            ORDER BY i.id ASC
            """
        )
    )

    await conn.execute(
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
            ORDER BY u.item_id ASC, u.id ASC
            """
        )
    )

    await conn.execute(
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
            ORDER BY i.id ASC
            """
        )
    )

    await conn.execute(
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
            ORDER BY sc.item_id ASC, sc.id ASC
            """
        )
    )

    await conn.execute(
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
            ORDER BY b.item_id ASC, b.id ASC
            """
        )
    )


@lru_cache(maxsize=1)
def discover_permission_names() -> list[str]:
    app_dir = _repo_root() / "app"
    if not app_dir.exists():
        return ["page.admin.read", "page.admin.write"]

    pat = re.compile(r"""["']([a-z][a-z0-9_]*\.[a-z0-9_]+\.[a-z0-9_.]+)["']""")
    names: set[str] = set()

    for p in app_dir.rglob("*.py"):
        try:
            s = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in pat.finditer(s):
            v = (m.group(1) or "").strip()
            if not v or len(v) > 128:
                continue
            if v.count(".") < 2:
                continue
            if not re.fullmatch(r"[a-z0-9_.]+", v):
                continue
            names.add(v)

    # 当前 admin 主线至少应包含页面级权限
    names.add("page.admin.read")
    names.add("page.admin.write")
    return sorted(names)


async def seed_in_conn(conn) -> None:
    """
    在已有连接/事务里执行 seed（pytest/conftest 调用）
    调用方保证已 TRUNCATE 干净，并且 SET search_path TO public

    当前权限基线：
    - 运行时权限真相源 = user_permissions
    - 不再创建 roles / user_roles / role_permissions
    - admin 测试用户直接拥有全部 permissions
    """
    root = _repo_root()
    base_sql_path = root / "tests" / "fixtures" / "base_seed.sql"

    # 1) 主数据基线
    await conn.execute(text(_load_sql(base_sql_path)))

    await _sync_wms_pms_projection_baseline(conn)

    # 2) admin 用户（可登录）
    await ensure_admin_user(username="admin", password="admin123", full_name="Dev Admin")

    # 3) 权限字典
    names = discover_permission_names()

    await conn.execute(
        text(
            """
            INSERT INTO permissions (name)
            SELECT x.name
            FROM (SELECT unnest(CAST(:names AS text[])) AS name) AS x
            ON CONFLICT (name) DO NOTHING
            """
        ),
        {"names": names},
    )

    user_id = (await conn.execute(text("SELECT id FROM users WHERE username='admin' LIMIT 1"))).scalar_one()
    user_id = int(user_id)

    # 4) 运行时权限真相源：admin 直配全部 permissions
    # 先清再灌，确保测试基线确定且可重复。
    await conn.execute(
        text(
            """
            DELETE FROM user_permissions
             WHERE user_id = :uid
            """
        ),
        {"uid": user_id},
    )

    await conn.execute(
        text(
            """
            INSERT INTO user_permissions (user_id, permission_id)
            SELECT :uid, p.id
            FROM permissions p
            """
        ),
        {"uid": user_id},
    )


async def main() -> None:
    dsn = os.getenv("WMS_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("WMS_DATABASE_URL / DATABASE_URL 未设置，无法 seed")

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(dsn, poolclass=NullPool, pool_pre_ping=False, future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SET search_path TO public"))
            await seed_in_conn(conn)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
