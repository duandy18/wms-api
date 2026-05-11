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

    PMS legacy baseline 去 owner 化：
    - base_seed.sql 暂时保留旧 PMS owner seed，支撑 legacy baseline 过渡区。
    - pms_projection_seed.sql 是 WMS PMS projection-only baseline。
    - projection seed 不再从旧 PMS owner 表物化。
    """
    root = _repo_root()
    base_sql_path = root / "tests" / "fixtures" / "base_seed.sql"
    pms_projection_sql_path = root / "tests" / "fixtures" / "pms_projection_seed.sql"

    # 1) 主数据基线
    await conn.execute(text(_load_sql(base_sql_path)))

    # 1.1) WMS PMS projection-only baseline
    await conn.execute(text(_load_sql(pms_projection_sql_path)))

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
