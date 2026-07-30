from __future__ import annotations

import asyncio
from collections.abc import Awaitable

import pytest

from edgy.core.utils.concurrency import run_concurrently

pytestmark = pytest.mark.anyio


async def test_run_concurrently_limit_one_avoids_gather(monkeypatch: pytest.MonkeyPatch) -> None:
    async def coro(value: int) -> int:
        await asyncio.sleep(0)
        return value

    async def fail_gather(*args: object, **kwargs: object) -> object:
        raise AssertionError("asyncio.gather should not be called for limit=1")

    monkeypatch.setattr(asyncio, "gather", fail_gather)

    result = await run_concurrently([coro(1), coro(2), coro(3)], limit=1)
    assert result == [1, 2, 3]


@pytest.mark.parametrize("limit", [2, None, 0, -1])
async def test_run_concurrently_shall_gather(monkeypatch: pytest.MonkeyPatch, limit) -> None:
    async def coro(value: int) -> int:
        await asyncio.sleep(0)
        return value

    gathered = 0

    async def succeed_gather(*args: Awaitable, **kwargs: object) -> object:
        nonlocal gathered
        gathered = len(args)
        return [await arg for arg in args]

    monkeypatch.setattr(asyncio, "gather", succeed_gather)

    result = await run_concurrently([coro(1), coro(2)], limit=limit)
    assert result == [1, 2]
    assert gathered == 2


@pytest.mark.parametrize("limit", [0, 1, 2])
async def test_run_concurrently_fail(limit) -> None:
    called = 0

    async def coro(value: int) -> None:
        nonlocal called
        called += 1
        await asyncio.sleep(0)
        raise ValueError

    arr = [coro(1), coro(2), coro(3)]
    assert called == 0
    with pytest.raises(ValueError):
        await run_concurrently(arr, limit=limit)
    if limit == 0:
        assert called == 3
    elif limit == 1:
        assert called == 1
    else:
        assert called == 2
