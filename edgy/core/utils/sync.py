import asyncio
from contextvars import copy_context
from functools import lru_cache
from threading import Thread
from typing import Any, Awaitable, Optional

import nest_asyncio


async def _coro_helper(awaitable: Awaitable) -> Any:
    return await awaitable


@lru_cache(1, False)
def _init_nest_asyncio() -> None:
    nest_asyncio.apply()


def thread_run(awaitable: Awaitable, future: asyncio.Future, loop: Any = None) -> None:
    close_after = False
    if loop is None:
        loop = asyncio.new_event_loop()
        close_after = True
    try:
        future.set_result(loop.run_until_complete(_coro_helper(awaitable)))
    except BaseException as exc:
        future.set_exception(exc)
    finally:
        if close_after:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()


def run_sync(
    awaitable: Awaitable, timeout: Optional[int] = None, use_nested_loop: bool = True
) -> Any:
    """
    Runs the queries in sync mode
    """
    future: asyncio.Future = asyncio.Future()
    context = copy_context()
    close_after = False
    loop = None
    if use_nested_loop:
        _init_nest_asyncio()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            close_after = True
    thread = Thread(target=context.run, args=[thread_run, awaitable, future, loop])
    thread.start()
    try:
        thread.join(timeout)
        return future.result()
    finally:
        if close_after and loop is not None:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
