# scripts/oms/sync_fulfillment_projection.py
from __future__ import annotations

import argparse
import asyncio

from app.db.session import async_session_maker
from app.integrations.oms.projection_contracts import OmsFulfillmentReadyPlatform
from app.integrations.oms.projection_sync import (
    DEFAULT_LIMIT,
    sync_oms_fulfillment_projection_once,
)


def _platform(value: str | None) -> OmsFulfillmentReadyPlatform | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized not in {"pdd", "taobao", "jd"}:
        raise SystemExit("unsupported platform; expected one of: pdd, taobao, jd")
    return normalized  # type: ignore[return-value]


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync WMS OMS fulfillment projection from oms-api read-v1 output."
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--oms-api-base-url", default=None)
    parser.add_argument("--oms-api-token", default=None)
    parser.add_argument("--platform", default=None, choices=["pdd", "taobao", "jd"])
    parser.add_argument("--store-code", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    async with async_session_maker() as session:
        result = await sync_oms_fulfillment_projection_once(
            session,
            oms_api_base_url=args.oms_api_base_url,
            oms_api_token=args.oms_api_token,
            platform=_platform(args.platform),
            store_code=args.store_code,
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
        )
        await session.commit()

    print(
        "synced OMS fulfillment projection: "
        f"fetched={result.fetched} "
        f"orders={result.upserted_orders} "
        f"lines={result.upserted_lines} "
        f"components={result.upserted_components} "
        f"pages={result.pages} "
        f"last_offset={result.last_offset} "
        f"total={result.total}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
