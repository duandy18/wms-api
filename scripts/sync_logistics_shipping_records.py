from __future__ import annotations

import argparse
import asyncio

from app.db.session import async_session_maker
from app.shipping_assist.records.sync.service import sync_logistics_shipping_record_facts_once


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Sync Logistics shipping record facts into WMS shipping_records")
    parser.add_argument("--after-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--platform", default=None)
    parser.add_argument("--store-code", default=None)
    args = parser.parse_args()

    async with async_session_maker() as session:
        result = await sync_logistics_shipping_record_facts_once(
            session,
            after_id=args.after_id,
            limit=args.limit,
            platform=args.platform,
            store_code=args.store_code,
        )
        await session.commit()

    print(
        "synced logistics shipping records: "
        f"fetched={result.fetched} upserted={result.upserted} "
        f"last_cursor={result.last_cursor} has_more={result.has_more}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
