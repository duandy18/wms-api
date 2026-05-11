# scripts/pms/reconcile_projection.py
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.db.session import async_session_maker
from app.integrations.pms.projection_reconciliation import (
    reconcile_pms_projection_references,
)


async def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile WMS PMS scalar references against local PMS projection tables"
    )
    parser.add_argument("--per-reference-limit", type=int, default=200)
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        help="Exit with code 2 when reconciliation issues are found.",
    )
    args = parser.parse_args()

    async with async_session_maker() as session:
        result = await reconcile_pms_projection_references(
            session,
            per_reference_limit=int(args.per_reference_limit),
        )

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
    if args.fail_on_issues and not result.ok:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
