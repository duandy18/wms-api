#!/usr/bin/env python3
# scripts/rebuild_wms_pms_projection.py
from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild WMS-local PMS projection tables from current PMS owner tables.",
    )
    parser.add_argument(
        "--dsn",
        default=None,
        help=(
            "Database DSN. If provided, both WMS_DATABASE_URL and "
            "WMS_TEST_DATABASE_URL are set to this value before opening the session."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run rebuild inside a transaction and roll it back after reporting counts.",
    )
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()

    if args.dsn:
        dsn = str(args.dsn).strip()
        if not dsn:
            raise SystemExit("--dsn cannot be blank")
        os.environ["WMS_DATABASE_URL"] = dsn
        os.environ["WMS_TEST_DATABASE_URL"] = dsn

    # Import after env setup: app.db.session reads env vars at import time.
    from app.db.session import AsyncSessionLocal, close_engines
    from app.wms.pms_projection.services.rebuild_service import (
        WmsPmsProjectionRebuildService,
    )

    try:
        async with AsyncSessionLocal() as session:
            tx = await session.begin()
            try:
                result = await WmsPmsProjectionRebuildService(session).rebuild_all()
                payload = asdict(result)
                payload["dry_run"] = bool(args.dry_run)

                if args.dry_run:
                    await tx.rollback()
                else:
                    await tx.commit()

                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                return 0
            except Exception:
                await tx.rollback()
                raise
    finally:
        await close_engines()


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
