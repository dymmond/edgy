import asyncio
from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple, Type, Union

from edgy.exceptions import SignalError
from edgy.utils.inspect import func_accepts_kwargs

if TYPE_CHECKING:
    from edgy import Model


def make_id(target: Any) -> Union[int, Tuple[int, int]]:
    """
    Creates an id for a function.
    """
    if hasattr(target, "__func__"):
        return (id(target.__self__), id(target.__func__))
    return id(target)


class Signal:
    """
    Base class for all Edgy signals.
    """

    def __init__(self) -> None:
        """
        Creates a new signal.
        """
        self.receivers: Dict[Union[int, Tuple[int, int]], Callable] = {}

    def connect(self, receiver: Callable) -> None:
        """
        Connects a given receiver to the the signal.
        """
        if not callable(receiver):
            raise SignalError("The signals should be callables")

        if not func_accepts_kwargs(receiver):
            raise SignalError("Signal receivers must accept keyword arguments (**kwargs).")

        key = make_id(receiver)
        if key not in self.receivers:
            self.receivers[key] = receiver

    def disconnect(self, receiver: Callable) -> bool:
        """
        Removes the receiver from the signal.
        """
        key = make_id(receiver)
        func: Union[Callable, None] = self.receivers.pop(key, None)
        return True if func is not None else False

    async def send(self, sender: Type["Model"], **kwargs: Any) -> None:
        """
        Sends the notification to all the receivers.
        """
        receivers = [func(sender=sender, **kwargs) for func in self.receivers.values()]
        await asyncio.gather(*receivers)


class Broadcaster(dict):
    def __getattr__(self, item: str) -> Signal:
        return self.setdefault(item, Signal())  # type: ignore

    def __setattr__(self, __name: str, __value: Signal) -> None:
        if not isinstance(__value, Signal):
            raise SignalError(f"{__value} is not valid signal")
        self[__name] = __value
