import re
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    Union,
    cast,
)

from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo

if TYPE_CHECKING:
    from sqlalchemy import Table


class AutoReflectionMetaInfo(MetaInfo):
    __slots__ = ("include_pattern", "exclude_pattern", "template", "databases", "schemes")
    include_pattern: re.Pattern
    exclude_pattern: Optional[re.Pattern]
    template: Callable[["Table"], str]
    databases: frozenset[Union[str, None]]
    schemes: frozenset[Union[str, None]]

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        self.include_pattern = getattr(meta, "include_pattern", None)
        self.exclude_pattern = getattr(meta, "exclude_pattern", None)
        self.template = getattr(meta, "template", None)
        self.databases = getattr(meta, "databases", (None,))  # type: ignore
        self.schemes = getattr(meta, "schemes", (None,))  # type: ignore

        super().__init__(meta, **kwargs)

    def load_dict(self, values: dict[str, Any]) -> None:
        super().load_dict(values)
        template: Any = self.template
        if template is None:
            template = "{modelname}{tablename}"
        if isinstance(template, str):

            def _(table: "Table") -> str:
                return template.format(
                    tablename=table.name, tablekey=table.key, modelname=self.model.__name__
                )

            self.template = _

        include_pattern: Any = self.include_pattern
        if not include_pattern:
            include_pattern = ".*"
        if isinstance(include_pattern, str):
            include_pattern = re.compile(include_pattern)
        self.include_pattern = include_pattern

        exclude_pattern: Any = self.exclude_pattern
        if not exclude_pattern:
            exclude_pattern = None
        if isinstance(exclude_pattern, str):
            exclude_pattern = re.compile(exclude_pattern)
        self.exclude_pattern = exclude_pattern

        self.databases = frozenset(cast(Any, self.databases))
        self.schemes = frozenset(cast(Any, (x if x else None for x in self.schemes)))


class AutoReflectionMeta(BaseModelMeta):
    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        attrs: dict[str, Any],
        skip_registry: bool = False,
        meta_info_class: type[AutoReflectionMetaInfo] = AutoReflectionMetaInfo,
        **kwargs: Any,
    ) -> Any:
        new_model = super().__new__(
            cls,
            name,
            bases,
            attrs,
            meta_info_class=meta_info_class,
            skip_registry=True,
            **kwargs,
        )
        if (
            not skip_registry
            and isinstance(new_model.meta, AutoReflectionMetaInfo)
            and not new_model.meta.abstract
            and new_model.meta.registry
        ):
            new_model.meta.registry.pattern_models[new_model.__name__] = new_model
        return new_model
