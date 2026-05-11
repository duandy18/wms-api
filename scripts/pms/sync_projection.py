# scripts/pms/sync_projection.py
from __future__ import annotations

import argparse
import asyncio

from app.db.session import async_session_maker
from app.integrations.pms.projection_sync import (
    DEFAULT_LIMIT,
    RESOURCE_ORDER,
    ProjectionResource,
    sync_pms_read_projection_once,
)


def _resources(values: list[str] | None) -> tuple[ProjectionResource, ...] | None:
    if not values:
        return None

    allowed = set(RESOURCE_ORDER)
    out: list[ProjectionResource] = []
    for value in values:
        resource = value.strip()
        if resource not in allowed:
            raise SystemExit(f"unsupported resource={resource}; expected one of {sorted(allowed)}")
        out.append(resource)  # type: ignore[arg-type]
    return tuple(out)


async def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync PMS read projection tables from pms-api read-v1 projection feed"
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--pms-api-base-url", default=None)
    parser.add_argument(
        "--resource",
        action="append",
        choices=list(RESOURCE_ORDER),
        help="Resource to sync. Can be repeated. Defaults to all resources.",
    )
    args = parser.parse_args()

    async with async_session_maker() as session:
        result = await sync_pms_read_projection_once(
            session,
            pms_api_base_url=args.pms_api_base_url,
            limit=args.limit,
            resources=_resources(args.resource),
        )
        await session.commit()

    print(
        "synced PMS read projection: "
        f"fetched={result.fetched} upserted={result.upserted}"
    )
    for resource, row in result.resources.items():
        print(
            f"- {resource}: fetched={row.fetched} upserted={row.upserted} "
            f"pages={row.pages} last_offset={row.last_offset} has_more={row.has_more}"
        )


if __name__ == "__main__":
    asyncio.run(_main())
