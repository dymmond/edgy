from __future__ import annotations

import asyncio
import warnings
from collections.abc import Iterable
from functools import partial
from inspect import Parameter, Signature, isawaitable
from itertools import islice
from typing import TYPE_CHECKING, Any, Optional, cast

import sqlalchemy

from edgy.core.db.fields.base import BaseField, BaseForeignKey
from edgy.core.db.models.types import BaseModelType
from edgy.core.db.relationships.utils import crawl_relationship

if TYPE_CHECKING:
    from edgy.core.connection.database import Database

    from .types import QuerySetType, tables_and_models_type

generic_field = BaseField()
_forbidden_param_kinds = frozenset([Parameter.KEYWORD_ONLY, Parameter.VAR_KEYWORD])


def is_callable_queryset_filter(inp: Any) -> bool:
    if getattr(inp, "_edgy_force_callable_queryset_filter", None) is not None:
        return cast(bool, inp._edgy_force_callable_queryset_filter)
    if not callable(inp):
        return False
    try:
        signature = Signature.from_callable(inp)
    except ValueError:
        return False
    if len(signature.parameters) < 2:
        return False
    return all(
        param.kind not in _forbidden_param_kinds
        for param in islice(signature.parameters.values(), 2)
    )


async def parse_clause_arg(
    arg: Any, instance: QuerySetType, tables_and_models: tables_and_models_type
) -> Any:
    if is_callable_queryset_filter(arg):
        arg = arg(instance, tables_and_models)
    if isawaitable(arg):
        arg = await arg
    return arg


async def parse_clause_args(
    args: Iterable[Any], queryset: QuerySetType, tables_and_models: tables_and_models_type
) -> list[Any]:
    result: list[Any] = []
    for arg in args:
        result.append(parse_clause_arg(arg, queryset, tables_and_models))
    if queryset.database.force_rollback:
        return [await el for el in result]
    else:
        return await asyncio.gather(*result)


def clean_query_kwargs(
    model_class: type[BaseModelType],
    kwargs: dict[str, Any],
    embed_parent: Optional[tuple[str, str]] = None,
    model_database: Optional[Database] = None,
) -> dict[str, Any]:
    new_kwargs: dict[str, Any] = {}
    for key, val in kwargs.items():
        if embed_parent:
            if embed_parent[1] and key.startswith(embed_parent[1]):
                key = key.removeprefix(embed_parent[1]).removeprefix("__")
            else:
                key = f"{embed_parent[0]}__{key}"
        sub_model_class, field_name, _, _, _, cross_db_remainder = crawl_relationship(
            model_class, key, model_database=model_database
        )
        # we preserve the uncleaned argument
        field = None if cross_db_remainder else sub_model_class.meta.fields.get(field_name)
        if field is not None and not callable(val):
            new_kwargs.update(field.clean(key, val, for_query=True))
        else:
            new_kwargs[key] = val
    assert "pk" not in new_kwargs, "pk should be already parsed"
    return new_kwargs


class _DefaultClausesHelper:
    def __init__(self, op: Any, default_empty: Any) -> None:
        self.op = op
        self.default_empty = default_empty

    def __call__(self, *args: Any) -> Any:
        # unpack, so there are no trues and falses or connectors without any relevance in the where query
        if len(args) == 0:
            return self.default_empty
        if len(args) == 1:
            return args[0]
        return self.op(*args)


def _calculate_select_related(queryset: QuerySetType, *, kwargs: dict[str, Any]) -> set[str]:
    select_related: set[str] = set()
    cleaned_kwargs = clean_query_kwargs(
        queryset.model_class,
        kwargs,
        queryset.embed_parent_filters,
        model_database=queryset.database,
    )
    for key in cleaned_kwargs:
        model_class, field_name, op, related_str, _, cross_db_remainder = crawl_relationship(
            queryset.model_class, key
        )
        if related_str:
            select_related.add(related_str)
    return select_related


def _calculate_select_related_sum(queryset: QuerySetType, *, callables: Iterable[Any]) -> set[str]:
    select_related: set[str] = set()
    for callab in callables:
        select_related.update(callab(queryset))
    return select_related


class _EnhancedClausesHelper:
    def __init__(self, op: Any) -> None:
        self.op = op

    def __call__(self, *args: Any, no_select_related: bool = False) -> Any:
        if all(not is_callable_queryset_filter(arg) and not isawaitable(arg) for arg in args):
            return self.op(*args)
        calculate_select_related_args: list[Any] = (
            []
            if no_select_related
            else [
                arg._edgy_calculate_select_related
                for arg in args
                if hasattr(arg, "_edgy_calculate_select_related")
            ]
        )

        async def wrapper(
            queryset: QuerySetType, tables_and_models: tables_and_models_type
        ) -> Any:
            return self.op(*(await parse_clause_args(args, queryset, tables_and_models)))

        wrapper._edgy_force_callable_queryset_filter = True
        if calculate_select_related_args:
            wrapper._edgy_calculate_select_related = partial(
                _calculate_select_related_sum, callables=calculate_select_related_args
            )
        return wrapper

    def from_kwargs(self, _: Any = None, /, **kwargs: Any) -> Any:
        # ignore first parameter for backward compatibility
        if _ is not None:
            warnings.warn(
                "`from_kwargs` doesn't use the passed positional table or model anymore.",
                DeprecationWarning,
                stacklevel=2,
            )

        async def wrapper(
            queryset: QuerySetType, tables_and_models: tables_and_models_type
        ) -> Any:
            clauses: list[Any] = []
            cleaned_kwargs = clean_query_kwargs(
                queryset.model_class,
                kwargs,
                queryset.embed_parent_filters,
                model_database=queryset.database,
            )

            for key, value in cleaned_kwargs.items():
                model_class, field_name, op, related_str, _, cross_db_remainder = (
                    crawl_relationship(queryset.model_class, key)
                )
                field = model_class.meta.fields.get(field_name, generic_field)
                if cross_db_remainder:
                    assert field is not generic_field
                    fk_field = cast(BaseForeignKey, field)
                    sub_query = (
                        fk_field.target.query.filter(**{cross_db_remainder: value})
                        .only(*fk_field.related_columns.keys())
                        .values_list(fields=fk_field.related_columns.keys())
                    )
                    table = tables_and_models[related_str][0]
                    fk_tuple = sqlalchemy.tuple_(
                        *(getattr(table.columns, colname) for colname in field.get_column_names())
                    )
                    clauses.append(fk_tuple.in_(await sub_query))
                else:
                    assert not isinstance(value, BaseModelType), (
                        f"should be parsed in clean: {key}: {value}"
                    )

                    value = await parse_clause_arg(value, queryset, tables_and_models)
                    table = tables_and_models[related_str][0]

                    clauses.append(field.operator_to_clause(field.name, op, table, value))
            return self.op(*clauses)

        wrapper._edgy_force_callable_queryset_filter = True

        if any("__" in key for key in kwargs):
            wrapper._edgy_calculate_select_related = partial(
                _calculate_select_related, kwargs=kwargs
            )

        return wrapper


or_sqlalchemy = _DefaultClausesHelper(sqlalchemy.or_, sqlalchemy.false())
or_sqlalchemy.__doc__ = """
    Creates a SQL Alchemy OR clause for the expressions being passed.
"""
and_sqlalchemy = _DefaultClausesHelper(sqlalchemy.and_, sqlalchemy.true())
and_sqlalchemy.__doc__ = """
    Creates a SQL Alchemy AND clause for the expressions being passed.
"""

or_ = _EnhancedClausesHelper(or_sqlalchemy)
or_.__doc__ = """
    Creates an edgy OR clause for the expressions being passed.
"""
and_ = _EnhancedClausesHelper(and_sqlalchemy)
and_.__doc__ = """
    Creates an edgy AND clause for the expressions being passed.
"""

# alias
Q = and_


def not_(clause: Any, *, no_select_related: bool = False) -> Any:
    """
    Creates a SQL Alchemy NOT clause for the expressions being passed.
    """
    if not is_callable_queryset_filter(clause) and not isawaitable(clause):
        return sqlalchemy.not_(clause)

    async def wrapper(queryset: QuerySetType, tables_and_models: tables_and_models_type) -> Any:
        return sqlalchemy.not_(await parse_clause_arg(clause, queryset, tables_and_models))

    wrapper._edgy_force_callable_queryset_filter = True
    if not no_select_related and hasattr(clause, "_edgy_calculate_select_related"):
        wrapper._edgy_calculate_select_related = clause._edgy_calculate_select_related

    return wrapper


__all__ = [
    "and_",
    "and_sqlalchemy",
    "or_",
    "or_sqlalchemy",
    "not_",
    "generic_field",
    "parse_clause_arg",
    "parse_clause_args",
    "clean_query_kwargs",
]
