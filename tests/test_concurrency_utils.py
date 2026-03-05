from __future__ import annotations

import asyncio

import pytest

from edgy.core.utils.concurrency import batched, run_concurrently

pytestmark = pytest.mark.anyio


def test_batched_invalid_size() -> None:
    with pytest.raises(ValueError, match="n must be at least one"):
        tuple(batched((1, 2, 3), 0))


def test_batched_groups_items() -> None:
    assert tuple(batched((1, 2, 3, 4, 5), 2)) == ((1, 2), (3, 4), (5,))


async def test_run_concurrently_limit_one_avoids_gather(monkeypatch: pytest.MonkeyPatch) -> None:
    async def coro(value: int) -> int:
        await asyncio.sleep(0)
        return value

    async def fail_gather(*args: object, **kwargs: object) -> object:
        raise AssertionError("asyncio.gather should not be called for limit=1")

    monkeypatch.setattr(asyncio, "gather", fail_gather)

    result = await run_concurrently([coro(1), coro(2), coro(3)], limit=1)
    assert result == [1, 2, 3]
