from typing import cast

from lilya.context import session


def add_message(level: str, message: str) -> None:
    """
    Adds a flash message to the current session. These messages are typically
    displayed to the user on the next request and then cleared.

    The `level` parameter categorizes the message (e.g., 'success', 'info',
    'warning', 'error'), which can be used for styling or conditional rendering.

    Args:
        level (str): The severity or type of the message (e.g., "success", "info", "warning", "error").
        message (str): The actual text content of the message.
    """
    # Check if a 'messages' attribute exists in the session context.
    # If not, initialize it as an empty list.
    if not hasattr(session, "messages"):
        session.messages = []
    # Cast the 'messages' attribute to a list and append the new message as a dictionary.
    cast(list, session.messages).append({"level": level, "text": message})


def get_messages(peek: bool = False) -> list:
    """
    Retrieves flash messages from the session.

    By default, this function retrieves all messages and then clears them from
    the session so they are not displayed again. If `peek` is set to `True`,
    the messages are returned without being cleared from the session, allowing
    them to be accessed multiple times.

    Args:
        peek (bool, optional): If `True`, messages are returned but not cleared from the session.
                               Defaults to `False`.

    Returns:
        list: A list of dictionaries, where each dictionary represents a message
              and contains 'level' and 'text' keys. Returns an empty list if no
              messages are present.
    """
    # If no 'messages' attribute exists in the session, return an empty list.
    if not hasattr(session, "messages"):
        return []
    # Get the messages list from the session.
    messages = cast(list, session.messages)
    if peek:
        # If 'peek' is True, return the messages without clearing them.
        return messages
    # If 'peek' is False, create a copy of the messages, clear the original
    # list in the session, and then return the copy.
    _messages = messages.copy()
    messages.clear()
    return _messages
