from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, TypeVar

import anyio
from anyio import Semaphore

from edgy.conf import settings

T = TypeVar("T")
TaskFactory = Callable[[], Awaitable[T]]


async def gather_limited(tasks: Sequence[TaskFactory[T]], limit: int | None = None) -> list[T]:
    """
    Runs a sequence of zero-argument coroutine factories concurrently with an optional
    concurrency limit.

    This utility functions similarly to `asyncio.gather` but leverages `anyio` for
    asynchronous scheduling and incorporates an explicit throttling mechanism via an
    `anyio.Semaphore` when a limit is provided.

    The primary guarantee of this function is that the results of the executed coroutines
    are collected and returned in a list that **preserves the original order** of the
    input `tasks` sequence, regardless of their completion time.

    Args:
        tasks: A sequence of callable objects (factories). Each callable must take no
               arguments and return an awaitable (a coroutine) to be executed.
        limit: An integer specifying the maximum number of tasks allowed to execute
               simultaneously.
               - If set to an integer greater than 0, an `anyio.Semaphore` is initialized
                 to enforce the bound.
               - If set to `None`, concurrency is unbounded (limited only by the
                 underlying `anyio` event loop scheduler).

    Returns:
        A list containing the results (`T`) of the awaited coroutines. The order
        of elements in this list corresponds directly to the order of tasks in the
        input sequence.

    Raises:
        Exception: If any task within the group raises an exception, the `anyio.create_task_group`
                   will propagate that exception, and all other running tasks will be
                   immediately cancelled.
    """
    if not tasks:
        return []

    # Initialize a results list with 'None' placeholders to ensure the final list
    # preserves the input order based on index.
    results: list[Any] = [None] * len(tasks)

    # Initialize the Semaphore only if a positive integer limit is provided.
    semaphore: Semaphore | None = anyio.Semaphore(limit) if limit and limit > 0 else None

    async def _one(i: int, f: TaskFactory[Any]) -> None:
        """
        Internal asynchronous worker that executes a single task factory, awaits its
        coroutine, and stores the result at the correct index `i`.

        It handles the acquisition and release of the concurrency semaphore if one exists.
        """
        if semaphore:
            async with semaphore:
                results[i] = await f()
        else:
            results[i] = await f()

    # Create a TaskGroup to manage the concurrent lifecycle of all tasks
    async with anyio.create_task_group() as tg:
        for i, f in enumerate(tasks):
            # Start each task, passing its original index `i` and the factory `f`
            tg.start_soon(_one, i, f)

    # All tasks are guaranteed to be complete when the task group exits successfully.
    # We cast to list[T] as all placeholders must have been replaced by results of type T.
    return results


async def run_all(coros: Sequence[Awaitable[Any]], limit: int | None = None) -> list[Any]:
    """
    Executes a sequence of already-created coroutine objects concurrently with an
    optional limit on the number of simultaneous executions.

    This function acts as a convenience wrapper, similar to `asyncio.gather`, but
    is built on `anyio` and supports concurrency throttling via the `gather_limited`
    utility.

    It ensures that all coroutines are started, awaited, and their results are collected
    in a list that preserves the original input order.

    Args:
        coros: A sequence of already created `Awaitable[Any]` objects (coroutines).
        limit: An integer specifying the maximum number of coroutines allowed to run
               concurrently.
               - If `None`, concurrency is unbounded.
               - If an integer, execution is throttled by a semaphore.

    Returns:
        A list containing the results of the awaited coroutines, ordered identically
        to the input `coros` sequence.

    Implementation Detail:
        It converts the sequence of awaitables into a sequence of zero-argument callable
        factories (using a lambda function with a closure `c=c`) as required by
        `gather_limited`.
    """
    return await gather_limited([lambda c=c: c for c in coros], limit=limit)


async def run_concurrently(coros: Sequence[Awaitable[Any]], limit: int | None = None) -> list[Any]:
    """
    Generic concurrent runner for Edgy ORM operations that need to be executed
    in parallel while respecting global concurrency settings.

    This function executes a sequence of already-created coroutine objects (`coros`)
    using an `anyio.create_task_group`. It enforces a concurrency limit read from
    `settings.orm_concurrency_limit` via an `anyio.Semaphore`.

    The results are collected in the order the coroutines finish, **not** necessarily
    the order they appeared in the input sequence.

    Args:
        coros: A sequence of already created `Awaitable[Any]` objects (coroutines)
               to be executed.

    Returns:
        A list containing the results of the awaited coroutines. The order of results
        is determined by the completion time of the tasks.

    Internal Logic:
        - It reads the **concurrency limit** (`orm_concurrency_limit`, defaults to 5)
          and **enabled status** (`orm_concurrency_enabled`, defaults to True) from
          the global `settings`.
        - If concurrency is disabled, the semaphore is set to `None`, effectively
          running tasks sequentially without concurrency benefit.
    """
    if not coros:
        return []

    enabled: bool = getattr(settings, "orm_concurrency_enabled", True)
    if not enabled:
        return [await c for c in coros]

    # Read concurrency settings with defaults
    limit = limit if limit is not None else getattr(settings, "orm_concurrency_limit", None)
    if limit is None or limit < 1:
        limit = 1

    # Initialize semaphore if enabled; otherwise, it's None.
    sem: Semaphore | None = anyio.Semaphore(limit) if enabled else None

    # Results are collected in the order of completion
    results: list[Any] = []

    async def _runner(coro: Awaitable[Any]) -> None:
        """
        Internal worker function that executes a single coroutine, acquiring the
        concurrency semaphore if one is present.
        """
        if sem:
            async with sem:
                results.append(await coro)
        else:
            results.append(await coro)

    # Use a TaskGroup for efficient concurrent execution
    async with anyio.create_task_group() as tg:
        for c in coros:
            tg.start_soon(_runner, c)

    # Return results collected by the _runner workers
    return results
