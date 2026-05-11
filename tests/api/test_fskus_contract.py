# tests/api/test_fskus_contract.py
from __future__ import annotations

from typing import Any, Dict, List
from uuid import uuid4

import pytest
from pytest import MonkeyPatch
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pms.contracts import PmsExportSkuCodeResolution


def _assert_problem_shape(obj: Dict[str, Any]) -> None:
    assert isinstance(obj, dict)
    assert "error_code" in obj
    assert "message" in obj
    assert "http_status" in obj
    assert "trace_id" in obj
    assert "context" in obj


async def _auth_headers(client) -> Dict[str, str]:
    r = await client.post("/users/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    data = r.json()
    token = data.get("access_token")
    assert isinstance(token, str) and token
    return {"Authorization": f"Bearer {token}"}


async def _pick_any_item_id(session: AsyncSession) -> int:
    row = (
        await session.execute(
            text(
                """
                SELECT i.id
                  FROM items i
                  JOIN item_sku_codes c
                    ON c.item_id = i.id
                   AND c.code = i.sku
                   AND c.is_active IS TRUE
                  JOIN item_uoms u
                    ON u.item_id = i.id
                   AND (u.is_outbound_default IS TRUE OR u.is_base IS TRUE)
                 WHERE i.enabled IS TRUE
                 ORDER BY i.id ASC
                 LIMIT 1
                """
            )
        )
    ).first()
    assert row is not None, "expected seeded enabled item with active sku code and outbound/base uom"
    return int(row[0])


async def _pick_item_sku_by_id(session: AsyncSession, *, item_id: int) -> str:
    row = (
        await session.execute(
            text(
                """
                SELECT sku
                  FROM items
                 WHERE id = :item_id
                 LIMIT 1
                """
            ),
            {"item_id": int(item_id)},
        )
    ).first()
    assert row is not None, f"item_id not found in seeded items: {item_id}"
    sku = str(row[0]).strip()
    assert sku
    return sku


async def _load_resolution_by_sku(
    session: AsyncSession,
    *,
    sku: str,
) -> PmsExportSkuCodeResolution:
    row = (
        await session.execute(
            text(
                """
                SELECT
                    c.id AS sku_code_id,
                    i.id AS item_id,
                    c.code AS sku_code,
                    c.code_type::text AS code_type,
                    c.is_primary AS is_primary,
                    i.sku AS item_sku,
                    i.name AS item_name,
                    u.id AS item_uom_id,
                    u.uom AS uom,
                    u.display_name AS display_name,
                    COALESCE(NULLIF(u.display_name, ''), u.uom) AS uom_name,
                    u.ratio_to_base AS ratio_to_base
                  FROM item_sku_codes c
                  JOIN items i
                    ON i.id = c.item_id
                  JOIN item_uoms u
                    ON u.item_id = i.id
                   AND (u.is_outbound_default IS TRUE OR u.is_base IS TRUE)
                 WHERE c.code = :sku
                   AND c.is_active IS TRUE
                   AND i.enabled IS TRUE
                 ORDER BY u.is_outbound_default DESC, u.is_base DESC, u.id ASC
                 LIMIT 1
                """
            ),
            {"sku": str(sku).strip()},
        )
    ).mappings().first()

    assert row is not None, f"expected PMS resolution seed for sku={sku!r}"

    return PmsExportSkuCodeResolution(
        sku_code_id=int(row["sku_code_id"]),
        item_id=int(row["item_id"]),
        sku_code=str(row["sku_code"]),
        code_type=str(row["code_type"]),
        is_primary=bool(row["is_primary"]),
        item_sku=str(row["item_sku"]),
        item_name=str(row["item_name"]),
        item_uom_id=int(row["item_uom_id"]),
        uom=str(row["uom"]),
        display_name=(str(row["display_name"]) if row["display_name"] is not None else None),
        uom_name=str(row["uom_name"]),
        ratio_to_base=int(row["ratio_to_base"]),
    )


class _FakeSyncPmsReadClient:
    def __init__(self, resolution_by_code: dict[str, PmsExportSkuCodeResolution]) -> None:
        self._resolution_by_code = {
            str(code).strip(): row for code, row in resolution_by_code.items()
        }

    def resolve_active_code_for_outbound_default(
        self,
        *,
        code: str,
        enabled_only: bool = True,
    ) -> PmsExportSkuCodeResolution | None:
        _ = enabled_only
        return self._resolution_by_code.get(str(code).strip())


def _patch_fsku_pms_resolver(
    monkeypatch: MonkeyPatch,
    resolution_by_code: dict[str, PmsExportSkuCodeResolution],
) -> None:
    import app.oms.fsku.services.fsku_service_write as fsku_write

    def _factory(*args, **kwargs) -> _FakeSyncPmsReadClient:
        _ = args
        _ = kwargs
        return _FakeSyncPmsReadClient(resolution_by_code)

    monkeypatch.setattr(fsku_write, "create_sync_pms_read_client", _factory)


async def _create_draft_fsku(
    client,
    headers: Dict[str, str],
    *,
    session: AsyncSession,
    monkeypatch: MonkeyPatch,
    name: str = "FSKU-TEST",
    shape: str = "bundle",
    fsku_expr: str | None = None,
) -> Dict[str, Any]:
    if fsku_expr is None:
        item_id = await _pick_any_item_id(session)
        sku = await _pick_item_sku_by_id(session, item_id=item_id)
        resolution = await _load_resolution_by_sku(session, sku=sku)
        _patch_fsku_pms_resolver(monkeypatch, {sku: resolution})
        alloc_unit_price = 1 + (uuid4().int % 100000)
        fsku_expr = f"{sku}*1*{alloc_unit_price}"

    r = await client.post(
        "/oms/fskus",
        json={"name": name, "shape": shape, "fsku_expr": fsku_expr},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _replace_components(
    client,
    headers: Dict[str, str],
    fsku_id: int,
    components: List[dict],
    *,
    session: AsyncSession,
    monkeypatch: MonkeyPatch,
):
    parts: list[str] = []
    resolution_by_code: dict[str, PmsExportSkuCodeResolution] = {}

    for c in components:
        sku = await _pick_item_sku_by_id(session, item_id=int(c["resolved_item_id"]))
        resolution_by_code[sku] = await _load_resolution_by_sku(session, sku=sku)
        qty = int(c.get("qty") or 1)
        parts.append(f"{sku}*{qty}*1")

    _patch_fsku_pms_resolver(monkeypatch, resolution_by_code)

    expr = "+".join(parts)
    r = await client.post(
        f"/oms/fskus/{fsku_id}/expression",
        json={"fsku_expr": expr},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_fsku_list_contract_with_archive_fields(client):
    """
    核心合同：
    GET /oms/fskus 必须返回列表页所需的全部字段
    """
    headers = await _auth_headers(client)

    r = await client.get("/oms/fskus", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    assert "items" in data and isinstance(data["items"], list)
    assert "total" in data
    assert "limit" in data
    assert "offset" in data

    items = data["items"]
    if not items:
        return

    one = items[0]

    for k in (
        "id",
        "code",
        "name",
        "shape",
        "status",
        "updated_at",
        "components_summary",
        "published_at",
        "retired_at",
    ):
        assert k in one, one

    assert isinstance(one["id"], int)
    assert isinstance(one["code"], str) and one["code"]
    assert isinstance(one["name"], str)
    assert one["shape"] in ("single", "bundle")
    assert one["status"] in ("draft", "published", "retired")
    assert isinstance(one["components_summary"], str)

    if one["status"] == "retired":
        assert one["retired_at"] is not None
    else:
        assert one["retired_at"] is None


@pytest.mark.asyncio
async def test_fsku_archive_lifecycle(
    client,
    session: AsyncSession,
    monkeypatch: MonkeyPatch,
):
    """
    归档（retire）行为必须在列表中可见
    """
    headers = await _auth_headers(client)
    item_id = await _pick_any_item_id(session)

    f = await _create_draft_fsku(
        client,
        headers,
        session=session,
        monkeypatch=monkeypatch,
        name="FSKU-ARCHIVE-TEST",
    )

    await _replace_components(
        client,
        headers,
        fsku_id=f["id"],
        components=[{"resolved_item_id": item_id, "qty": 1, "role": "primary"}],
        session=session,
        monkeypatch=monkeypatch,
    )

    r_pub = await client.post(f"/oms/fskus/{f['id']}/publish", headers=headers)
    assert r_pub.status_code == 200

    r_ret = await client.post(f"/oms/fskus/{f['id']}/retire", headers=headers)
    assert r_ret.status_code == 200
    body = r_ret.json()

    assert body["status"] == "retired"
    assert body["retired_at"] is not None

    r_list = await client.get("/oms/fskus", headers=headers)
    items = r_list.json()["items"]
    hit = next(x for x in items if x["id"] == f["id"])
    assert hit["status"] == "retired"
    assert hit["retired_at"] is not None


@pytest.mark.asyncio
async def test_fsku_unretire_lifecycle(
    client,
    session: AsyncSession,
    monkeypatch: MonkeyPatch,
):
    """
    契约封板：FSKU 生命周期单向（draft → published → retired），发布事实不可逆。
    因此 unretire endpoint 仅兼容保留，但必须永远返回 409（state_conflict）+ Problem shape。
    """
    headers = await _auth_headers(client)
    item_id = await _pick_any_item_id(session)

    f = await _create_draft_fsku(
        client,
        headers,
        session=session,
        monkeypatch=monkeypatch,
        name="FSKU-UNRETIRE-TEST",
    )

    await _replace_components(
        client,
        headers,
        fsku_id=f["id"],
        components=[{"resolved_item_id": item_id, "qty": 1, "role": "primary"}],
        session=session,
        monkeypatch=monkeypatch,
    )

    r_pub = await client.post(f"/oms/fskus/{f['id']}/publish", headers=headers)
    assert r_pub.status_code == 200, r_pub.text
    pub = r_pub.json()
    assert pub["status"] == "published"
    assert pub["published_at"] is not None

    r_ret = await client.post(f"/oms/fskus/{f['id']}/retire", headers=headers)
    assert r_ret.status_code == 200, r_ret.text
    ret = r_ret.json()
    assert ret["status"] == "retired"
    assert ret["retired_at"] is not None
    assert ret["published_at"] is not None

    r_un = await client.post(f"/oms/fskus/{f['id']}/unretire", headers=headers)
    assert r_un.status_code == 409, r_un.text
    body = r_un.json()
    _assert_problem_shape(body)
    assert body.get("error_code") == "state_conflict"
    msg = str(body.get("message") or "")
    assert ("不支持取消归档" in msg) or ("生命周期单向" in msg)


@pytest.mark.asyncio
async def test_fsku_unretire_guard_requires_retired(
    client,
    session: AsyncSession,
    monkeypatch: MonkeyPatch,
):
    """
    契约封板：unretire 永远不允许（兼容保留但必须 409 + Problem）
    - draft -> 409 + Problem
    - published -> 409 + Problem
    - retired -> 409 + Problem
    """
    headers = await _auth_headers(client)
    item_id = await _pick_any_item_id(session)

    f = await _create_draft_fsku(
        client,
        headers,
        session=session,
        monkeypatch=monkeypatch,
        name="FSKU-UNRETIRE-GUARD",
    )

    r_un_draft = await client.post(f"/oms/fskus/{f['id']}/unretire", headers=headers)
    assert r_un_draft.status_code == 409, r_un_draft.text
    _assert_problem_shape(r_un_draft.json())

    await _replace_components(
        client,
        headers,
        fsku_id=f["id"],
        components=[{"resolved_item_id": item_id, "qty": 1, "role": "primary"}],
        session=session,
        monkeypatch=monkeypatch,
    )

    r_pub = await client.post(f"/oms/fskus/{f['id']}/publish", headers=headers)
    assert r_pub.status_code == 200, r_pub.text

    r_un_pub = await client.post(f"/oms/fskus/{f['id']}/unretire", headers=headers)
    assert r_un_pub.status_code == 409, r_un_pub.text
    _assert_problem_shape(r_un_pub.json())

    r_ret = await client.post(f"/oms/fskus/{f['id']}/retire", headers=headers)
    assert r_ret.status_code == 200, r_ret.text

    r_un_ret = await client.post(f"/oms/fskus/{f['id']}/unretire", headers=headers)
    assert r_un_ret.status_code == 409, r_un_ret.text
    _assert_problem_shape(r_un_ret.json())
