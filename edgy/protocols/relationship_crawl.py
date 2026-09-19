from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:  # pragma: no cove
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.types import BaseModelType


class RelationshipCrawlFn(Protocol):
    @staticmethod
    def __call__(
        *,
        model_class: type[BaseModelType],
        field: BaseFieldType | None,
        field_name: str,
        reverse_path: str | Literal[False],
        forward_path: str,
        reverse: bool,
        operator: None | str,
        cross_db_remainder: str,
        last_cross_db_remainder: str,
    ) -> None:
        """Callback hint."""
