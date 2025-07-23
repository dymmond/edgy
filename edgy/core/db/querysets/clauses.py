from __future__ import annotations

import asyncio
import warnings
from collections.abc import Iterable
from functools import partial
from inspect import Parameter, Signature, isawaitable
from itertools import islice
from typing import TYPE_CHECKING, Any, cast

import sqlalchemy

from edgy.core.db.fields.base import BaseField, BaseForeignKey
from edgy.core.db.models.types import BaseModelType
from edgy.core.db.relationships.utils import RelationshipCrawlResult, crawl_relationship

if TYPE_CHECKING:
    from edgy.core.connection.database import Database

    from .types import QuerySetType, tables_and_models_type

# An instance of BaseField used as a generic fallback.
generic_field = BaseField()
# A frozenset of parameter kinds that are forbidden for the first two arguments of a callable
# queryset filter.
_forbidden_param_kinds = frozenset([Parameter.KEYWORD_ONLY, Parameter.VAR_KEYWORD])


def is_callable_queryset_filter(inp: Any) -> bool:
    """
    Checks if an input is a callable suitable for a queryset filter.

    A callable is considered suitable if it meets the following criteria:
    1. It has a `_edgy_force_callable_queryset_filter` attribute set to a truthy value.
    2. It is a callable object.
    3. Its signature can be successfully inspected.
    4. It has at least two positional parameters.
    5. Its first two parameters are not keyword-only or variable keyword parameters.

    Args:
        inp (Any): The input to check for callable queryset filter suitability.

    Returns:
        bool: True if the input is a suitable callable filter, False otherwise.
    """
    # Check for a special attribute that forces it to be treated as a callable queryset filter.
    if getattr(inp, "_edgy_force_callable_queryset_filter", None) is not None:
        return cast(bool, inp._edgy_force_callable_queryset_filter)
    # If it's not callable, it cannot be a callable queryset filter.
    if not callable(inp):
        return False
    try:
        # Attempt to get the signature of the callable.
        signature = Signature.from_callable(inp)
    except ValueError:
        # If the signature cannot be obtained, it's not a suitable callable.
        return False
    # A suitable callable queryset filter must have at least two parameters.
    if len(signature.parameters) < 2:
        return False
    # Check if the first two parameters are not keyword-only or variable keyword.
    return all(
        param.kind not in _forbidden_param_kinds
        for param in islice(signature.parameters.values(), 2)
    )


async def parse_clause_arg(
    arg: Any, instance: QuerySetType, tables_and_models: tables_and_models_type
) -> Any:
    """
    Parses a single clause argument, handling callables and awaitables.

    If the argument is identified as a `is_callable_queryset_filter`, it is invoked
    with the `queryset` instance and `tables_and_models`. If the result of this
    invocation or the original argument itself is an awaitable, it is awaited.

    Args:
        arg (Any): The argument to be parsed. This can be a direct value, a callable
                   that acts as a queryset filter, or an awaitable.
        instance (QuerySetType): The queryset instance to be passed to callable filters.
        tables_and_models (tables_and_models_type): A dictionary mapping table aliases to
                                                    (table, model) tuples, also passed to
                                                    callable filters.

    Returns:
        Any: The parsed argument, with callables invoked and awaitables awaited.
    """
    # If the argument is a callable queryset filter, invoke it.
    if is_callable_queryset_filter(arg):
        arg = arg(instance, tables_and_models)
    # If the argument (or its result, if it was a callable) is awaitable, await it.
    if isawaitable(arg):
        arg = await arg
    return arg


async def parse_clause_args(
    args: Iterable[Any], queryset: QuerySetType, tables_and_models: tables_and_models_type
) -> list[Any]:
    """
    Parses an iterable of clause arguments asynchronously.

    Each argument in the `args` iterable is processed by `parse_clause_arg`. The
    execution strategy (sequential vs. concurrent) depends on the
    `queryset.database.force_rollback` flag. If `force_rollback` is True, arguments
    are awaited sequentially to ensure order and prevent potential transactional issues.
    Otherwise, they are awaited concurrently using `asyncio.gather` for performance.

    Args:
        args (Iterable[Any]): An iterable of arguments to be parsed.
        queryset (QuerySetType): The queryset instance, used to determine the database
                                  rollback strategy.
        tables_and_models (tables_and_models_type): A dictionary mapping table aliases to
                                                    (table, model) tuples, passed to
                                                    `parse_clause_arg`.

    Returns:
        list[Any]: A list containing the parsed results of all arguments.
    """
    result: list[Any] = []
    # Prepare all arguments for parsing, creating a list of awaitables.
    for arg in args:
        result.append(parse_clause_arg(arg, queryset, tables_and_models))
    # Await the results based on the force_rollback flag.
    if queryset.database.force_rollback:
        # Await sequentially if force_rollback is enabled.
        return [await el for el in result]
    else:
        # Await concurrently using asyncio.gather if force_rollback is disabled.
        return await asyncio.gather(*result)


def clean_query_kwargs(
    model_class: type[BaseModelType],
    kwargs: dict[str, Any],
    embed_parent: tuple[str, str] | None = None,
    model_database: Database | None = None,
) -> dict[str, Any]:
    """
    Cleans and normalizes query keyword arguments for a given model class.

    This function iterates through the provided `kwargs`, processes each key-value pair
    to align with the model's structure, and applies field-specific cleaning logic.
    It handles embedded parent filters by adjusting the key prefixes and uses
    `crawl_relationship` to identify the correct sub-model, field, and any related
    string for complex lookups (e.g., across relationships). Field values are cleaned
    using the `field.clean` method, ensuring consistency and proper formatting for
    database queries.

    Args:
        model_class (type[BaseModelType]): The base model class against which the
                                            `kwargs` are being applied.
        kwargs (dict[str, Any]): The raw keyword arguments for the query, potentially
                                 containing uncleaned values or complex lookup keys.
        embed_parent (tuple[str, str] | None): An optional tuple `(parent_alias, prefix)`
                                                used for handling filters on embedded
                                                parent models. If provided, `kwargs` keys
                                                starting with `prefix` are modified, and
                                                others are prefixed with `parent_alias`.
                                                Defaults to None.
        model_database (Database | None): The database instance to be used during
                                          `crawl_relationship` to resolve cross-database
                                          relationships. Defaults to None.

    Returns:
        dict[str, Any]: A new dictionary containing the cleaned and normalized keyword
                        arguments suitable for constructing a SQLAlchemy query.

    Raises:
        AssertionError: If the key "pk" is found in the `new_kwargs` after cleaning.
                        This is an internal consistency check to ensure that "pk"
                        has been properly handled or transformed earlier in the process.
    """
    new_kwargs: dict[str, Any] = {}
    for key, val in kwargs.items():
        # Handle embedded parent filters by adjusting the key.
        if embed_parent:
            # If a prefix is defined and the key starts with it, remove the prefix.
            if embed_parent[1] and key.startswith(embed_parent[1]):
                key = key.removeprefix(embed_parent[1]).removeprefix("__")
            else:
                # Otherwise, prepend the parent alias to the key.
                key = f"{embed_parent[0]}__{key}"
        # Crawl the relationship to find the relevant sub_model_class, field_name,
        # operator, related_string, and cross-database remainder.
        sub_model_class, field_name, _, _, _, cross_db_remainder = crawl_relationship(
            model_class, key, model_database=model_database
        )
        # Determine the field; if there's a cross-database remainder, the field is None,
        # otherwise, get the field from the sub_model_class's meta.fields.
        field = None if cross_db_remainder else sub_model_class.meta.fields.get(field_name)
        # Clean the field value if a field is found and the value is not callable.
        if field is not None and not callable(val):
            # Update new_kwargs with the cleaned key-value pair(s).
            new_kwargs.update(field.clean(key, val, for_query=True))
        else:
            # If no specific field cleaning is applied, keep the original key and value.
            new_kwargs[key] = val
    # Assert that "pk" is not present in the cleaned kwargs, indicating it should have
    # been processed or transformed elsewhere.
    assert "pk" not in new_kwargs, "pk should be already parsed"
    return new_kwargs


def clean_path_to_crawl_result(
    model_class: type[BaseModelType],
    path: str,
    embed_parent: tuple[str, str] | None = None,
    model_database: Database | None = None,
) -> RelationshipCrawlResult:
    if embed_parent:
        # If a prefix is defined and the key starts with it, remove the prefix.
        if embed_parent[1] and path.startswith(embed_parent[1]):
            path = path.removeprefix(embed_parent[1]).removeprefix("__")
        else:
            # Otherwise, prepend the parent alias to the key.
            path = f"{embed_parent[0]}__{path}"
    # Crawl the relationship to find the relevant sub_model_class, field_name,
    # operator, related_string, and cross-database remainder.
    crawl_result = crawl_relationship(model_class, path, model_database=model_database)
    if crawl_result.operator != "exact":
        raise ValueError("Cannot select operators here.")
    return crawl_result


class _DefaultClausesHelper:
    """
    Helper class for creating default SQLAlchemy clauses (e.g., AND, OR) with
    specific behaviors for empty or single argument lists.

    This class simplifies the creation of boolean conjunctions or disjunctions
    by providing a `__call__` method that intelligently handles the number of
    arguments, returning a default empty value (like `sqlalchemy.true()` or
    `sqlalchemy.false()`) when no arguments are given, or the argument itself
    when only one is provided, before applying the specified SQLAlchemy operator.
    """

    def __init__(self, op: Any, default_empty: Any) -> None:
        """
        Initializes the `_DefaultClausesHelper` with a specific SQLAlchemy operator
        and a default value for empty argument lists.

        Args:
            op (Any): The SQLAlchemy operator function to apply (e.g., `sqlalchemy.and_`,
                      `sqlalchemy.or_`). This function is expected to take multiple
                      expressions as arguments and combine them into a single clause.
            default_empty (Any): The SQLAlchemy expression to return when no arguments
                                 are provided to the `__call__` method (e.g.,
                                 `sqlalchemy.true()` for AND, `sqlalchemy.false()` for OR).
        """
        self.op = op
        self.default_empty = default_empty

    def __call__(self, *args: Any) -> Any:
        """
        Creates an SQLAlchemy clause by combining the given arguments using the
        initialized operator (`self.op`).

        This method provides convenient handling for various argument counts:
        - If no arguments are provided, it returns `self.default_empty`.
        - If exactly one argument is provided, it returns that argument directly,
          avoiding unnecessary wrapping by the operator.
        - If multiple arguments are provided, it applies `self.op` to all of them.

        Args:
            *args (Any): Variable positional arguments representing the expressions
                         to be combined into a clause. These can be SQLAlchemy expressions
                         or other suitable filter conditions.

        Returns:
            Any: The combined SQLAlchemy clause. This could be `self.default_empty`,
                 a single argument, or the result of `self.op` applied to multiple arguments.
        """
        # Return the default empty value if no arguments are provided.
        if len(args) == 0:
            return self.default_empty
        # If only one argument, return it directly without applying the operator.
        if len(args) == 1:
            return args[0]
        # For multiple arguments, apply the operator to combine them.
        return self.op(*args)


def _calculate_select_related(queryset: QuerySetType, *, kwargs: dict[str, Any]) -> set[str]:
    """
    Calculates the set of `select_related` paths required based on the provided
    query keyword arguments.

    This function analyzes the `kwargs` to identify any keys that represent
    relationships (i.e., contain "__") and extracts the base relationship path.
    It uses `clean_query_kwargs` to preprocess the `kwargs` and `crawl_relationship`
    to properly identify the relationship string. The unique relationship paths are
    then collected into a set, which indicates which related models need to be
    eagerly loaded to fulfill the query.

    Args:
        queryset (QuerySetType): The queryset instance, used to access the model class
                                  and embedded parent filters.
        kwargs (dict[str, Any]): The dictionary of keyword arguments representing the
                                 filter conditions for the query.

    Returns:
        set[str]: A set of unique string paths representing the relationships
                  that should be eagerly loaded using `select_related`.
    """
    select_related: set[str] = set()
    # Clean the query kwargs, which also helps in normalizing relationship paths.
    cleaned_kwargs = clean_query_kwargs(
        queryset.model_class,
        kwargs,
        queryset.embed_parent_filters,
        model_database=queryset.database,
    )
    # Iterate through the cleaned kwargs to identify relationship paths.
    for key in cleaned_kwargs:
        # Crawl the relationship for each key to get detailed information, including related_str.
        _, _, _, related_str, _, _ = crawl_relationship(queryset.model_class, key)
        # If a related_str is found, it means this key involves a relationship, so add it.
        if related_str:
            select_related.add(related_str)
    return select_related


def _calculate_select_related_sum(queryset: QuerySetType, *, callables: Iterable[Any]) -> set[str]:
    """
    Aggregates `select_related` paths from multiple callable arguments.

    This function iterates through a list of callables, typically those that
    represent complex filter conditions. For each callable, it checks if it
    has a `_edgy_calculate_select_related` attribute. If present, this attribute
    is expected to be another callable (e.g., a `partial` function) that, when
    invoked with the `queryset`, returns a set of `select_related` paths.
    All such sets are combined into a single, comprehensive set.

    Args:
        queryset (QuerySetType): The queryset instance to be passed to the
                                  `_edgy_calculate_select_related` callable.
        callables (Iterable[Any]): An iterable of callable objects, each potentially
                                   contributing `select_related` paths.

    Returns:
        set[str]: A combined set of unique relationship paths that need to be
                  eagerly loaded based on all provided callables.
    """
    select_related: set[str] = set()
    # Iterate through each callable in the provided list.
    for callab in callables:
        # Check if the callable has the special attribute for calculating select_related.
        if hasattr(callab, "_edgy_calculate_select_related"):
            # Invoke the _edgy_calculate_select_related callable with the queryset
            # and update the main select_related set with its results.
            select_related.update(callab(queryset))
    return select_related


class _EnhancedClausesHelper:
    """
    Helper class for creating enhanced SQLAlchemy clauses that support asynchronous
    and callable filter arguments, and integrate `select_related` calculation.

    This class extends the basic clause helper by allowing filter arguments to be
    either direct values, awaitable values, or special callable queryset filters.
    It handles the asynchronous parsing of these arguments and can also dynamically
    determine which related models should be eagerly loaded (`select_related`)
    based on the structure of the filter conditions, especially when dealing with
    related field lookups (e.g., 'relationship__field').
    """

    def __init__(self, op: Any) -> None:
        """
        Initializes the `_EnhancedClausesHelper` with a specific SQLAlchemy operator.

        Args:
            op (Any): The SQLAlchemy operator function to apply (e.g., `sqlalchemy.and_`,
                      `sqlalchemy.or_`). This operator will be used to combine the parsed
                      expressions into a single clause.
        """
        self.op = op

    def __call__(self, *args: Any, no_select_related: bool = False) -> Any:
        """
        Creates an enhanced SQLAlchemy clause from the given arguments, supporting
        asynchronous parsing and `select_related` inference.

        If all arguments are direct (not callable queryset filters or awaitables),
        they are combined immediately using `self.op`. Otherwise, it creates an
        asynchronous `wrapper` function. This `wrapper` will parse the arguments
        asynchronously using `parse_clause_args` before applying `self.op`.

        The `wrapper` is marked with `_edgy_force_callable_queryset_filter` to ensure
        it's treated as a special filter callable. If `no_select_related` is False,
        it also aggregates `_edgy_calculate_select_related` callables from its
        arguments into its own `_edgy_calculate_select_related` attribute, allowing
        for cascading `select_related` calculation.

        Args:
            *args (Any): Variable positional arguments representing the filter
                         conditions. These can be direct SQLAlchemy expressions,
                         awaitables, or callable queryset filters.
            no_select_related (bool): If True, skips the aggregation of
                                      `_edgy_calculate_select_related` attributes
                                      from the arguments. Defaults to False.

        Returns:
            Any: The combined SQLAlchemy clause. This can be a direct SQLAlchemy
                 expression or an asynchronous callable wrapper that resolves to
                 an SQLAlchemy expression.
        """
        # If none of the arguments are callable queryset filters or awaitables,
        # combine them directly using the operator.
        if all(not is_callable_queryset_filter(arg) and not isawaitable(arg) for arg in args):
            return self.op(*args)

        # Collect `_edgy_calculate_select_related` callables from arguments if
        # `no_select_related` is False.
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
            """
            Asynchronous wrapper function that parses arguments and applies the operator.
            """
            # Parse all arguments asynchronously and then apply the operator to their results.
            return self.op(*(await parse_clause_args(args, queryset, tables_and_models)))

        # Mark the wrapper as a force-callable queryset filter.
        wrapper._edgy_force_callable_queryset_filter = True
        # If there are select_related calculation arguments, attach a combined partial
        # to the wrapper.
        if calculate_select_related_args:
            wrapper._edgy_calculate_select_related = partial(
                _calculate_select_related_sum, callables=calculate_select_related_args
            )
        return wrapper

    def from_kwargs(self, _: Any = None, /, **kwargs: Any) -> Any:
        """
        Creates an enhanced SQLAlchemy clause from keyword arguments.

        This method is designed to dynamically build a `WHERE` clause from a
        dictionary of keyword arguments. It supports complex lookups, including
        traversal of relationships and handling of cross-database relationships.
        For each `key: value` pair in `kwargs`, it determines the corresponding
        model field and constructs the appropriate SQLAlchemy clause using the
        field's operator mapping.

        The method returns an asynchronous callable `wrapper`. This `wrapper`
        will clean the `kwargs`, parse individual argument values (handling
        awaitables), and then construct the SQLAlchemy clause. It also attaches
        a `_edgy_force_callable_queryset_filter` flag and a
        `_edgy_calculate_select_related` partial (if needed for relationship
        lookups) to the wrapper for proper integration with query sets.

        Args:
            _ (Any): An ignored positional argument. This is kept for backward
                     compatibility to absorb an unused `table_or_model` argument
                     that might have been passed in older versions.
            **kwargs (Any): Arbitrary keyword arguments where keys represent
                            field names (potentially with relationship lookups
                            like `field__relation__subfield`) and values are
                            the filter conditions.

        Returns:
            Any: An asynchronous callable that, when awaited, resolves to the
                 final SQLAlchemy clause representing the filter conditions.

        Warns:
            DeprecationWarning: If a positional argument is passed to this method.
        """
        # Warn if a positional argument is passed for backward compatibility reasons.
        if _ is not None:
            warnings.warn(
                "`from_kwargs` doesn't use the passed positional table or model anymore.",
                DeprecationWarning,
                stacklevel=2,
            )

        async def wrapper(
            queryset: QuerySetType, tables_and_models: tables_and_models_type
        ) -> Any:
            """
            Asynchronous wrapper to build the SQLAlchemy clause from kwargs.
            """
            clauses: list[Any] = []
            # Clean and normalize the query keyword arguments.
            cleaned_kwargs = clean_query_kwargs(
                queryset.model_class,
                kwargs,
                queryset.embed_parent_filters,
                model_database=queryset.database,
            )

            for key, value in cleaned_kwargs.items():
                # Crawl the relationship to get the model_class, field_name, operator,
                # related_string, and cross-database remainder.
                model_class, field_name, op, related_str, _, cross_db_remainder = (
                    crawl_relationship(queryset.model_class, key)
                )
                # Get the field from the model's meta fields, or use generic_field as fallback.
                field = model_class.meta.fields.get(field_name, generic_field)
                # Handle cross-database relationships.
                if cross_db_remainder:
                    # Assert that a specific field (not generic_field) must be found for FK.
                    assert field is not generic_field
                    # Cast to BaseForeignKey for type-specific access.
                    fk_field = cast(BaseForeignKey, field)
                    # Construct a subquery to fetch related primary keys.
                    sub_query = (
                        fk_field.target.query.filter(**{cross_db_remainder: value})
                        .only(*fk_field.related_columns.keys())
                        .values_list(fields=fk_field.related_columns.keys())
                    )
                    # Get the table from tables_and_models using the related string.
                    table = tables_and_models[related_str][0]
                    # Create an SQLAlchemy tuple for the foreign key columns.
                    fk_tuple = sqlalchemy.tuple_(
                        *(getattr(table.columns, colname) for colname in field.get_column_names())
                    )
                    # Add an "IN" clause using the subquery result.
                    clauses.append(fk_tuple.in_(await sub_query))
                else:
                    # Ensure that BaseModelType instances are parsed in clean_query_kwargs.
                    assert not isinstance(value, BaseModelType), (
                        f"should be parsed in clean: {key}: {value}"
                    )

                    # Parse the argument, handling callables and awaitables.
                    value = await parse_clause_arg(value, queryset, tables_and_models)
                    # Get the table from tables_and_models using the related string.
                    table = tables_and_models[related_str][0]

                    # Add the field's operator clause to the list of clauses.
                    clauses.append(field.operator_to_clause(field.name, op, table, value))
            # Combine all generated clauses using the initialized operator.
            return self.op(*clauses)

        # Mark the wrapper as a force-callable queryset filter.
        wrapper._edgy_force_callable_queryset_filter = True

        # If any key contains "__", it suggests a relationship lookup, so
        # attach a select_related calculation partial.
        if any("__" in key for key in kwargs):
            wrapper._edgy_calculate_select_related = partial(
                _calculate_select_related, kwargs=kwargs
            )

        return wrapper


# Instance of _DefaultClausesHelper for SQLAlchemy OR operation.
or_sqlalchemy = _DefaultClausesHelper(sqlalchemy.or_, sqlalchemy.false())
or_sqlalchemy.__doc__ = """
    Creates a SQL Alchemy OR clause for the expressions being passed.
    Returns `sqlalchemy.false()` if no expressions are passed.
"""
# Instance of _DefaultClausesHelper for SQLAlchemy AND operation.
and_sqlalchemy = _DefaultClausesHelper(sqlalchemy.and_, sqlalchemy.true())
and_sqlalchemy.__doc__ = """
    Creates a SQL Alchemy AND clause for the expressions being passed.
    Returns `sqlalchemy.true()` if no expressions are passed.
"""

# Instance of _EnhancedClausesHelper for Edgy OR operation.
or_ = _EnhancedClausesHelper(or_sqlalchemy)
or_.__doc__ = """
    Creates an edgy OR clause for the expressions being passed.
    This supports asynchronous functions and `select_related` inference.
"""
# Instance of _EnhancedClausesHelper for Edgy AND operation.
and_ = _EnhancedClausesHelper(and_sqlalchemy)
and_.__doc__ = """
    Creates an edgy AND clause for the expressions being passed.
    This supports asynchronous functions and `select_related` inference.
"""

# Alias for `and_`, commonly used in query building.
Q = and_


def not_(clause: Any, *, no_select_related: bool = False) -> Any:
    """
    Creates a SQL Alchemy NOT clause for the expressions being passed.

    This function wraps the `sqlalchemy.not_` operator and can handle
    asynchronous and callable clauses. It ensures that if the input `clause`
    is itself a special filter callable or an awaitable, it will be properly
    parsed before negation. It also propagates `select_related` information
    from the original clause if `no_select_related` is False.

    Args:
        clause (Any): The expression or callable/awaitable to be negated.
                      This can be a direct SQLAlchemy expression, a callable
                      queryset filter, or an awaitable.
        no_select_related (bool): If True, the `_edgy_calculate_select_related`
                                  attribute will not be propagated from the
                                  original `clause`. Defaults to False.

    Returns:
        Any: The negated SQLAlchemy clause. This can be a direct `sqlalchemy.not_`
             expression or an asynchronous callable wrapper that resolves to a
             negated SQLAlchemy expression.
    """
    # If the clause is not a callable queryset filter and not awaitable, negate it directly.
    if not is_callable_queryset_filter(clause) and not isawaitable(clause):
        return sqlalchemy.not_(clause)

    async def wrapper(queryset: QuerySetType, tables_and_models: tables_and_models_type) -> Any:
        """
        Asynchronous wrapper for negating a clause that might be callable or awaitable.
        """
        # Parse the clause argument asynchronously and then apply the NOT operator.
        return sqlalchemy.not_(await parse_clause_arg(clause, queryset, tables_and_models))

    # Mark the wrapper as a force-callable queryset filter.
    wrapper._edgy_force_callable_queryset_filter = True
    # If select_related calculation is not suppressed and the original clause has
    # the attribute, propagate it to the wrapper.
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
    "Q",
]
