from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.factory import create_pms_read_client
from app.wms.inventory_adjustment.return_inbound.contracts.probe import (
    InboundTaskProbeOut,
    InboundTaskProbeStatus,
)
from app.wms.inventory_adjustment.return_inbound.repos.inbound_task_probe_repo import (
    InboundTaskProbeLine,
    get_inbound_task_probe_lines,
)


async def _load_actual_uom_name(
    session: AsyncSession,
    *,
    item_id: int,
    item_uom_id: int | None,
) -> str | None:
    if item_uom_id is None:
        return None

    uom = await create_pms_read_client(session=session).get_uom(
        item_uom_id=int(item_uom_id),
    )
    if uom is None:
        return None
    if int(uom.item_id) != int(item_id):
        return None

    return str(uom.uom_name or uom.display_name or uom.uom or "").strip() or None


def _match_line(
    *,
    lines: list[InboundTaskProbeLine],
    item_id: int,
    item_uom_id: int | None,
) -> tuple[InboundTaskProbeStatus, InboundTaskProbeLine | None, str | None]:
    if item_uom_id is not None:
        exact = [ln for ln in lines if ln.item_id == item_id and ln.item_uom_id == item_uom_id]
        if len(exact) == 1:
            return InboundTaskProbeStatus.MATCHED, exact[0], None
        if len(exact) > 1:
            return (
                InboundTaskProbeStatus.AMBIGUOUS,
                None,
                "当前收货单存在多条相同商品包装任务行，无法自动命中。",
            )

    by_item = [ln for ln in lines if ln.item_id == item_id]
    if len(by_item) == 1:
        msg = None
        if item_uom_id is not None and by_item[0].item_uom_id != item_uom_id:
            msg = "当前收货单计划包装与实际扫码包装不同，已按同商品命中任务行。"
        return InboundTaskProbeStatus.MATCHED, by_item[0], msg

    if len(by_item) > 1:
        return (
            InboundTaskProbeStatus.AMBIGUOUS,
            None,
            "当前收货单存在同商品多条任务行，无法仅按商品自动命中。",
        )

    return (
        InboundTaskProbeStatus.UNMATCHED,
        None,
        "当前收货单不存在该商品。",
    )


async def probe_inbound_task_barcode(
    session: AsyncSession,
    *,
    receipt_no: str,
    barcode: str,
) -> InboundTaskProbeOut:
    code = (barcode or "").strip()
    lines = await get_inbound_task_probe_lines(session, receipt_no=receipt_no)

    probe = await create_pms_read_client(session=session).probe_barcode(barcode=code)
    if probe.status != "BOUND" or probe.item_id is None:
        return InboundTaskProbeOut(
            ok=True,
            status=InboundTaskProbeStatus.UNBOUND,
            barcode=code,
            message="条码未绑定商品包装。",
        )

    item_id = int(probe.item_id)
    item_uom_id = int(probe.item_uom_id) if probe.item_uom_id is not None else None
    ratio_to_base = int(probe.ratio_to_base) if probe.ratio_to_base is not None else None

    status, matched, message = _match_line(
        lines=lines,
        item_id=item_id,
        item_uom_id=item_uom_id,
    )

    actual_uom_name_snapshot = await _load_actual_uom_name(
        session,
        item_id=item_id,
        item_uom_id=item_uom_id,
    )

    return InboundTaskProbeOut(
        ok=True,
        status=status,
        barcode=code,
        item_id=item_id,
        item_uom_id=item_uom_id,
        ratio_to_base=ratio_to_base,
        matched_line_no=(matched.line_no if matched else None),
        item_name_snapshot=(matched.item_name_snapshot if matched else None),
        uom_name_snapshot=(
            actual_uom_name_snapshot
            if actual_uom_name_snapshot is not None
            else (matched.uom_name_snapshot if matched else None)
        ),
        message=message,
    )


__all__ = [
    "probe_inbound_task_barcode",
]
