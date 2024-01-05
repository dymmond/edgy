import asyncio
from concurrent import futures
from concurrent.futures import Future
from typing import Any, Awaitable


def run_sync(async_function: Awaitable) -> Any:
    """
    Runs the queries in sync mode
    """
    try:
        return asyncio.run(async_function)
    except RuntimeError:
        with futures.ThreadPoolExecutor(max_workers=1) as executor:
            future: Future = executor.submit(asyncio.run, async_function)
            return future.result()
