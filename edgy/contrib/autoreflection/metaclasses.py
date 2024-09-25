import re
from typing import TYPE_CHECKING, Any, Callable, Dict, FrozenSet, Tuple, Type, Union, cast

from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo

if TYPE_CHECKING:
    from sqlalchemy import Table


class AutoReflectionMetaInfo(MetaInfo):
    __slots__ = ("pattern", "template", "databases", "concrete")
    pattern: re.Pattern
    template: Callable[["Table"], str]
    databases: FrozenSet[Union[str, None]]

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        self.concrete = getattr(meta, "concrete", False)
        self.pattern = getattr(meta, "pattern", None)
        self.template = getattr(meta, "template", None)
        self.databases = getattr(meta, "databases", (None,))  # type: ignore

        super().__init__(meta, **kwargs)

    def load_dict(self, values: Dict[str, Any]) -> None:
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

        pattern: Any = self.pattern
        if not pattern:
            pattern = ".*"
        if isinstance(pattern, str):
            self.pattern = re.compile(pattern)

        self.databases = frozenset(cast(Any, self.databases))


class AutoReflectionMeta(BaseModelMeta):
    def __new__(
        cls,
        name: str,
        bases: Tuple[Type, ...],
        attrs: Dict[str, Any],
        skip_registry: bool = False,
        **kwargs: Any,
    ) -> Any:
        new_model = super().__new__(
            cls,
            name,
            bases,
            attrs,
            meta_info_class=AutoReflectionMetaInfo,
            skip_registry=True,
            **kwargs,
        )
        if (
            not skip_registry
            and not new_model.meta.concrete
            and not new_model.meta.abstract
            and new_model.meta.registry is not None
        ):
            new_model.meta.registry.pattern_models[new_model.__name__] = new_model
        return new_model
