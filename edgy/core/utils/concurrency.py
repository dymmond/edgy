from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Generator, Iterable, Sequence
from itertools import islice
from typing import TypeVar

from edgy.conf import settings

T = TypeVar("T")


def batched(iterable: Iterable[T], n: int) -> Generator[tuple[T, ...], None, None]:
    # batched('ABCDEFG', 2) → AB CD EF G
    if n < 1:
        raise ValueError("n must be at least one")
    iterator = iter(iterable)
    while batch := tuple(islice(iterator, n)):
        yield batch


async def run_concurrently(coros: Sequence[Awaitable[T]], limit: int | None = None) -> list[T]:
    """
    Generic concurrent runner for Edgy ORM operations that need to be executed
    in parallel while respecting global concurrency settings.

    Args:
        coros: A sequence of already created `Awaitable[Any]` objects (coroutines)
               to be executed.
        limit:
            An optional limit. Can be 0 to be disabled, 1 for a sequential mode,
            None for using the orm_concurrency_limit setting.

    Returns:
        A list containing the results of the awaited coroutines. The order of results
        is determined by the completion time of the tasks.
    """
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
    results: list[T] = []
    for batch in batched(coros, eff_limit):
        results.extend(await asyncio.gather(*batch))

    return results
