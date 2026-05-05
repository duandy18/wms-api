from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_async_session
from app.oms.order_facts.contracts.code_mapping import (
    CodeMappingCodeOptionListOut,
)
from app.oms.order_facts.services.code_mapping_service import (
    list_code_mapping_code_options,
)


router = APIRouter(tags=["oms-code-mapping"])


def _route_name(platform: str, suffix: str) -> str:
    return f"{platform}_{suffix}"


def _register_platform_routes(platform: str) -> None:
    @router.get(
        f"/{platform}/code-mapping/code-options",
        response_model=CodeMappingCodeOptionListOut,
        name=_route_name(platform, "list_platform_code_mapping_code_options"),
    )
    async def list_platform_code_mapping_code_options(
        store_code: str | None = Query(None, min_length=1, max_length=128),
        merchant_code: str | None = Query(None, min_length=1, max_length=128),
        only_unbound: bool = Query(False),
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        session: AsyncSession = Depends(get_async_session),
    ) -> CodeMappingCodeOptionListOut:
        try:
            data = await list_code_mapping_code_options(
                session,
                platform=platform,
                store_code=store_code,
                merchant_code=merchant_code,
                only_unbound=only_unbound,
                limit=int(limit),
                offset=int(offset),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return CodeMappingCodeOptionListOut(ok=True, data=data)


for _platform in ("pdd", "taobao", "jd"):
    _register_platform_routes(_platform)
