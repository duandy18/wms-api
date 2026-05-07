# app/wms/outbound/services/order_fulfillment_service.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.problem import raise_problem


@dataclass(frozen=True)
class FulfillmentRow:
    order_id: int
    planned_warehouse_id: Optional[int]
    actual_warehouse_id: Optional[int]
    fulfillment_status: Optional[str]
    blocked_reasons: Optional[dict]
    execution_stage: Optional[str]
    outbound_committed_at: Optional[datetime]
    outbound_completed_at: Optional[datetime]


class OrderFulfillmentService:
    """
    Phase 5（路 A）：执行阶段真相只看 execution_stage；SHIP 子状态机从 fulfillment_status 彻底移除。

    - execution_stage：NULL/PICK/SHIP（单向，不回退）
    - outbound_committed_at：进入 WMS 出库提交 / 出库裁决链路的事实时间
    - outbound_completed_at：WMS 库存出库完成时间；不是物流单号/面单完成时间
    - fulfillment_status：仅保留路由/阻断/人工干预语义（DB 已禁止 SHIP_COMMITTED/SHIPPED）
    """

    STAGE_PICK = "PICK"
    STAGE_SHIP = "SHIP"

    @staticmethod
    async def _load_for_update(
        session: AsyncSession,
        *,
        order_id: int,
    ) -> Optional[FulfillmentRow]:
        row = (
            await session.execute(
                text(
                    """
                    SELECT
                      order_id,
                      planned_warehouse_id,
                      actual_warehouse_id,
                      fulfillment_status,
                      blocked_reasons,
                      execution_stage,
                      outbound_committed_at,
                      outbound_completed_at
                    FROM order_fulfillment
                    WHERE order_id = :oid
                    FOR UPDATE
                    """
                ),
                {"oid": int(order_id)},
            )
        ).first()

        if not row:
            return None

        return FulfillmentRow(
            order_id=int(row[0]),
            planned_warehouse_id=(int(row[1]) if row[1] is not None else None),
            actual_warehouse_id=(int(row[2]) if row[2] is not None else None),
            fulfillment_status=(str(row[3]) if row[3] is not None else None),
            blocked_reasons=(row[4] if row[4] is not None else None),
            execution_stage=(str(row[5]) if row[5] is not None else None),
            outbound_committed_at=(row[6] if row[6] is not None else None),
            outbound_completed_at=(row[7] if row[7] is not None else None),
        )

    async def ensure_outbound_committed(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        warehouse_id: int,
        at: datetime,
    ) -> dict:
        """
        进入 WMS 出库提交 / 出库裁决链路锚点（事实）：

        - 确保 order_fulfillment 行存在
        - 硬约束执行仓不可漂移
        - outbound_committed_at：NULL -> at；非 NULL 幂等
        - execution_stage：单向推进到 SHIP（不回退）

        返回：
        - idempotent: bool（outbound_committed_at 是否已存在）
        - outbound_committed_at: str（ISO）
        """
        existing = await self._load_for_update(session, order_id=int(order_id))

        if existing is None:
            await session.execute(
                text(
                    """
                    INSERT INTO order_fulfillment(
                      order_id,
                      actual_warehouse_id,
                      outbound_committed_at,
                      execution_stage,
                      updated_at
                    )
                    VALUES (:oid, :wid, :oca, :stg, :at)
                    """
                ),
                {
                    "oid": int(order_id),
                    "wid": int(warehouse_id),
                    "oca": at,
                    "stg": self.STAGE_SHIP,
                    "at": at,
                },
            )
            return {
                "idempotent": False,
                "outbound_committed_at": at.isoformat(),
            }

        if existing.actual_warehouse_id is not None and int(
            existing.actual_warehouse_id
        ) != int(warehouse_id):
            raise_problem(
                status_code=409,
                error_code="fulfillment_warehouse_conflict",
                message="执行仓冲突：订单已绑定执行仓，禁止换仓提交出库。",
                context={
                    "order_id": int(order_id),
                    "existing_actual_warehouse_id": int(existing.actual_warehouse_id),
                    "incoming_warehouse_id": int(warehouse_id),
                },
                details=[],
                next_actions=[
                    {
                        "action": "inspect_fulfillment",
                        "label": "检查订单履约记录",
                    }
                ],
            )

        idempotent = existing.outbound_committed_at is not None

        await session.execute(
            text(
                """
                UPDATE order_fulfillment
                   SET actual_warehouse_id = COALESCE(actual_warehouse_id, :wid),
                       outbound_committed_at = COALESCE(outbound_committed_at, :oca),
                       execution_stage = CASE
                           WHEN execution_stage IS NULL THEN 'SHIP'
                           WHEN execution_stage = 'PICK' THEN 'SHIP'
                           WHEN execution_stage = 'SHIP' THEN 'SHIP'
                           ELSE execution_stage
                       END,
                       updated_at = :at
                 WHERE order_id = :oid
                """
            ),
            {"oid": int(order_id), "wid": int(warehouse_id), "oca": at, "at": at},
        )

        return {
            "idempotent": bool(idempotent),
            "outbound_committed_at": (
                existing.outbound_committed_at or at
            ).isoformat(),
        }

    async def mark_outbound_completed(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        at: datetime,
    ) -> dict:
        """
        WMS 库存出库完成（事实）：

        规则（硬）：
        - 必须先存在 outbound_committed_at（否则 409）
        - outbound_completed_at 幂等：已存在则不重复写
        - execution_stage 强制为 SHIP（单向不回退）

        返回：
        - idempotent: bool（outbound_completed_at 是否已存在）
        - outbound_completed_at: str（ISO）
        """
        existing = await self._load_for_update(session, order_id=int(order_id))
        if existing is None:
            raise_problem(
                status_code=409,
                error_code="fulfillment_missing",
                message="订单履约记录不存在：禁止直接标记已出库，请先进入 WMS 出库提交链路。",
                context={"order_id": int(order_id)},
                details=[],
                next_actions=[
                    {
                        "action": "ensure_outbound_committed",
                        "label": "先进入 WMS 出库提交链路",
                    }
                ],
            )
            return {"idempotent": False, "outbound_completed_at": ""}

        if existing.outbound_completed_at is not None:
            await session.execute(
                text(
                    """
                    UPDATE order_fulfillment
                       SET execution_stage = CASE
                           WHEN execution_stage IS NULL THEN 'SHIP'
                           WHEN execution_stage = 'PICK' THEN 'SHIP'
                           WHEN execution_stage = 'SHIP' THEN 'SHIP'
                           ELSE execution_stage
                       END,
                           updated_at = :at
                     WHERE order_id = :oid
                    """
                ),
                {"oid": int(order_id), "at": at},
            )
            return {
                "idempotent": True,
                "outbound_completed_at": existing.outbound_completed_at.isoformat(),
            }

        if existing.outbound_committed_at is None:
            raise_problem(
                status_code=409,
                error_code="fulfillment_invalid_transition",
                message="履约状态不允许直接标记已出库：必须先进入 WMS 出库提交链路。",
                context={"order_id": int(order_id)},
                details=[],
                next_actions=[
                    {
                        "action": "ensure_outbound_committed",
                        "label": "先进入 WMS 出库提交链路",
                    }
                ],
            )
            return {"idempotent": False, "outbound_completed_at": ""}

        await session.execute(
            text(
                """
                UPDATE order_fulfillment
                   SET outbound_completed_at = COALESCE(outbound_completed_at, :oca),
                       execution_stage = CASE
                           WHEN execution_stage IS NULL THEN 'SHIP'
                           WHEN execution_stage = 'PICK' THEN 'SHIP'
                           WHEN execution_stage = 'SHIP' THEN 'SHIP'
                           ELSE execution_stage
                       END,
                       updated_at = :at
                 WHERE order_id = :oid
                """
            ),
            {"oid": int(order_id), "oca": at, "at": at},
        )

        return {"idempotent": False, "outbound_completed_at": at.isoformat()}
