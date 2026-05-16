# tests/ci/test_wms_service_permission_runtime_contract.py
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.wms.system.service_auth.deps import (
    WMS_SERVICE_CLIENT_HEADER,
    require_wms_service_capability,
)
from app.wms.system.service_auth.models import (
    WmsServiceCapability,
    WmsServiceClient,
    WmsServicePermission,
)
from app.wms.system.service_auth.services import WmsServicePermissionService


def _sqlite_session() -> Session:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _register_sqlite_functions(dbapi_connection, _connection_record) -> None:
        dbapi_connection.create_function(
            "btrim",
            1,
            lambda value: "" if value is None else str(value).strip(),
        )

    WmsServiceCapability.__table__.create(engine)
    WmsServiceClient.__table__.create(engine)
    WmsServicePermission.__table__.create(engine)
    return Session(bind=engine)


def _seed_permission(
    db: Session,
    *,
    client_code: str,
    capability_code: str,
    capability_active: bool = True,
    client_active: bool = True,
    permission_active: bool = True,
) -> None:
    capability = WmsServiceCapability(
        capability_code=capability_code,
        capability_name=f"{capability_code} name",
        resource_code=capability_code.split(".")[-1],
        is_active=capability_active,
    )
    db.add(capability)
    db.flush()

    client = WmsServiceClient(
        client_code=client_code,
        client_name=f"{client_code} name",
        is_active=client_active,
    )
    db.add(client)
    db.flush()

    permission = WmsServicePermission(
        client_id=int(client.id),
        capability_code=capability_code,
        is_active=permission_active,
    )
    db.add(permission)
    db.commit()


def test_wms_service_permission_service_allows_active_client_and_capability() -> None:
    with _sqlite_session() as db:
        _seed_permission(
            db,
            client_code="procurement-service",
            capability_code="wms.read.warehouses",
        )

        service = WmsServicePermissionService(db)

        assert service.is_allowed(
            client_code=" procurement-service ",
            capability_code=" wms.read.warehouses ",
        )


def test_wms_service_permission_service_rejects_missing_inactive_or_ungranted() -> None:
    with _sqlite_session() as db:
        _seed_permission(
            db,
            client_code="inactive-capability-client",
            capability_code="wms.read.inactive_capability",
            capability_active=False,
        )
        _seed_permission(
            db,
            client_code="inactive-client",
            capability_code="wms.read.inactive_client",
            client_active=False,
        )
        _seed_permission(
            db,
            client_code="inactive-permission",
            capability_code="wms.read.inactive_permission",
            permission_active=False,
        )
        _seed_permission(
            db,
            client_code="procurement-service",
            capability_code="wms.read.warehouses",
        )

        service = WmsServicePermissionService(db)

        assert not service.is_allowed(client_code=None, capability_code="wms.read.warehouses")
        assert not service.is_allowed(client_code="procurement-service", capability_code=None)
        assert not service.is_allowed(
            client_code="unknown-service",
            capability_code="wms.read.warehouses",
        )
        assert not service.is_allowed(
            client_code="inactive-capability-client",
            capability_code="wms.read.inactive_capability",
        )
        assert not service.is_allowed(
            client_code="inactive-client",
            capability_code="wms.read.inactive_client",
        )
        assert not service.is_allowed(
            client_code="inactive-permission",
            capability_code="wms.read.inactive_permission",
        )
        assert not service.is_allowed(
            client_code="procurement-service",
            capability_code="wms.read.shipping_handoffs",
        )


class FakePermissionService:
    def __init__(self, *, allowed: bool) -> None:
        self.allowed = allowed
        self.calls: list[tuple[str | None, str | None]] = []

    def is_allowed(self, *, client_code: str | None, capability_code: str | None) -> bool:
        self.calls.append((client_code, capability_code))
        return self.allowed


def test_wms_service_permission_dependency_uses_service_client_header() -> None:
    assert WMS_SERVICE_CLIENT_HEADER == "X-Service-Client"

    dependency = require_wms_service_capability("wms.read.warehouses")
    service = FakePermissionService(allowed=True)

    dependency(
        x_service_client="procurement-service",
        service=service,  # type: ignore[arg-type]
    )

    assert service.calls == [("procurement-service", "wms.read.warehouses")]


def test_wms_service_permission_dependency_rejects_missing_service_client_header() -> None:
    dependency = require_wms_service_capability("wms.read.warehouses")
    service = FakePermissionService(allowed=True)

    try:
        dependency(
            x_service_client=None,
            service=service,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "wms_service_client_required"
    else:
        raise AssertionError("missing X-Service-Client should be rejected")


def test_wms_service_permission_dependency_rejects_denied_capability() -> None:
    dependency = require_wms_service_capability("wms.read.shipping_handoffs")
    service = FakePermissionService(allowed=False)

    try:
        dependency(
            x_service_client="procurement-service",
            service=service,  # type: ignore[arg-type]
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "wms_service_permission_denied"
    else:
        raise AssertionError("denied service permission should be rejected")
