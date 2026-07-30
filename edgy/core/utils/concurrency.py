from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Collection
from typing import TypeVar

from edgy.conf import settings

T = TypeVar("T")


async def run_concurrently(coros: Collection[Awaitable[T]], limit: int | None = None) -> list[T]:
    """
    Generic concurrent runner for Edgy ORM operations that need to be executed
    in parallel while respecting global concurrency settings.

    Args:
        coros: A Collection or Sequence of already created `Awaitable[Any]` objects (coroutines)
               to be executed. The order will be honored in case the input has an order.
        limit:
            An optional limit. Can be 0 to be disabled, 1 for a sequential mode,
            None for using the orm_concurrency_limit setting.

    Returns:
        A list containing the results of the awaited coroutines in the same order
        as the input sequence.
    """
    # don't call gather with zero args, speedup path
    if not coros:
        return []

    enabled: bool = getattr(settings, "orm_concurrency_enabled", True)
    eff_limit: int | None = (
        limit if limit is not None else getattr(settings, "orm_concurrency_limit", None)
    )

    if not enabled:
        eff_limit = 1
    if eff_limit is None or eff_limit <= 0:
        return await asyncio.gather(*coros)
    _coros: deque[Awaitable[T]] = deque(coros)
    del coros
    results: list[T] = []
    batch: list[Awaitable[T]] = []
    try:
        while _coros:
            while _coros and len(batch) < eff_limit:
                batch.append(_coros.popleft())
            if len(batch) > 1:
                results.extend(await asyncio.gather(*batch))
            else:
                results.append(await batch[0])
            batch.clear()
    except BaseException:
        # cleanup not executed coroutines
        cleanup_batch = []
        while _coros:
            future = asyncio.ensure_future(_coros.popleft())
            # cancel them all
            future.cancel()
            cleanup_batch.append(future)
        # and just ignore (don't return another exception except if gather is canceled)
        await asyncio.gather(*cleanup_batch, return_exceptions=True)
        raise

    return results
