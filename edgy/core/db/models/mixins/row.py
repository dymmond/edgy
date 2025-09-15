from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from edgy.core.db.fields.base import RelationshipField
from edgy.core.db.models.utils import apply_instance_extras
from edgy.core.db.querysets.prefetch import Prefetch, check_prefetch_collision
from edgy.core.db.relationships.utils import crawl_relationship
from edgy.exceptions import QuerySetError

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy import Table
    from sqlalchemy.engine.result import Row

    from edgy.core.connection import Database
    from edgy.core.db.models.model import Model
    from edgy.core.db.models.types import BaseModelType
    from edgy.core.db.querysets.types import reference_select_type


class ModelRowMixin:
    """
    Mixin class responsible for building and populating model instances from SQLAlchemy row
    results.

    This class provides methods to convert raw database rows into Edgy ORM model objects,
    handling relationships such as `select_related` and `prefetch_related`.
    """

    @classmethod
    def can_load_from_row(cls: type[Model], row: Row, table: Table) -> bool:
        """
        Checks if a model class can be instantiated and populated from a given SQLAlchemy row
        and table.

        This method verifies if the model's registry exists, if it's not an abstract model,
        and if all primary key columns for the model are present and not None in the
        provided row's mapping.

        Args:
            row (Row): The SQLAlchemy row object containing the data.
            table (Table): The SQLAlchemy table object associated with the row.

        Returns:
            bool: True if the model can be loaded from the row, False otherwise.
        """
        return bool(
            cls.meta.registry
            and not cls.meta.abstract
            and all(row._mapping.get(f"{table.name}_{col}") is not None for col in cls.pkcolumns)
        )

    @classmethod
    async def from_sqla_row(
        cls: type[Model],
        row: Row,
        tables_and_models: dict[str, tuple[Table, type[BaseModelType]]],
        select_related: Sequence[Any] | None = None,
        prefetch_related: Sequence[Prefetch] | None = None,
        only_fields: Sequence[str] | None = None,
        is_defer_fields: bool = False,
        exclude_secrets: bool = False,
        using_schema: str | None = None,
        database: Database | None = None,
        prefix: str = "",
        old_select_related_value: Model | None = None,
        reference_select: reference_select_type | None = None,
    ) -> Model | None:
        """
        Converts a SQLAlchemy `Row` object into an Edgy `Model` instance.

        This is a class method that processes a SQLAlchemy row, populating the model's
        fields, including handling `select_related` and `prefetch_related` relationships.
        It intelligently constructs the model instance by iterating through selected
        fields, managing prefixes for joined tables, and applying deferred or secret
        field exclusions.

        Args:
            row (Row): The SQLAlchemy row result to convert.
            tables_and_models (dict[str, tuple[Table, type[BaseModelType]]]): A dictionary
                mapping prefixes to tuples of SQLAlchemy Table objects and Edgy Model types,
                representing the tables and models involved in the query.
            select_related (Sequence[Any] | None): An optional sequence of relationship
                names to eager-load. These relationships will be joined in the main query.
            prefetch_related (Sequence[Prefetch] | None): An optional sequence of `Prefetch`
                objects for pre-fetching related data in separate queries.
            only_fields (Sequence[str] | None): An optional sequence of field names to
                include in the model instance. If specified, only these fields will be
                populated.
            is_defer_fields (bool): A boolean indicating whether fields are deferred. If
                True, the model instance will be a proxy model with deferred field loading.
            exclude_secrets (bool): A boolean indicating whether secret fields should be
                excluded from the populated model instance.
            using_schema (str | None): An optional schema name to use for the model.
            database (Database | None): An optional database instance to associate with
                the model.
            prefix (str): An optional prefix used for columns in the row mapping,
                typically for joined tables in `select_related`.
            old_select_related_value (Model | None): An optional existing model instance
                to update with the new row data, used in recursive `select_related` calls.
            reference_select (reference_select_type | None): An optional dictionary
                specifying how to map specific columns from the row to model fields,
                especially for aliased columns or complex selects.

        Returns:
            Model | None: A fully populated Edgy Model instance, or None if the model
            cannot be loaded from the row due to missing primary key values in joined
            relationships.

        Raises:
            QuerySetError: If a field specified in `select_related` does not exist on
                the model or is not a `RelationshipField`.
            NotImplementedError: If prefetching from other databases is attempted, as
                this feature is not yet supported.
        """
        # Initialize reference_select if not provided.
        _reference_select: reference_select_type = (
            reference_select if reference_select is not None else {}
        )
        item: dict[str, Any] = {}  # Dictionary to store the model's attributes.
        select_related = select_related or []
        prefetch_related = prefetch_related or []
        secret_columns: set[str] = set()

        # If exclude_secrets is True, gather all column names corresponding to secret fields.
        if exclude_secrets:
            for name in cls.meta.secret_fields:
                secret_columns.update(cls.meta.field_to_column_names[name])

        # Process select_related relationships.
        for related in select_related:
            field_name = related.split("__", 1)[0]
            try:
                field = cls.meta.fields[field_name]
            except KeyError:
                raise QuerySetError(
                    detail=f'Selected field "{field_name}cast("Model", " does not exist on {cls}.'
                ) from None

            if isinstance(field, RelationshipField):
                # Traverse the field to get the related model class and any remaining path.
                model_class, _, remainder = field.traverse_field(related)
            else:
                raise QuerySetError(
                    detail=f'Selected field "{field_name}" is not a RelationshipField on {cls}.'
                ) from None

            _prefix = field_name if not prefix else f"{prefix}__{field_name}"

            # If the related model cannot be loaded from the current row (e.g., all FKs
            # are None, indicating no join match), skip processing this relationship.
            if not model_class.can_load_from_row(
                row,
                tables_and_models[_prefix][0],
            ):
                continue

            # Get the nested reference_select for the current related field.
            reference_select_sub = _reference_select.get(field_name)
            if not isinstance(reference_select_sub, dict):
                reference_select_sub = {}

            if remainder:
                # Recursively call from_sqla_row for nested select_related.
                item[field_name] = await model_class.from_sqla_row(
                    row,
                    tables_and_models=tables_and_models,
                    select_related=[remainder],
                    prefetch_related=prefetch_related,
                    exclude_secrets=exclude_secrets,
                    is_defer_fields=is_defer_fields,
                    using_schema=using_schema,
                    database=database,
                    prefix=_prefix,
                    old_select_related_value=item.get(field_name),
                    reference_select=reference_select_sub,
                )
            else:
                # Call from_sqla_row for the direct related model.
                item[field_name] = await model_class.from_sqla_row(
                    row,
                    tables_and_models=tables_and_models,
                    exclude_secrets=exclude_secrets,
                    is_defer_fields=is_defer_fields,
                    using_schema=using_schema,
                    database=database,
                    prefix=_prefix,
                    old_select_related_value=item.get(field_name),
                    reference_select=reference_select_sub,
                )

        # If an `old_select_related_value` (an existing model instance) is provided,
        # update its attributes with the newly populated `item` and return it.
        if old_select_related_value:
            for k, v in item.items():
                setattr(old_select_related_value, k, v)
            return old_select_related_value

        table_columns = tables_and_models[prefix][0].columns

        # Populate the foreign key related names (lazy-loaded relationships).
        for related in cls.meta.foreign_key_fields:
            foreign_key = cls.meta.fields[related]

            # Determine if this related field should be ignored (e.g., if it's already
            # handled by select_related or is a secret field).
            ignore_related: bool = cls.__should_ignore_related_name(related, select_related)
            if ignore_related or related in cls.meta.secret_fields:
                continue
            if related in item:  # Skip if already populated by select_related.
                continue

            if exclude_secrets and foreign_key.secret:
                continue

            columns_to_check = foreign_key.get_column_names(related)
            model_related = foreign_key.target
            child_item = {}

            # Collect foreign key column values from the row mapping.
            for column_name in columns_to_check:
                column = getattr(table_columns, column_name, None)
                if column_name is None:
                    continue
                columnkeyhash = column_name
                if prefix:
                    columnkeyhash = f"{tables_and_models[prefix][0].name}_{column.key}"

                if columnkeyhash in row._mapping:
                    child_item[foreign_key.from_fk_field_name(related, column_name)] = (
                        row._mapping[columnkeyhash]
                    )

            # Process nested reference selects for the child model.
            reference_select_child = _reference_select.get(related)
            extra_no_trigger_child: set[str] = set()
            if isinstance(reference_select_child, dict):
                for (
                    reference_target_child,
                    reference_source_child,
                ) in cast("reference_select_type", reference_select_child).items():
                    if isinstance(reference_source_child, dict) or not reference_source_child:
                        continue
                    extra_no_trigger_child.add(reference_target_child)
                    if isinstance(reference_source_child, str):
                        reference_source_child_parts = reference_source_child.rsplit("__", 1)
                        if (
                            len(reference_source_child_parts) == 2
                            and reference_source_child_parts[0] in tables_and_models
                        ):
                            reference_source_child = (
                                f"{tables_and_models[reference_source_child_parts[0]][0].name}_"
                                f"{reference_source_child_parts[1]}"
                            )
                    child_item[reference_target_child] = row._mapping[reference_source_child]

            # Create a proxy model for the related field, representing a lazy-loaded
            # instance containing only the foreign key(s).
            proxy_model = model_related.proxy_model(**child_item)
            proxy_database = database if model_related.database is cls.database else None

            # Apply instance extras (schema, database, etc.) to the proxy model.
            # apply_instance_extras filters out table Alias
            proxy_model = apply_instance_extras(
                proxy_model,
                model_related,
                using_schema,
                database=proxy_database,
            )
            proxy_model.identifying_db_fields = foreign_key.related_columns
            proxy_model.__no_load_trigger_attrs__.update(extra_no_trigger_child)
            if exclude_secrets:
                proxy_model.__no_load_trigger_attrs__.update(model_related.meta.secret_fields)

            item[related] = proxy_model

        # Populate the regular column values for the main model.
        class_columns = cls.table.columns
        for column in table_columns:
            # Skip if only_fields is specified and the column is not in it.
            if (
                only_fields
                and prefix not in only_fields
                and (f"{prefix}__{column.key}" if prefix else column.key) not in only_fields
            ):
                continue
            if column.key in secret_columns:  # Skip if the column is a secret.
                continue
            if column.key not in class_columns:  # Skip if the column is not part of the model.
                continue
            if column.key in item:  # Skip if already populated (e.g., by select_related).
                continue
            columnkeyhash = column.key
            if prefix:
                columnkeyhash = f"{tables_and_models[prefix][0].name}_{columnkeyhash}"

            if columnkeyhash in row._mapping:
                item[column.key] = row._mapping[columnkeyhash]

        # Apply any explicit column mappings from `reference_select`.
        for reference_target_main, reference_source_main in _reference_select.items():
            if isinstance(reference_source_main, dict) or not reference_source_main:
                continue

            if isinstance(reference_source_main, str):
                reference_source_main_parts = reference_source_main.rsplit("__", 1)
                if (
                    len(reference_source_main_parts) == 2
                    and reference_source_main_parts[0] in tables_and_models
                ):
                    reference_source_main = (
                        f"{tables_and_models[reference_source_main_parts[0]][0].name}_"
                        f"{reference_source_main_parts[1]}"
                    )
            # Overwrite existing item with the value from reference_select.
            item[reference_target_main] = row._mapping[reference_source_main]

        # Instantiate the model (either as a proxy or a full model).
        model: Model = (
            cls.proxy_model(**item, __phase__="init_db")
            if exclude_secrets or is_defer_fields or only_fields
            else cls(**item, __phase__="init_db")
        )

        # Mark the model as fully loaded if no deferred or only_fields are active.
        if not is_defer_fields and not only_fields:
            model._db_deleted = False
            model._db_loaded = True

        # If excluding secrets, ensure these attributes do not trigger a load.
        if exclude_secrets:
            model.__no_load_trigger_attrs__.update(cls.meta.secret_fields)

        # Apply instance extras (schema, database, table, etc.) to the main model.
        # apply_instance_extras filters out table Alias
        model = apply_instance_extras(
            model,
            cls,
            using_schema,
            database=database,
            table=tables_and_models[prefix][0],
        )

        # Handle prefetch_related fields if specified.
        if prefetch_related:
            await cls.__handle_prefetch_related(
                row=row,
                prefix=prefix,
                model=model,
                tables_and_models=tables_and_models,
                prefetch_related=prefetch_related,
            )
        assert model.pk is not None, model  # Ensure the primary key is not None.
        return model

    @classmethod
    def __should_ignore_related_name(
        cls, related_name: str, select_related: Sequence[str]
    ) -> bool:
        """
        Determines whether a foreign key related name should be ignored during model
        population, typically if it's already covered by a `select_related` statement.

        Args:
            related_name (str): The name of the foreign key relationship.
            select_related (Sequence[str]): A sequence of strings representing the
                `select_related` relationships.

        Returns:
            bool: True if the related name should be ignored, False otherwise.
        """
        for related_field in select_related:
            fields = related_field.split("__")
            if related_name in fields:
                return True
        return False

    @classmethod
    def create_model_key_from_sqla_row(cls, row: Row, row_prefix: str = "") -> tuple:
        """
        Builds a unique cache key for a model instance based on its class name and
        primary key values extracted from a SQLAlchemy row.

        Args:
            row (Row): The SQLAlchemy row object from which to extract primary key values.
            row_prefix (str): An optional prefix for column names in the row mapping,
                used when dealing with joined tables.

        Returns:
            tuple: A tuple representing the unique key for the model instance.
        """
        pk_key_list: list[Any] = [cls.__name__]
        for attr in cls.pkcolumns:
            # Append the primary key value from the row to the key list.
            pk_key_list.append(str(row._mapping[f"{row_prefix}{attr}"]))
        return tuple(pk_key_list)

    @classmethod
    async def __set_prefetch(
        cls,
        row: Row,
        model: Model,
        row_prefix: str,
        related: Prefetch,
    ) -> None:
        """
        Sets a prefetched relationship on a model instance. This method handles the logic
        of retrieving and associating the prefetched data.

        Args:
            row (Row): The SQLAlchemy row from which the main model was constructed.
            model (Model): The Edgy Model instance to which the prefetched data will be
                attached.
            row_prefix (str): The prefix used for columns in the SQLAlchemy row,
                representing the main model's table.
            related (Prefetch): The Prefetch object specifying the relationship to prefetch.

        Raises:
            QuerySetError: If creating a reverse path is not possible (e.g., for
                unidirectional fields).
            NotImplementedError: If prefetching from other databases is attempted.
        """
        model_key = ()
        if related._is_finished:
            # If the prefetch operation is marked as finished (meaning all rows for this
            # prefetch have been collected), then bake the results. This allows for
            # efficient retrieval of prefetched data.
            await related.init_bake(type(model))
            model_key = model.create_model_key()

        # If the model's key exists in the baked results, retrieve and set the prefetched
        # data directly.
        if model_key in related._baked_results:
            setattr(model, related.to_attr, related._baked_results[model_key])
        else:
            # If not in baked results, or not finished, proceed with fetching.
            # Crawl the relationship path to get details about the related model and
            # reverse path.
            crawl_result = crawl_relationship(
                model.__class__, related.related_name, traverse_last=True
            )
            if crawl_result.reverse_path is False:
                raise QuerySetError(
                    detail="Creating a reverse path is not possible, unidirectional fields used."
                )
            if crawl_result.cross_db_remainder:
                raise NotImplementedError(
                    "Cannot prefetch from other db yet. Maybe in future this feature will be "
                    "added."
                )

            queryset = related.queryset
            if related._is_finished:
                assert queryset is not None, "Queryset is not set but _is_finished flag"
            else:
                # Check for potential conflicts with existing attributes on the model.
                check_prefetch_collision(model, related)
                if queryset is None:
                    # If no specific queryset is provided for prefetch, default to all.
                    queryset = crawl_result.model_class.query.all()

                # Ensure the reverse path is selected to link back to the main model.
                queryset = queryset.all()
                queryset._select_related.add(crawl_result.reverse_path)
                queryset._cached_select_related_expression = None

            # Construct the filter clause for the prefetched query using the main model's
            # primary key(s).
            clause = {
                f"{crawl_result.reverse_path}__{pkcol}": row._mapping[f"{row_prefix}{pkcol}"]
                for pkcol in cls.pkcolumns
            }
            # Execute the prefetched query and set the result on the model instance.
            setattr(model, related.to_attr, await queryset.filter(clause))

    @classmethod
    async def __handle_prefetch_related(
        cls,
        row: Row,
        model: Model,
        prefix: str,
        tables_and_models: dict[str, tuple[Table, type[BaseModelType]]],
        prefetch_related: Sequence[Prefetch],
    ) -> None:
        """
        Manages the execution of all `prefetch_related` queries for a given model instance.
        This method iterates through the specified prefetch relationships, checks for
        collisions, and initiates the asynchronous loading of related data.

        Args:
            row (Row): The SQLAlchemy row from which the main model was constructed.
            model (Model): The Edgy Model instance for which prefetch relationships are
                to be handled.
            prefix (str): The prefix used for columns in the SQLAlchemy row,
                representing the main model's table.
            tables_and_models (dict[str, tuple[Table, type[BaseModelType]]]): A dictionary
                mapping prefixes to tuples of SQLAlchemy Table objects and Edgy Model types,
                representing the tables and models involved in the query.
            prefetch_related (Sequence[Prefetch]): A sequence of `Prefetch` objects to
                process.

        Raises:
            QuerySetError: If a conflicting attribute is found that would be
                overwritten by a prefetch operation.
        """
        queries = []

        for related in prefetch_related:
            # Check for conflicting names early to prevent unexpected overwrites.
            check_prefetch_collision(model=model, related=related)
            row_prefix = f"{tables_and_models[prefix][0].name}_" if prefix else ""
            queries.append(
                cls.__set_prefetch(row=row, row_prefix=row_prefix, model=model, related=related)
            )
        # Execute all prefetch queries concurrently if there are any.
        if queries:
            await asyncio.gather(*queries)
