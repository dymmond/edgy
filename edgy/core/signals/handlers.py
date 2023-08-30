from typing import TYPE_CHECKING, Callable, List, Type, Union

if TYPE_CHECKING:  # pragma: no cover
    from edgy import Model


class Send:
    """
    Base for all the wrappers handling the signals.
    """

    def consumer(signal: str, senders: Union[Type["Model"], List[Type["Model"]]]) -> Callable:
        """
        Connects the function to all the senders.
        """

        def wrapper(func: Callable) -> Callable:
            _senders = [senders] if not isinstance(senders, list) else senders

            for sender in _senders:
                signals = getattr(sender.meta.signals, signal)
                signals.connect(func)
            return func

        return wrapper


def pre_save(senders: Union[Type["Model"], List[Type["Model"]]]) -> Callable:
    """
    Connects all the senders to pre_save.
    """
    return Send.consumer(signal="pre_save", senders=senders)


def pre_update(senders: Union[Type["Model"], List[Type["Model"]]]) -> Callable:
    """
    Connects all the senders to pre_update.
    """
    return Send.consumer(signal="pre_update", senders=senders)


def pre_delete(senders: Union[Type["Model"], List[Type["Model"]]]) -> Callable:
    """
    Connects all the senders to pre_delete.
    """
    return Send.consumer(signal="pre_delete", senders=senders)


def post_save(senders: Union[Type["Model"], List[Type["Model"]]]) -> Callable:
    """
    Connects all the senders to post_save.
    """
    return Send.consumer(signal="post_save", senders=senders)


def post_update(senders: Union[Type["Model"], List[Type["Model"]]]) -> Callable:
    """
    Connects all the senders to post_update.
    """
    return Send.consumer(signal="post_update", senders=senders)


def post_delete(senders: Union[Type["Model"], List[Type["Model"]]]) -> Callable:
    """
    Connects all the senders to post_delete.
    """
    return Send.consumer(signal="post_delete", senders=senders)
