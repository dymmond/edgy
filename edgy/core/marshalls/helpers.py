from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any, Dict, Generator

if TYPE_CHECKING:
    from edgy.core.marshalls import Marshall


class MarshallFieldMapping(MutableMapping):
    """
    Dictionary used to store the information about
    the fields used in the Marshall.
    """

    def __init__(self, marshall: "Marshall") -> None:
        self._marshall = marshall
        self._fields: Dict[str, Any] = {}

    def __setitem__(self, key: str, field: Any) -> None:
        self._fields[key] = field

    def __getitem__(self, key: str) -> Any:
        return self._fields[key]

    def __delitem__(self, key: str) -> None:
        del self._fields[key]

    def __iter__(self) -> Generator:
        return iter(self._fields)

    def __len__(self) -> int:
        return len(self._fields)

    def __repr__(self) -> Any:
        return dict.__repr__(self._fields)
