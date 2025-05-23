from typing import cast

from lilya.context import session


def add_message(level: str, message: str) -> None:
    """
    Stores a message in the session for rendering in the next request.
    Level can be: success, info, warning, error.
    """
    if not hasattr(session, "messages"):
        session.messages = []
    cast(list, session.messages).append({"level": level, "text": message})


def get_messages(peek: bool = False) -> list:
    """
    Retrieves and clears messages from the session.
    """
    if not hasattr(session, "messages"):
        return []
    messages = cast(list, session.messages)
    if peek:
        return messages
    _messages = messages.copy()
    messages.clear()
    return _messages
