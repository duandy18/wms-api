# tests/api/test_orders_sla_stats_api.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.services._helpers import ensure_store

pytestmark = pytest.mark.asyncio


async def _seed_outbound_completed_order(
    session: AsyncSession,
    *,
    platform: str = "PDD",
    store_code: str = "UT-SLA-STORE",
    created_at: datetime,
    outbound_completed_at: datetime,
) -> int:
    store_id = await ensure_store(
        session,
        platform=platform,
        store_code=store_code,
        name=f"UT-{platform}-{store_code}",
    )
    ext_order_no = f"UT-SLA-{uuid4().hex[:10]}"
    row = await session.execute(
        text(
            """
            INSERT INTO orders(
              platform,
              store_code,
              store_id,
              ext_order_no,
              status,
              created_at,
              updated_at
            )
            VALUES (
              :platform,
              :store_code,
              :store_id,
              :ext_order_no,
              'CREATED',
              :created_at,
              :created_at
            )
            RETURNING id
            """
        ),
        {
            "platform": platform,
            "store_code": store_code,
            "store_id": int(store_id),
            "ext_order_no": ext_order_no,
            "created_at": created_at,
        },
    )
    order_id = int(row.scalar_one())

    await session.execute(
        text(
            """
            INSERT INTO order_fulfillment(
              order_id,
              actual_warehouse_id,
              execution_stage,
              outbound_committed_at,
              outbound_completed_at,
              updated_at
            )
            VALUES (
              :order_id,
              1,
              'SHIP',
              :outbound_completed_at,
              :outbound_completed_at,
              :outbound_completed_at
            )
            ON CONFLICT (order_id) DO UPDATE
               SET actual_warehouse_id = EXCLUDED.actual_warehouse_id,
                   execution_stage = EXCLUDED.execution_stage,
                   outbound_committed_at = EXCLUDED.outbound_committed_at,
                   outbound_completed_at = EXCLUDED.outbound_completed_at,
                   updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "order_id": order_id,
            "outbound_completed_at": outbound_completed_at,
        },
    )
    await session.commit()
    return order_id


async def test_orders_sla_stats_uses_order_fulfillment_outbound_completed_at(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    created_at = now - timedelta(hours=2)
    outbound_completed_at = now - timedelta(hours=1)

    await _seed_outbound_completed_order(
        session,
        created_at=created_at,
        outbound_completed_at=outbound_completed_at,
    )

    resp = await client.get(
        "/orders/stats/sla",
        params={
            "time_from": (outbound_completed_at - timedelta(minutes=1)).isoformat(),
            "time_to": (outbound_completed_at + timedelta(minutes=1)).isoformat(),
            "platform": "PDD",
            "store_code": "UT-SLA-STORE",
            "sla_hours": 2,
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_orders"] == 1
    assert data["on_time_orders"] == 1
    assert data["on_time_rate"] == 1.0
    assert data["avg_ship_hours"] is not None
    assert 0.9 <= float(data["avg_ship_hours"]) <= 1.1


async def test_orders_sla_stats_filters_by_outbound_completed_at_window(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)

    await _seed_outbound_completed_order(
        session,
        platform="PDD",
        store_code="UT-SLA-WINDOW",
        created_at=now - timedelta(hours=5),
        outbound_completed_at=now - timedelta(hours=4),
    )

    resp = await client.get(
        "/orders/stats/sla",
        params={
            "time_from": (now - timedelta(hours=2)).isoformat(),
            "time_to": now.isoformat(),
            "platform": "PDD",
            "store_code": "UT-SLA-WINDOW",
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_orders"] == 0
    assert data["on_time_orders"] == 0
    assert data["on_time_rate"] == 0.0
