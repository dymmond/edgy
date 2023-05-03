import typing
from collections.abc import Mapping
from typing import Any, Generator, List, Optional, TypeVar

from edgy.core.datastructures import ArbitraryHashableBaseModel


class Position(ArbitraryHashableBaseModel):
    def __init__(self, line_no: int, column_no: int, char_index: int, **kwargs: typing.Any):
        super().__init__(**kwargs)
        self.line_no = line_no
        self.column_no = column_no
        self.char_index = char_index

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, Position)
            and self.line_no == other.line_no
            and self.column_no == other.column_no
            and self.char_index == other.char_index
        )

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return (
            f"{class_name}(line_no={self.line_no}, column_no={self.column_no},"
            f" char_index={self.char_index})"
        )


class Message(ArbitraryHashableBaseModel):
    def __init__(
        self,
        *,
        text: str,
        code: Optional[str] = None,
        key: Optional[typing.Union[int, str]] = None,
        index: Optional[List[typing.Union[int, str]]] = None,
        position: Optional[Position] = None,
        start_position: Optional[Position] = None,
        end_position: Optional[Position] = None,
        **kwargs: typing.Any,
    ):
        super().__init__(**kwargs)
        self.text = text
        self.code = "custom" if code is None else code
        if key is not None:
            assert index is None
            self.index = [key]
        else:
            self.index = [] if index is None else index

        if position is None:
            self.start_position = start_position
            self.end_position = end_position
        else:
            assert start_position is None
            assert end_position is None
            self.start_position = position
            self.end_position = position

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Message) and (
            self.text == other.text
            and self.code == other.code
            and self.index == other.index
            and self.start_position == other.start_position
            and self.end_position == other.end_position
        )

    def __hash__(self) -> int:
        ident = (self.code, tuple(self.index))
        return hash(ident)

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        index_str = f", index={self.index!r}" if self.index else ""
        if self.start_position is None:
            position_str = ""
        elif self.start_position == self.end_position:
            position_str = f", position={self.start_position!r}"
        else:
            position_str = (
                f", start_position={self.start_position!r}," f" end_position={self.end_position!r}"
            )
        return f"{class_name}(text={self.text!r}," f" code={self.code!r}{index_str}{position_str})"


class BaseError(Mapping, Exception):
    def __init__(
        self,
        *,
        text: Optional[str] = None,
        code: Optional[str] = None,
        key: Optional[typing.Union[int, str]] = None,
        position: Optional[Position] = None,
        messages: Optional[typing.List[Message]] = None,
    ):
        if messages is None:
            assert text is not None
            messages = [Message(text=text, code=code, key=key, position=position)]
        else:
            assert text is None
            assert code is None
            assert key is None
            assert position is None
            assert len(messages)

        self._messages = messages
        self._message_dict: typing.Dict[typing.Union[int, str], typing.Union[str, dict]] = {}

        # Populate 'self._message_dict'
        for message in messages:
            insert_into = self._message_dict
            for key in message.index[:-1]:
                insert_into = insert_into.setdefault(key, {})  # type: ignore
            insert_key = message.index[-1] if message.index else ""
            insert_into[insert_key] = message.text

    def messages(self, *, prefix: Optional[typing.Union[str, int]] = None) -> typing.List[Message]:
        """
        Return a list of all the messages.

        prefix - An optional key to add to the index of all returned messages.
                    Useful in nested objects when validation needs to accumulate
                    all the child messages for each item in the parent object.
        """
        if prefix is not None:
            return [
                Message(
                    text=message.text,
                    code=message.code,
                    index=[prefix] + message.index,
                )
                for message in self._messages
            ]
        return list(self._messages)

    def __iter__(self) -> typing.Iterator:
        return iter(self._message_dict)

    def __len__(self) -> int:
        return len(self._message_dict)

    def __getitem__(self, key: typing.Any) -> typing.Union[str, dict]:
        return self._message_dict[key]

    def __eq__(self, other: typing.Any) -> bool:
        from edgy.exceptions import ValidationError

        return bool(isinstance(other, ValidationError) and self._messages == other._messages)

    def __hash__(self) -> int:
        ident = tuple(hash(m) for m in self._messages)
        return hash(ident)

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        if len(self._messages) == 1 and not self._messages[0].index:
            message = self._messages[0]
            return f"{class_name}(text={message.text!r}, code={message.code!r})"
        return f"{class_name}({self._messages!r})"

    def __str__(self) -> str:
        if len(self._messages) == 1 and not self._messages[0].index:
            return self._messages[0].text
        return str(dict(self))


BaseErrorType = TypeVar("BaseErrorType", bound=BaseError)


class ValidationResult(ArbitraryHashableBaseModel):
    def __init__(
        self,
        *,
        value: Optional[Any] = None,
        error: Optional[BaseErrorType] = None,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(**kwargs)
        assert value is None or error is None
        self.value = value
        self.error = error

    def __iter__(self) -> Generator:
        yield self.value
        yield self.error

    def __bool__(self) -> bool:
        return self.error is None

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        if self.error is not None:
            return f"{class_name}(error={self.error!r})"
        return f"{class_name}(value={self.value!r})"
