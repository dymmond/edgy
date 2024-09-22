import re
from typing import TYPE_CHECKING, Any, Callable, Dict, FrozenSet, Tuple, Type, Union, cast

from edgy.core.db.models.metaclasses import BaseModelMeta, MetaInfo

if TYPE_CHECKING:
    from sqlalchemy import Table


class AutoReflectionMetaInfo(MetaInfo):
    __slots__ = ("pattern", "template", "databases")
    pattern: re.Pattern
    template: Callable[["Table"], str]
    databases: FrozenSet[Union[str, None]]

    def __init__(self, meta: Any = None, **kwargs: Any) -> None:
        self.pattern = getattr(meta, "pattern", None)
        self.template = getattr(meta, "template", None)
        self.databases = getattr(meta, "databases", (None,))

        super().__init__(meta, **kwargs)

    def load_dict(self, values: Dict[str, Any]) -> None:
        super().load_dict(values)
        template: Any = self.template
        if template is None:

            def _(table: "Table") -> str:
                return f"{self.model.__name__}{table.name}"

            self.template = _
        elif isinstance(template, str):

            def _(table: "Table") -> str:
                return template.format(tablename=table.name, model_class=self.model)

            self.template = _

        pattern: Any = self.pattern
        if not pattern:
            pattern = ".*"
        if isinstance(pattern, str):
            self.pattern = re.compile(pattern)

        self.databases = frozenset(cast(Any, self.databases))


class AutoReflectionMeta(BaseModelMeta):
    def __new__(
        cls, name: str, bases: Tuple[Type, ...], attrs: Dict[str, Any], **kwargs: Any
    ) -> Any:
        new_model = super().__new__(cls, name, bases, attrs, skip_registry=True, **kwargs)
        new_model.meta = AutoReflectionMetaInfo(new_model.meta)
        if not new_model.meta.is_abstract and new_model.meta.registry is not None:
            new_model.meta.registry.pattern_models[new_model.__name__] = new_model
        return new_model
