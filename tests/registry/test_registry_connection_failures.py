from __future__ import annotations

import pytest

from edgy.core.connection.registry import Registry

pytestmark = pytest.mark.anyio


async def test_registry_enter_raises_and_disconnects_successful_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = Registry("sqlite:///primary.db", extra={"analytics": "sqlite:///analytics.db"})
    disconnected: list[str] = []

    async def disconnect_primary() -> None:
        disconnected.append("primary")

    async def disconnect_analytics() -> None:
        disconnected.append("analytics")

    registry.database.disconnect = disconnect_primary  # type: ignore[method-assign]
    registry.extra["analytics"].disconnect = disconnect_analytics  # type: ignore[method-assign]

    async def fake_connect_and_init(
        self: Registry,
        name: str | None,
        database: object,  # noqa: ARG001
    ) -> None:
        if name == "analytics":
            raise RuntimeError("connect-failed")

    monkeypatch.setattr(Registry, "_connect_and_init", fake_connect_and_init)

    with pytest.raises(RuntimeError, match="connect-failed"):
        await registry.__aenter__()

    assert disconnected == ["primary"]


async def test_registry_enter_prefers_original_connect_error_over_disconnect_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = Registry("sqlite:///primary.db", extra={"analytics": "sqlite:///analytics.db"})

    async def disconnect_primary() -> None:
        raise RuntimeError("disconnect-failed")

    async def disconnect_analytics() -> None:
        raise AssertionError("failing connection must not be rolled back here")

    registry.database.disconnect = disconnect_primary  # type: ignore[method-assign]
    registry.extra["analytics"].disconnect = disconnect_analytics  # type: ignore[method-assign]

    async def fake_connect_and_init(
        self: Registry,
        name: str | None,
        database: object,  # noqa: ARG001
    ) -> None:
        if name == "analytics":
            raise RuntimeError("connect-failed")

    monkeypatch.setattr(Registry, "_connect_and_init", fake_connect_and_init)

    with pytest.raises(RuntimeError, match="connect-failed"):
        await registry.__aenter__()
