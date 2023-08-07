from typing import Any

import sqlalchemy


class QuerySetPropsMixin:
    """
    Properties used by the Queryset are placed in isolation
    for clean access and maintainance.
    """

    @property
    def database(self) -> Any:
        return self.model_class.meta.registry.database  # type: ignore

    @property
    def table(self) -> sqlalchemy.Table:
        return self.model_class.table  # type: ignore

    @property
    def pkname(self) -> Any:
        return self.model_class.pkname  # type: ignore

    @property
    def is_m2m(self) -> bool:
        return bool(self.model_class.meta.is_multi)

    @property
    def m2m_related(self) -> str:
        return self._m2m_related

    @m2m_related.setter
    def m2m_related(self, value: str) -> None:
        self._m2m_related = value
