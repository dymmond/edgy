import inspect
from typing import Callable


def func_accepts_kwargs(func: Callable) -> bool:
    """
    Checks if a function accepts **kwargs.
    """
    return any(
        param
        for param in inspect.signature(func).parameters.values()
        if param.kind == param.VAR_KEYWORD
    )
