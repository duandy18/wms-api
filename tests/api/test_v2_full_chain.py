# tests/api/test_v2_full_chain.py
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.oms.services.order_service import OrderService
from app.wms.stock.services.lots import ensure_lot_full
from app.wms.stock.services.stock_service import StockService


async def _ensure_store_route_to_wh1(session: AsyncSession, *, plat: str, store_code: str, province: str) -> None:
    """
    该 helper 保留用于历史/可读性：配置 store_warehouse + store_province_routes。
    Phase 5 的服务归属命中依赖 warehouse_service_provinces(/cities)，与 store_province_routes 无关。
    """
    await session.execute(
        text(
            """
            INSERT INTO stores (
  platform,
  store_code,
  store_name
)
VALUES (
  :p,
  :s,
  :n
)
            ON CONFLICT (platform, store_code) DO NOTHING
            """
        ),
        {"p": plat.upper(), "s": store_code, "n": f"UT-{plat.upper()}-{store_code}"},
    )
    row = await session.execute(
        text("SELECT id FROM stores WHERE platform=:p AND store_code=:s LIMIT 1"),
        {"p": plat.upper(), "s": store_code},
    )
    store_id = int(row.scalar_one())

    # 绑定仓 1
    await session.execute(
        text(
            """
            INSERT INTO store_warehouse (store_id, warehouse_id, is_top, priority)
            VALUES (:sid, 1, TRUE, 10)
            ON CONFLICT (store_id, warehouse_id) DO NOTHING
            """
        ),
        {"sid": store_id},
    )

    # 省路由 → 仓 1（仅为兼容旧测试数据，不作为主线依赖）
    await session.execute(
        text("DELETE FROM store_province_routes WHERE store_id=:sid AND province=:prov"),
        {"sid": store_id, "prov": province},
    )
    await session.execute(
        text(
            """
            INSERT INTO store_province_routes (store_id, province, warehouse_id, priority, active)
            VALUES (:sid, :prov, 1, 10, TRUE)
            """
        ),
        {"sid": store_id, "prov": province},
    )


async def _ensure_supplier_lot(session: AsyncSession, *, wh_id: int, item_id: int, lot_code: str) -> int:
    """
    当前终态：
    - REQUIRED lot 身份 = (warehouse_id, item_id, production_date)
    - lot_code 只保留为展示/输入/追溯属性
    因此测试侧必须走统一入口 ensure_lot_full，并在 REQUIRED 商品下显式给 production_date。
    """
    return await ensure_lot_full(
        session,
        item_id=int(item_id),
        warehouse_id=int(wh_id),
        lot_code=str(lot_code),
        production_date=date.today(),
        expiry_date=None,
    )


async def _load_order_id(
    session: AsyncSession,
    *,
    plat: str,
    store_code: str,
    ext_order_no: str,
) -> int:
    row = await session.execute(
        text(
            """
            SELECT id
            FROM orders
            WHERE platform = :platform
              AND store_code = :store_code
              AND ext_order_no = :ext_order_no
            LIMIT 1
            """
        ),
        {
            "platform": str(plat).upper(),
            "store_code": str(store_code),
            "ext_order_no": str(ext_order_no),
        },
    )
    order_id = row.scalar_one_or_none()
    assert order_id is not None, "order row not found after ingest"
    return int(order_id)



@pytest.mark.asyncio
async def test_v2_order_full_chain(client: AsyncClient, db_session_like_pg: AsyncSession):
    """
    Phase 5+ 下的“订单驱动履约链”核心验收（当前主线）：

    1) ingest：创建订单并写 trace_id
    2) 人工履约决策：调用 manual-assign 指定执行仓，并标记可进入履约
    3) 入库（为后续 pick/ship 准备库存）
    4) legacy pick HTTP route 已退役；WMS 验证订单、履约分配、库存就绪边界
    5) shipment execution / waybill 已迁移到 logistics-api；WMS 不再请求面单
    """
    plat = "PDD"
    store_code = "1"
    uniq = uuid4().hex[:10]
    ext = f"ORD-TEST-3001-{uniq}"
    order_ref = f"ORD:{plat}:{store_code}:{ext}"
    now = datetime.now(timezone.utc)

    province = "UT-PROV"
    city = "UT-CITY"
    district = "UT-DISTRICT"

    await _ensure_store_route_to_wh1(db_session_like_pg, plat=plat, store_code=store_code, province=province)
    await db_session_like_pg.commit()

    trace_id = f"TEST-TRACE-ORDER-3001-{uniq}"

    print(f"[TEST] 准备订单 {order_ref}")

    # 1) 创建订单（必须带 province）
    r = await OrderService.ingest(
        db_session_like_pg,
        platform=plat,
        store_code=store_code,
        ext_order_no=ext,
        occurred_at=now,
        buyer_name="tester",
        buyer_phone="",
        order_amount=0,
        pay_amount=0,
        items=[{"item_id": 3001, "qty": 1, "title": "猫粮"}],
        address={
            "province": province,
            "city": city,
            "district": district,
            "receiver_name": "X",
            "receiver_phone": "000",
        },
        extras=None,
        trace_id=trace_id,
    )
    await db_session_like_pg.commit()
    print(f"[TEST] ingest 返回: {r}")
    assert r["ref"] == order_ref

    order_id = await _load_order_id(
        db_session_like_pg,
        plat=plat,
        store_code=store_code,
        ext_order_no=ext,
    )

    # 2) manual-assign（需要登录；测试环境一般用 admin/admin123）
    login = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        f"/orders/{plat}/{store_code}/{ext}/fulfillment/manual-assign",
        json={"warehouse_id": 1, "reason": "UT assign", "note": "test"},
        headers=headers,
    )
    print("[HTTP] manual-assign status:", resp.status_code, "body:", resp.text)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "OK"
    assert body["ref"] == order_ref
    assert int(body["to_warehouse_id"]) == 1

    # 3) 入库（Lot-World：必须锚定 lot_id）
    stock_svc = StockService()
    lot_code = "BATCH-001"
    lot_id = await _ensure_supplier_lot(db_session_like_pg, wh_id=1, item_id=3001, lot_code=lot_code)

    await stock_svc.adjust_lot(
        session=db_session_like_pg,
        item_id=3001,
        warehouse_id=1,
        lot_id=int(lot_id),
        delta=10,
        reason="RECEIPT",
        ref=f"UNIT-TEST-IN-3001-{uniq}",
        ref_line=1,
        occurred_at=now,
        lot_code=lot_code,
        production_date=now.date(),
        expiry_date=None,
        trace_id=None,
    )
    await db_session_like_pg.commit()
    print("[TEST] 已通过 StockService.adjust_lot 入库 10 件到 BATCH-001")

    # 4) legacy HTTP pick route has been retired.
    # Formal outbound execution is covered by /wms/outbound/orders/{order_id}/submit
    # and dedicated outbound submit API tests.
    assert lot_id > 0

    # 5) Logistics handoff boundary.
    # Shipment execution / waybill 已迁移到 logistics-api。
    # WMS 全链路测试停在订单创建、人工履约分配、库存就绪这条边界。
    assert order_id > 0

    # diagnostics trace endpoint has been retired.
    # The full-chain contract now ends at the WMS logistics handoff boundary;
    # trace_id remains a persisted data field, not a debug API dependency.
    assert trace_id
