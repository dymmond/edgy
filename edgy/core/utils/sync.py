import asyncio
from typing import Any, Awaitable

import nest_asyncio

nest_asyncio.apply()


def run_sync(awaitable: Awaitable) -> Any:
    """
    Runs the queries in sync mode
    """
    return asyncio.run(awaitable)
