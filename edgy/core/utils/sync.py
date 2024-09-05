import asyncio
from contextvars import copy_context
from threading import Thread
from typing import Any, Awaitable, Optional


async def _coro_helper(awaitable: Awaitable, timeout: Optional[float]) -> Any:
    if timeout is not None and timeout > 0:
        return await asyncio.wait_for(awaitable, timeout)
    return await awaitable


def thread_run(awaitable: Awaitable, future: asyncio.Future) -> None:
    try:
        future.set_result(asyncio.run(awaitable))
    except BaseException as exc:
        future.set_exception(exc)


def run_sync(awaitable: Awaitable, timeout: Optional[float] = None) -> Any:
    """
    Runs the queries in sync mode
    """
    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return asyncio.run(_coro_helper(awaitable, timeout))
    else:
        future: asyncio.Future = loop.create_future()
        context = copy_context()
        thread = Thread(
            target=context.run,
            args=[thread_run, _coro_helper(awaitable, timeout), future],
        )
        thread.start()
        thread.join()
        return future.result()
