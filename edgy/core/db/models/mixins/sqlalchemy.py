from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

import sqlalchemy

from edgy.core.db.fields.base import RelationshipField
from edgy.core.db.fields.foreign_keys import BaseForeignKeyField
from edgy.core.db.fields.many_to_many import BaseManyToManyForeignKeyField
from edgy.core.db.fields.ref_foreign_key import BaseRefForeignKey
from edgy.core.db.relationships.related_field import RelatedField
from edgy.exceptions import ImproperlyConfigured

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType
    from edgy.core.db.models.model import Model

_missing = object()


class SQLAlchemyModelMixin:
    """
    Opt-in compatibility mixin that exposes SQLAlchemy Core columns as class attributes.

    By default, Edgy models require `Model.columns.<name>` for SQLAlchemy-style
    expressions. This mixin enables a migration mode where class-level access can use
    field-like names directly:

    ```python
    import sqlalchemy
    import edgy

    class Workspace(edgy.SQLAlchemyModelMixin, edgy.StrictModel):
        id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
        name: str = edgy.CharField(max_length=255)

        class Meta:
            registry = ...

    stmt = sqlalchemy.select(Workspace.id).where(Workspace.id == 1)
    ```

    Key behavior:
    - The mode is explicit and per-model: only models inheriting this mixin are affected.
    - Instance attribute access is unchanged.
    - Relationship fields are not exposed as SQLAlchemy scalar columns.
    - Foreign key scalar aliases are exposed in SQLAlchemy-style form (`owner_id`).
    """

    __edgy_sqlalchemy_compatibility__: ClassVar[bool] = True

    @classmethod
    def _resolve_sqlalchemy_compatible_attribute(cls: type[Model], name: str) -> Any:
        """
        Resolve a class attribute name to a SQLAlchemy column for compatibility mode.

        Args:
            name: The class attribute being requested.

        Returns:
            A SQLAlchemy `Column` object when the name can be mapped.

        Raises:
            AttributeError: If no SQLAlchemy-compatible mapping exists for `name`.
            ImproperlyConfigured: If `name` refers to an unsupported or ambiguous field.
        """
        field = cls.meta.fields.get(name)
        if field is not None:
            return cls._resolve_sqlalchemy_field_column(name=name, field=field)

        column_key = cls._lookup_sqlalchemy_foreign_key_alias(name)
        if column_key is _missing:
            raise AttributeError(name)
        if column_key is None:
            raise ImproperlyConfigured(
                detail=(
                    f'Foreign key alias "{name}" is ambiguous on model "{cls.__name__}". '
                    "Use explicit SQLAlchemy columns via Model.columns."
                )
            )
        return cls._get_sqlalchemy_column_by_key(name=name, column_key=column_key)

    @classmethod
    def _resolve_sqlalchemy_field_column(
        cls: type[Model], *, name: str, field: BaseFieldType
    ) -> sqlalchemy.Column[Any]:
        """
        Resolve a model field name to a single SQLAlchemy column.

        Relationship/meta fields that do not map to a scalar table column raise an
        actionable configuration error.
        """
        if isinstance(field, BaseManyToManyForeignKeyField):
            raise ImproperlyConfigured(
                detail=(
                    f'Field "{name}" on "{cls.__name__}" is a many-to-many relation and does not '
                    "map to a scalar SQLAlchemy column."
                )
            )
        if isinstance(field, RelatedField):
            raise ImproperlyConfigured(
                detail=(
                    f'Field "{name}" on "{cls.__name__}" is a reverse relation and cannot be used '
                    "as a SQLAlchemy column expression."
                )
            )
        if isinstance(field, BaseRefForeignKey):
            raise ImproperlyConfigured(
                detail=(
                    f'Field "{name}" on "{cls.__name__}" is a RefForeignKey helper and does not '
                    "map to a SQLAlchemy table column."
                )
            )
        if isinstance(field, BaseForeignKeyField):
            aliases = cls._foreign_key_aliases_for_field(name)
            if aliases:
                aliases_str = ", ".join(f'"{alias}"' for alias in aliases)
                raise ImproperlyConfigured(
                    detail=(
                        f'Field "{name}" on "{cls.__name__}" is a relationship. '
                        f"Use foreign key column alias(es): {aliases_str}."
                    )
                )
            raise ImproperlyConfigured(
                detail=(
                    f'Field "{name}" on "{cls.__name__}" is a relationship and cannot be used as '
                    "a SQLAlchemy scalar column."
                )
            )
        if isinstance(field, RelationshipField):
            raise ImproperlyConfigured(
                detail=(
                    f'Field "{name}" on "{cls.__name__}" is a relationship and cannot be used as '
                    "a SQLAlchemy scalar column."
                )
            )

        columns = tuple(cls.meta.get_columns_for_name(name))
        if not columns:
            raise ImproperlyConfigured(
                detail=(
                    f'Field "{name}" on "{cls.__name__}" does not define SQLAlchemy columns and '
                    "cannot be used in SQLAlchemy Core expressions."
                )
            )
        if len(columns) != 1:
            columns_str = ", ".join(f'"{column.key}"' for column in columns)
            raise ImproperlyConfigured(
                detail=(
                    f'Field "{name}" on "{cls.__name__}" maps to multiple SQLAlchemy columns '
                    f"({columns_str}). Use a concrete column name."
                )
            )
        return cast(
            sqlalchemy.Column[Any],
            cls._get_sqlalchemy_column_by_key(name=name, column_key=columns[0].key),
        )

    @classmethod
    def _lookup_sqlalchemy_foreign_key_alias(cls: type[Model], name: str) -> str | None | object:
        """
        Resolve `name` against generated foreign key scalar aliases.

        Returns:
            - `str`: the resolved table column key
            - `None`: alias exists but is ambiguous
            - `_missing`: no alias found
        """
        alias_map: dict[str, str | None] = {}

        for field_name in cls.meta.foreign_key_fields:
            field = cls.meta.fields[field_name]
            if not isinstance(field, BaseForeignKeyField):
                continue
            for alias, column_key in cls._iter_foreign_key_aliases(field_name, field):
                # Never shadow explicit model field names with compatibility aliases.
                if alias in cls.meta.fields:
                    continue
                existing = alias_map.get(alias, _missing)
                if existing is _missing:
                    alias_map[alias] = column_key
                elif existing != column_key:
                    alias_map[alias] = None

        return alias_map.get(name, _missing)

    @classmethod
    def _foreign_key_aliases_for_field(cls: type[Model], field_name: str) -> tuple[str, ...]:
        """
        Return deterministic alias names generated for a concrete foreign key field.
        """
        field = cls.meta.fields[field_name]
        if not isinstance(field, BaseForeignKeyField):
            return ()
        aliases = []
        for alias, _ in cls._iter_foreign_key_aliases(field_name, field):
            if alias not in aliases:
                aliases.append(alias)
        return tuple(aliases)

    @classmethod
    def _iter_foreign_key_aliases(
        cls: type[Model], field_name: str, field: BaseForeignKeyField
    ) -> tuple[tuple[str, str], ...]:
        """
        Produce SQLAlchemy compatibility alias -> real column key mappings.

        For a field like `owner` targeting `id`, this generates `owner_id`.
        """
        aliases: list[tuple[str, str]] = []
        for column in cls.meta.get_columns_for_name(field_name):
            translated = field.from_fk_field_name(field_name, column.key)
            aliases.append((f"{field_name}_{translated}", column.key))
        return tuple(aliases)

    @classmethod
    def _get_sqlalchemy_column_by_key(
        cls: type[Model], *, name: str, column_key: str
    ) -> sqlalchemy.Column[Any]:
        """
        Return a concrete table-bound SQLAlchemy column by key.
        """
        try:
            table = cls.table
        except AttributeError as exc:
            raise ImproperlyConfigured(
                detail=(
                    f'Cannot resolve "{name}" on model "{cls.__name__}" because no table is '
                    "available. Ensure the model is bound to a registry."
                )
            ) from exc

        try:
            return cast(sqlalchemy.Column[Any], table.columns[column_key])
        except KeyError as exc:
            raise ImproperlyConfigured(
                detail=(
                    f'Column key "{column_key}" for compatibility attribute "{name}" is not '
                    f'available on model "{cls.__name__}".'
                )
            ) from exc
