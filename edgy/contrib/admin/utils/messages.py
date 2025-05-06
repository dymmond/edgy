from typing import Any

from lilya.requests import Request


def add_message(request: Request, level: str, message: str) -> None:
    """
    Stores a message in the session for rendering in the next request.
    Level can be: success, info, warning, error.
    """
    session = request.session.setdefault("_messages", [])
    session.append({"level": level, "text": message})


def get_messages(request: Request) -> Any:
    """
    Retrieves and clears messages from the session.
    """
    messages = request.session.pop("_messages", [])
    return messages
