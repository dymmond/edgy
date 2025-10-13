from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import anyio


async def gather_limited(
    tasks: Sequence[Callable[[], Awaitable[Any]]], limit: int | None = None
) -> list[Any]:
    """
    Run 0-arg coroutine factories concurrently with optional concurrency limit.
    Results preserve input order.
    """
    if not tasks:
        return []
    results: list[Any] = [None] * len(tasks)
    sem = anyio.Semaphore(limit) if limit else None

    async def _one(i: int, f: Callable[[], Awaitable[Any]]) -> None:
        if sem:
            async with sem:
                results[i] = await f()
        else:
            results[i] = await f()

    async with anyio.create_task_group() as tg:
        for i, f in enumerate(tasks):
            tg.start_soon(_one, i, f)

    return results


async def run_all(coros: Sequence[Awaitable[Any]], limit: int | None = None) -> list[Any]:
    """
    Convenience: like asyncio.gather but anyio + optional limit.
    """
    return await gather_limited([lambda c=c: c for c in coros], limit=limit)
