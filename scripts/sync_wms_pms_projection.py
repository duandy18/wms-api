#!/usr/bin/env python3
# scripts/sync_wms_pms_projection.py
from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict
from datetime import datetime


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync WMS-local PMS projection incrementally from PMS owner updated_at.",
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
        help="Run sync inside a transaction and roll it back after reporting counts.",
    )
    parser.add_argument(
        "--overlap-seconds",
        type=int,
        default=0,
        help="Optional updated_at overlap window. Defaults to 0 to avoid repeated rebuild.",
    )
    return parser.parse_args()


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


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
    from app.wms.pms_projection.services.sync_service import WmsPmsProjectionSyncService

    try:
        async with AsyncSessionLocal() as session:
            tx = await session.begin()
            try:
                result = await WmsPmsProjectionSyncService(session).sync_once(
                    overlap_seconds=int(args.overlap_seconds),
                )
                payload = asdict(result)
                payload["dry_run"] = bool(args.dry_run)

                if args.dry_run:
                    await tx.rollback()
                else:
                    await tx.commit()

                print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_default))
                return 0
            except Exception:
                if args.dry_run:
                    await tx.rollback()
                else:
                    # sync_once records FAILED / last_error / retry_count before re-raising.
                    # Commit that diagnostic state when possible; cursor itself is not advanced.
                    await tx.commit()
                raise
    finally:
        await close_engines()


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
