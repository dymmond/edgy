from __future__ import annotations

import asyncio
from collections.abc import Sequence
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel

from edgy.core.db.fields.base import RelationshipField
from edgy.core.db.querysets.bulk import BulkOperation
from edgy.core.db.querysets.clauses import and_, or_
from edgy.exceptions import (
    ObjectNotFound,
    RelationshipIncompatible,
    RelationshipNotFound,
    SkipOperation,
)
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:
    from edgy import QuerySet
    from edgy.core.db.models.types import BaseModelType


class ManyRelation(ManyRelationProtocol):
    """
    Manages a many-to-many relationship between two models, typically via a
    `through` model. This class provides an interface for querying, adding,
    and removing related instances. It implements the `ManyRelationProtocol`,
    allowing it to be used as a descriptor on model fields.
    """

    def __init__(
        self,
        *,
        from_foreign_key: str,
        to_foreign_key: str,
        to: type[BaseModelType],
        through: type[BaseModelType],
        reverse: bool = False,
        embed_through: Literal[False] | str = "",
        refs: Any = (),
        instance: BaseModelType | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initializes a ManyRelation instance.

        Args:
            from_foreign_key (str): The name of the foreign key in the `through`
                                    model that points to the 'from' model
                                    (the model owning this relationship).
            to_foreign_key (str): The name of the foreign key in the `through`
                                  model that points to the 'to' model
                                  (the related model).
            to (type[BaseModelType]): The model class that is on the 'many' side
                                      of the relationship.
            through (type[BaseModelType]): The intermediate model class that
                                           defines the many-to-many relationship.
            reverse (bool): A flag indicating if this is the reverse side of the
                            relationship. Defaults to False.
            embed_through (Literal[False] | str): Specifies how to embed the
                                                  'through' model in queries.
                                                  Can be False or a string path.
                                                  Defaults to "".
            refs (Any): Initial references to related objects to be staged.
                        Can be a single instance or a sequence of instances.
                        Defaults to an empty tuple.
            instance (BaseModelType | None): The current instance of the model
                                             that owns this relationship.
                                             Defaults to None.
            **kwargs (Any): Additional keyword arguments passed to the
                            `ManyRelationProtocol` constructor.
        """
        super().__init__(**kwargs)
        self.through = through
        self.to = to
        self.instance = instance
        self.reverse = reverse
        self.from_foreign_key = from_foreign_key
        self.to_foreign_key = to_foreign_key
        self.embed_through = embed_through
        self.refs: list[BaseModelType] = []  # Initialize refs as a list
        # Ensure refs is a sequence; if not, wrap it in a list.
        if not isinstance(refs, Sequence):
            refs = [refs]
        # Stage the initial references.
        self.stage(*refs)

    @cached_property
    def _shared_relation_signals_params(self) -> dict:
        fk_to_defining_model = self.through.meta.fields[
            self.to_foreign_key if self.reverse else self.from_foreign_key
        ]
        fk_defining_model = fk_to_defining_model.target.meta.fields[
            fk_to_defining_model.reverse_name
        ]
        return {
            "target": fk_defining_model.owner if self.reverse else fk_defining_model.target,
            "source": fk_defining_model.target if self.reverse else fk_defining_model.owner,
            "field": fk_defining_model.related_name if self.reverse else fk_defining_model.name,
            "relation": "many_to_many",
        }

    def get_queryset(self) -> QuerySet:
        """
        Returns a `QuerySet` for fetching related instances through the `through` model.
        This queryset is pre-filtered to include only instances related to the
        current `instance` and configured for embedding.

        Returns:
            QuerySet: A queryset for the related model through the intermediate table.

        Raises:
            AssertionError: If the `instance` is not initialized.
        """
        # Retrieve the queryset from the 'through' model's query_related manager.
        # This ensures tenant checks are performed on every request.
        queryset = self.through.meta.managers["query_related"].get_queryset()
        # Assert that the current instance is available.
        assert self.instance, "instance not initialized"

        # Get the foreign key field on the 'through' model that points back to the 'from' model.
        fk = self.through.meta.fields[self.from_foreign_key]
        query = {}
        # Construct the filter query using the related columns of the foreign key.
        for related_name in fk.related_columns:
            # Use getattr to get the value from the current instance for each related column.
            query[related_name] = getattr(self.instance, related_name)
        # Apply the filter to the queryset using the foreign key and the constructed query.
        queryset = queryset.filter(**{self.from_foreign_key: query})

        # Set the embed_parent attribute on the queryset for embedding the 'to' model.
        # If embed_through is an empty string, it defaults to False.
        queryset.embed_parent = (self.to_foreign_key, self.embed_through or "")
        # If embed_through is not "",  use modern logic.
        if self.embed_through != "":
            queryset.embed_parent_filters = queryset.embed_parent
        if self.reverse:
            if not fk.is_cross_db():
                # not initialized yet
                queryset._select_related.add(self.from_foreign_key)
        else:
            if not self.through.meta.fields[self.to_foreign_key].is_cross_db():
                # not initialized yet
                queryset._select_related.add(self.to_foreign_key)
        return queryset.using(schema=self.instance.get_active_instance_schema())

    async def save_related(self) -> None:
        """
        Asynchronously saves all staged related instances to the database.
        This method iterates through the `refs` (staged children) and adds them
        to the relationship.
        """
        refs = list(self.refs)
        self.refs.clear()
        if not refs:
            return
        operation = BulkOperation(
            owner=self.get_queryset(),
            unique_columns={
                col
                for field in [self.from_foreign_key, self.to_foreign_key]
                for col in self.through.meta.field_to_column_names[field]
            },
            ignore_create_conflicts=True,
            signal_models=[
                self._shared_relation_signals_params["source"],
                self._shared_relation_signals_params["target"],
                self.through,
            ],
            signal_postfix="relation_add",
            signal_params={"operation": "save_related", **self._shared_relation_signals_params},
            create=True,
            retrieve=False,
            update=False,
            used_instance=self.instance,
            resolve_embed=False,
        )
        await operation.prepare(refs)
        try:
            await operation.send_pre_signal()
        except SkipOperation:
            operation.signal_params["row_count"] = 0
            operation.signal_params["row_count_create"] = 0
            await operation.send_post_signal()
            return
        await operation.apply_db()
        # no cache update because the queryset is temporarysignal
        # both parameters are the same here
        operation.signal_params["row_count"] = operation.signal_params.get("row_count_create")
        await operation.send_post_signal()

    def __getattr__(self, item: Any) -> Any:
        """
        Retrieves an attribute. If the attribute is not found directly on the
        `ManyRelation` instance, it first attempts to get it from the `QuerySet`
        returned by `get_queryset()`. If still not found, it then tries to get it
        from the `through` model class itself.

        Args:
            item (Any): The name of the attribute to retrieve.

        Returns:
            Any: The value of the retrieved attribute.

        Raises:
            AttributeError: If the attribute is not found on the queryset or the
                            `through` model.
        """
        try:
            # Attempt to get the attribute from the queryset.
            attr = getattr(self.get_queryset(), item)
        except AttributeError:
            # If not found on the queryset, attempt to get it from the 'through' model.
            attr = getattr(self.through, item)
        return attr

    def all(self, clear_cache: bool = False) -> QuerySet:
        """
        Returns a fresh `QuerySet` for all related instances.
        The `clear_cache` parameter is redundant here as `get_queryset()`
        always returns a new queryset.

        Args:
            clear_cache (bool): A flag (ignored) to indicate if the cache should be cleared.

        Returns:
            QuerySet: A queryset containing all related instances.
        """
        # get_queryset already returns a fresh queryset, so no need to make a copy.
        return self.get_queryset()

    def expand_relationship(self, value: Any) -> BaseModelType:
        """
        Expands a given value into an instance of the `through` model or its
        proxy model, preparing it for inclusion in the relationship. This
        handles cases where `value` might be the related `to` model or a dictionary.

        Args:
            value (Any): The value to expand, which can be an instance of the
                         `through` model, its proxy, the `to` model, its proxy,
                         or a dictionary.

        Returns:
            Any: An instance of the `through` model or its proxy, ready for use
                 in the relationship.
        """
        # Validate that the child is compatible with the relationship.
        if not isinstance(
            value,
            self.to | self.to.proxy_model | self.through | self.through.proxy_model | dict,
        ):
            raise RelationshipIncompatible(
                f"The child is not from the types '{self.to.__name__}', '{self.through.__name__}'."
            )
        through = self.through

        # If the value is already an instance of the through model or its proxy, return it directly.
        if isinstance(value, through | through.proxy_model):
            return value

        # Create a new proxy model instance of the 'through' model.
        # This instance links the current 'from' model instance with the 'to' model instance.
        instance = through.proxy_model(
            **{self.from_foreign_key: self.instance, self.to_foreign_key: value}
        )
        # Set identifying database fields for the 'through' model instance.
        instance.identifying_db_fields = tuple(
            col
            for field in [self.from_foreign_key, self.to_foreign_key]
            for col in through.meta.field_to_column_names[field]
        )
        # If the 'through' model is a tenant model, set the active schema for the instance.
        if getattr(through.meta, "is_tenant", False):
            instance.__using_schema__ = self.instance.get_active_instance_schema()  # type: ignore
        return instance

    def stage(self, *children: BaseModelType) -> None:
        """
        Stages one or more child instances to be added to the relationship.
        These instances are stored in an internal `refs` list and will be
        persisted when `save_related()` is called.

        Args:
            *children (BaseModelType): Variable number of child instances to stage.

        Raises:
            RelationshipIncompatible: If a child is not an instance of the
                                      `to` model, `through` model, or a dictionary.
        """
        for child in children:
            # Expand the child into a 'through' model instance and append it to refs.
            self.refs.append(self.expand_relationship(child))

    async def create(self, *args: Any, **kwargs: Any) -> BaseModelType | None:
        """
        Creates a new instance of the 'to' model and immediately adds it
        to the relationship.

        Args:
            *args (Any): Positional arguments to pass to the 'to' model constructor.
            **kwargs (Any): Keyword arguments to pass to the 'to' model constructor.

        Returns:
            BaseModelType | None: The newly created and added child instance, or None
                                  if it could not be added (e.g., due to integrity error).
        """
        # Create an instance of the 'to' model and then add it to the relationship.
        return await self.add(self.to(*args, **kwargs))

    async def add_many(self, *children: BaseModelType) -> list[BaseModelType | None]:
        """
        Asynchronously adds multiple child instances to the many-to-many relationship
        via the `through` model. This method validates each child type and
        attempts to save the intermediate records.

        Args:
            *children (BaseModelType): Variable number of child instances to add.
                                       Each can be an instance of the 'to' model,
                                        'through' model, or a dictionary.
        Returns:
            list[BaseModelType | None]: A list of saved intermediate model instances,
                                        or None for each record that already exists
                                        (IntegrityError).
        """
        prepared = []
        through = self.through
        for child in children:
            prepared.append(self.expand_relationship(child))
        if not prepared:
            return []
        operation = BulkOperation(
            owner=self.get_queryset(),
            unique_columns={
                col
                for field in [self.from_foreign_key, self.to_foreign_key]
                for col in through.meta.field_to_column_names[field]
            },
            ignore_create_conflicts=True,
            signal_models=[
                self._shared_relation_signals_params["source"],
                self._shared_relation_signals_params["target"],
                self.through,
            ],
            signal_postfix="relation_add",
            signal_params={"operation": "add", **self._shared_relation_signals_params},
            create=True,
            retrieve=False,
            update=False,
            used_instance=self.instance,
            resolve_embed=True,
        )
        await operation.prepare(prepared)
        try:
            await operation.send_pre_signal()
        except SkipOperation:
            operation.signal_params["row_count"] = 0
            operation.signal_params["row_count_create"] = 0
            await operation.send_post_signal()
            return []
        await operation.apply_db()
        # no cache update because the queryset is temporary
        # we can just rename the signals parameters for the post signal
        # both parameters are the same here
        operation.signal_params["row_count"] = operation.signal_params.get("row_count_create")
        await operation.send_post_signal()
        return cast(
            "list[BaseModelType | None]",
            [tup[0] for tup in operation.result],
        )

    async def add(self, child: BaseModelType) -> BaseModelType | None:
        """
        Asynchronously adds a child instance to the many-to-many relationship
        via the `through` model. This method validates the child type and
        attempts to save the intermediate record.

        Args:
            child (BaseModelType): The child instance to add. Can be an instance of
                                   the 'to' model, 'through' model, or a dictionary.

        Returns:
            BaseModelType | None: The saved intermediate model instance, or None
                                  if the record already exists (IntegrityError).

        Raises:
            RelationshipIncompatible: If the child type is not compatible.
        """
        return (await self.add_many(child))[0]

    async def remove_many(self, *children: BaseModelType) -> None:
        """
        Asynchronously removes multiple children from the many-to-many relationship.
        This deletes the corresponding records in the `through` table.

        Args:
            *children (BaseModelType): Variable number of child instances to remove.
                                       Each can be an instance of the 'to' model,
                                        'through' model, or None (if the foreign key is unique).
        Raises:
            RelationshipNotFound: If no child is found or specified for removal.
            RelationshipIncompatible: If a child type is not compatible.
        """

        def _helper_prepare(child: Any) -> Any:
            # Validate that the child is not a dict.
            if isinstance(child, dict):
                # this fails later and is wanted
                child = None
            return self.expand_relationship(child)

        prepared = [_helper_prepare(child) for child in children]
        if not prepared:
            return
        through = self.through.get_real_class()
        fk = self.through.meta.fields[self.from_foreign_key]
        fk_source = fk.target.meta.fields[fk.reverse_name]
        model_based_deletion = (
            fk.use_model_based_deletion or through.__require_model_based_deletion__
        )
        ops = []
        seen_signals: set[int] = set()
        for model_class in [
            self._shared_relation_signals_params["source"],
            self._shared_relation_signals_params["target"],
            through,
        ]:
            signal = model_class.meta.signals.pre_relation_remove
            if (signal_id := id(signal)) in seen_signals:
                continue
            seen_signals.add(signal_id)
            ops.append(
                model_class.meta.signals.pre_relation_remove.send_async(
                    through,
                    instance=self.instance,
                    raw_values=prepared,
                    model_based_deletion=model_based_deletion,
                    **self._shared_relation_signals_params,
                )
            )
        try:
            await asyncio.gather(*ops)
        except SkipOperation:
            ops = []
            # not really necessary but be safe
            seen_signals.clear()
            for model_class in [
                self._shared_relation_signals_params["source"],
                self._shared_relation_signals_params["target"],
                through,
            ]:
                signal = model_class.meta.signals.post_relation_remove
                if (signal_id := id(signal)) in seen_signals:
                    continue
                seen_signals.add(signal_id)
                ops.append(
                    signal.send_async(
                        through,
                        instance=self.instance,
                        raw_values=prepared,
                        row_count=0,
                        operation_skipped=True,
                        model_based_deletion=model_based_deletion,
                        **self._shared_relation_signals_params,
                    )
                )
            await asyncio.gather(*ops)
            return
        if prepared:
            queryset = self.get_queryset().update_embed_parent(None)
            # children can be removed by setting them to None
            clauses = [
                and_(*child.identifying_clauses()) for child in prepared if child is not None
            ]
            query = queryset.filter(or_(*clauses))
            async with queryset.transaction():
                row_count = await query.raw_delete(use_models=model_based_deletion)
                if row_count is not None and row_count != len(clauses):
                    related_name = fk_source.name
                    raise RelationshipNotFound(
                        detail=(
                            f"There is no relationship through '{related_name}' to {self.instance} from "
                            f"{('one of ' if len(clauses) > 1 else '')}"
                            f"{', '.join(str(getattr(child, self.to_foreign_key)) for child in prepared)}."
                        )
                    )
        else:
            row_count = 0
        ops = []
        # not really necessary but be safe
        seen_signals.clear()
        for model_class in [
            self._shared_relation_signals_params["source"],
            self._shared_relation_signals_params["target"],
            through,
        ]:
            signal = model_class.meta.signals.post_relation_remove
            if (signal_id := id(signal)) in seen_signals:
                continue
            seen_signals.add(signal_id)
            ops.append(
                signal.send_async(
                    through,
                    instance=self.instance,
                    raw_values=prepared,
                    row_count=row_count,
                    operation_skipped=False,
                    model_based_deletion=model_based_deletion,
                    **self._shared_relation_signals_params,
                )
            )
        await asyncio.gather(*ops)

    async def remove(self, child: BaseModelType | None = None) -> None:
        """
        Asynchronously removes a child from the many-to-many relationship.
        This deletes the corresponding record in the `through` table.

        Args:
            child (BaseModelType | None): The child instance to remove. If None and
                                          the foreign key is unique, it attempts to
                                          retrieve a single related child.

        Raises:
            RelationshipNotFound: If no child is found or specified for removal.
            RelationshipIncompatible: If the child type is not compatible.
        """

        if child is None:
            # Determine the foreign key based on whether it's a reverse relationship.
            if self.reverse:
                fk = self.through.meta.fields[self.from_foreign_key]
            else:
                fk = self.through.meta.fields[self.to_foreign_key]
            # If no child is specified and the foreign key is unique, attempt to get a single child.
            if fk.unique:
                try:
                    child = await self.get()
                except ObjectNotFound:
                    # If no child is found, raise a RelationshipNotFound error.
                    raise RelationshipNotFound(detail="No child found.") from None
            else:
                # If no child is specified and the foreign key is not unique, raise an error.
                raise RelationshipNotFound(detail="No child specified.")
        await self.remove_many(cast("BaseModelType", child))

    def __repr__(self) -> str:
        """
        Returns a developer-friendly string representation of the ManyRelation.
        """
        return f"<{type(self).__name__}: {self}>"

    def __str__(self) -> str:
        """
        Returns a human-readable string representation of the ManyRelation,
        displaying the name of the `through` model.
        """
        return f"{self.through.__name__}"

    def __get__(self, instance: BaseModelType, owner: Any = None) -> ManyRelationProtocol:
        """
        Descriptor method. When accessing a `ManyRelation` field on a model
        instance, this method ensures that the `instance` attribute of the
        `ManyRelation` is set to the current model instance.

        Args:
            instance (BaseModelType): The instance of the model on which this
                                      ManyRelation is being accessed.
            owner (Any): The owner class (model class). Unused in this context.

        Returns:
            ManyRelationProtocol: The ManyRelation instance itself, with its
                                  `instance` attribute set.
        """
        self.instance = instance
        return self


class SingleRelation(ManyRelationProtocol):
    """
    Manages a one-to-many or one-to-one relationship from the 'one' side,
    allowing access to a single related instance or a collection of related
    instances based on a foreign key. This class implements the
    `ManyRelationProtocol`, acting as a descriptor for model fields.
    """

    def __init__(
        self,
        *,
        to_foreign_key: str,
        to: type[BaseModelType],
        embed_parent: tuple[str, str] | None = None,
        refs: Any = (),
        instance: BaseModelType | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initializes a SingleRelation instance.

        Args:
            to_foreign_key (str): The name of the foreign key in the `to` model
                                  that points back to the owner of this relationship.
            to (type[BaseModelType]): The model class that is on the 'many' side
                                      of the relationship (or the single related model).
            embed_parent (tuple[str, str] | None): A tuple specifying how to embed
                                                   the parent in queries (field name, alias).
                                                   Defaults to None.
            refs (Any): Initial references to related objects to be staged.
                        Can be a single instance or a sequence of instances.
                        Defaults to an empty tuple.
            instance (BaseModelType | None): The current instance of the model
                                             that owns this relationship.
                                             Defaults to None.
            **kwargs (Any): Additional keyword arguments passed to the
                            `ManyRelationProtocol` constructor.
        """
        super().__init__(**kwargs)
        self.to = to
        self.instance = instance
        self.to_foreign_key = to_foreign_key
        self.embed_parent = embed_parent
        self.refs: list[BaseModelType] = []  # Initialize refs as a list
        # Ensure refs is a sequence; if not, wrap it in a list.
        if not isinstance(refs, Sequence):
            refs = [refs]
        # Stage the initial references.
        self.stage(*refs)

    @cached_property
    def _shared_relation_signals_params(self) -> dict:
        assert self.instance is not None
        fk = self.to.meta.fields[self.to_foreign_key]
        # here reverse_name=related_name
        return {
            "source": type(self.instance),
            "target": self.to,
            "field": fk.reverse_name,
            "relation": "one_to_many",
        }

    def get_queryset(self) -> QuerySet:
        """
        Returns a `QuerySet` for fetching related instances directly from the `to` model.
        This queryset is pre-filtered to include only instances related to the
        current `instance` via the `to_foreign_key`.

        Returns:
            QuerySet: A queryset for the related model.

        Raises:
            AssertionError: If the `instance` is not initialized.
        """
        # Retrieve the queryset from the 'to' model's query_related manager.
        # This ensures tenant checks are performed on every request.
        queryset = self.to.meta.managers["query_related"].get_queryset()
        # Get the foreign key field on the 'to' model that points back to the 'from' model.
        fk = self.to.meta.fields[self.to_foreign_key]
        # Assert that the current instance is available.
        assert self.instance, "instance not initialized"
        query = {}
        # Construct the filter query using the column names of the foreign key.
        for column_name in fk.get_column_names():
            # Get the related field name from the foreign key.
            related_name = fk.from_fk_field_name(fk.name, column_name)
            # Use getattr to get the value from the current instance for each related column.
            query[related_name] = getattr(self.instance, related_name)
        # Apply the filter to the queryset using the foreign key and the constructed query.
        queryset = queryset.filter(**{self.to_foreign_key: query})

        # Set the embed_parent attribute on the queryset for embedding.
        queryset.embed_parent = self.embed_parent
        # Apply embed_parent_filters only if embed_parent is set and the field is a RelationshipField.
        if self.embed_parent:
            embed_parent_field_name = self.embed_parent[0].split("__", 1)[0]
            embed_parent_field = fk.owner.meta.fields[embed_parent_field_name]
            if isinstance(
                embed_parent_field,
                RelationshipField,
            ):
                queryset.embed_parent_filters = queryset.embed_parent
                # also add to select_related, when not cross db
                if not embed_parent_field.is_cross_db(
                    owner_database=getattr(self.instance, "database", None)
                ):
                    # TODO: though this works, this isn't performant for deeply nested embed_parent definition
                    # not initialized yet, so just add it
                    queryset._select_related.add(embed_parent_field_name)
        return queryset

    def all(self, clear_cache: bool = False) -> QuerySet:
        """
        Returns a fresh `QuerySet` for all related instances.
        The `clear_cache` parameter is redundant here as `get_queryset()`
        always returns a new queryset.

        Args:
            clear_cache (bool): A flag (ignored) to indicate if the cache should be cleared.

        Returns:
            QuerySet: A queryset containing all related instances.
        """
        # get_queryset already returns a fresh queryset, so no need to make a copy.
        return self.get_queryset()

    def expand_relationship(self, value: Any) -> Any:
        """
        Expands a given value into an instance of the `to` model or its
        proxy model, preparing it for inclusion in the relationship.
        This handles cases where `value` might be a primitive type (like PK)
        or a dictionary.

        Args:
            value (Any): The value to expand, which can be an instance of the
                         `to` model, its proxy, a dictionary, or a primitive type.

        Returns:
            Any: An instance of the `to` model or its proxy, ready for use
                 in the relationship.
        """
        target = self.to
        if not isinstance(value, self.to | self.to.proxy_model | dict):
            raise RelationshipIncompatible(f"The child is not from the type '{self.to.__name__}'.")

        # If the value is already an instance of the target model or its proxy, return it directly.
        if isinstance(value, target | target.proxy_model):
            setattr(value, self.to_foreign_key, self.instance)
            return value

        related_columns = tuple(self.to.meta.fields[self.to_foreign_key].related_columns.keys())
        # If there's only one related column and the value is not a dict or BaseModel,
        # wrap it in a dictionary with the related column name as key.
        if len(related_columns) == 1 and not isinstance(value, dict | BaseModel):
            value = {next(iter(related_columns)): value}
        # Create a new proxy model instance of the 'to' model using the value.
        target_instance = target.proxy_model(**value)
        setattr(target_instance, self.to_foreign_key, self.instance)
        # Set identifying database fields for the 'to' model instance.
        target_instance.identifying_db_fields = related_columns
        # If the 'to' model is a tenant model, set the active schema for the instance.
        if getattr(target.meta, "is_tenant", False):
            target_instance.__using_schema__ = self.instance.get_active_instance_schema()  # type: ignore
        return target_instance

    def stage(self, *children: BaseModelType) -> None:
        """
        Stages one or more child instances to be added to the relationship.
        These instances are stored in an internal `refs` list and will be
        persisted when `save_related()` is called.

        Args:
            *children (BaseModelType): Variable number of child instances to stage.

        Raises:
            RelationshipIncompatible: If a child is not an instance of the
                                      `to` model or a dictionary.
        """
        for child in children:
            # Expand the child into a 'to' model instance and append it to refs.
            self.refs.append(self.expand_relationship(child))

    def __getattr__(self, item: Any) -> Any:
        """
        Retrieves an attribute. If the attribute is not found directly on the
        `SingleRelation` instance, it first attempts to get it from the `QuerySet`
        returned by `get_queryset()`. If still not found, it then tries to get it
        from the `to` model class itself.

        Args:
            item (Any): The name of the attribute to retrieve.

        Returns:
            Any: The value of the retrieved attribute.

        Raises:
            AttributeError: If the attribute is not found on the queryset or the
                            `to` model.
        """
        try:
            # Attempt to get the attribute from the queryset.
            attr = getattr(self.get_queryset(), item)
        except AttributeError:
            # If not found on the queryset, attempt to get it from the 'to' model.
            attr = getattr(self.to, item)

        return attr

    async def save_related(self) -> None:
        """
        Asynchronously saves all staged related instances to the database.
        This method iterates through the `refs` (staged children) and adds them
        to the relationship.
        """
        refs = list(self.refs)
        self.refs.clear()
        if not refs:
            return
        to = self.to
        operation = BulkOperation(
            owner=self.get_queryset(),
            unique_columns=to.pkcolumns,
            update_fields={self.to_foreign_key},
            signal_models=[
                self._shared_relation_signals_params["source"],
                self._shared_relation_signals_params["target"],
            ],
            signal_postfix="relation_add",
            signal_params={"operation": "save_related", **self._shared_relation_signals_params},
            ignore_create_conflicts=True,
            retrieve=False,
            create=True,
            update=True,
            used_instance=self.instance,
            resolve_embed=False,
        )
        await operation.prepare(refs)
        operation.signal_params["instance"] = self.instance
        try:
            await operation.send_pre_signal()
        except SkipOperation:
            operation.signal_params["row_count"] = 0
            operation.signal_params["row_count_create"] = 0
            await operation.send_post_signal()
            return
        await operation.apply_db()
        # no cache update because the queryset is temporary
        # we can just rename the signals parameters for the post signal
        operation.signal_params["row_count"] = operation.signal_params.pop("row_count_update")
        if operation.signal_params["row_count"] is not None:
            # keep the amount of created in the params
            operation.signal_params["row_count"] += operation.signal_params.get("row_count_create")
        operation.signal_params["instance"] = self.instance
        await operation.send_post_signal()

    async def create(self, *args: Any, **kwargs: Any) -> BaseModelType | None:
        """
        Creates a new instance of the 'to' model and immediately adds it
        to the relationship by setting its foreign key to the current instance.

        Args:
            *args (Any): Positional arguments to pass to the 'to' model constructor.
            **kwargs (Any): Keyword arguments to pass to the 'to' model constructor.

        Returns:
            BaseModelType | None: The newly created and added child instance.
        """
        return await self.add(self.to(*args, **kwargs))

    async def add(self, child: BaseModelType) -> BaseModelType | None:
        """
        Asynchronously adds a child instance to the one-to-many or one-to-one
        relationship by updating its foreign key.

        Args:
            child (BaseModelType): The child instance to add. Can be an instance of
                                   the 'to' model or a dictionary.

        Returns:
            BaseModelType | None: The saved child model instance.

        Raises:
            RelationshipIncompatible: If the child type is not compatible.
        """
        return (await self.add_many(child))[0]

    async def add_many(self, *children: BaseModelType) -> list[BaseModelType | None]:
        """
        Asynchronously adds multiple child instances to the one-to-many or
        one-to-one relationship by updating their foreign keys.

        Args:
            *children (BaseModelType): Variable number of child instances to add.
                                       Each can be an instance of the 'to'
                                        model or a dictionary.

        Returns:
            list[BaseModelType | None]: A list of saved child model instances.

        Raises:
            RelationshipIncompatible: If a child type is not compatible.
        """

        prepared = []
        to = self.to
        for child in children:
            prepared.append(self.expand_relationship(child))
        if not prepared:
            return []
        operation = BulkOperation(
            owner=self.get_queryset(),
            unique_columns=to.pkcolumns,
            update_fields={self.to_foreign_key},
            signal_models=[
                self._shared_relation_signals_params["source"],
                self._shared_relation_signals_params["target"],
            ],
            signal_postfix="relation_add",
            signal_params={"operation": "add", **self._shared_relation_signals_params},
            ignore_create_conflicts=True,
            retrieve=False,
            create=True,
            update=True,
            used_instance=self.instance,
            resolve_embed=True,
        )
        await operation.prepare(prepared)
        try:
            await operation.send_pre_signal()
        except SkipOperation:
            await operation.send_post_signal()
            return []
        await operation.apply_db()
        # no cache update because the queryset is temporary
        # we can just rename the signals parameters for the post signal
        operation.signal_params["row_count"] = operation.signal_params.pop("row_count_update")
        if operation.signal_params["row_count"] is not None:
            # keep the amount of created in the params
            operation.signal_params["row_count"] += operation.signal_params.get("row_count_create")
        await operation.send_post_signal()
        return cast(
            "list[BaseModelType | None]",
            [tup[0] for tup in operation.result],
        )

    async def remove_many(self, *children: BaseModelType) -> None:
        """
        Asynchronously removes multiple children from the one-to-many or
        one-to-one relationship. This is typically done by setting the foreign
        key on each child to None.

        Args:
            *children (BaseModelType): Variable number of child instances to remove.
                                       Each can be an instance of the 'to' model
                                       or None (if the foreign key is unique).

        Raises:
            RelationshipNotFound: If no child is found or specified for removal.
            RelationshipIncompatible: If a child type is not compatible.
        """

        def _helper_prepare(child: Any) -> Any:
            # Validate that the child is not a dict.
            if isinstance(child, dict):
                # this fails later and is wanted
                child = None
            child = self.expand_relationship(child)
            setattr(child, self.to_foreign_key, None)
            return child

        prepared = [_helper_prepare(child) for child in children]
        if not prepared:
            return

        to = self.to
        queryset = self.get_queryset()
        operation = BulkOperation(
            owner=queryset,
            unique_columns=to.pkcolumns,
            update_fields={self.to_foreign_key},
            signal_models=[
                self._shared_relation_signals_params["source"],
                self._shared_relation_signals_params["target"],
            ],
            signal_postfix="relation_remove",
            signal_params=self._shared_relation_signals_params,
            retrieve=False,
            create=False,
            update=True,
            used_instance=self.instance,
            resolve_embed=False,
        )
        await operation.prepare(prepared)
        # replace raw_values
        raw_values = [tup[0] for tup in operation.instances_and_created]
        del operation.signal_params["create_params"]
        del operation.signal_params["update_params"]
        operation.signal_params["raw_values"] = raw_values
        try:
            await operation.send_pre_signal()
        except SkipOperation:
            operation.signal_params["row_count"] = 0
            await operation.send_post_signal()
            return
        # allow modification via raw_values
        obj_ids = [id(obj) for obj in raw_values]
        operation.update_params = [tup for tup in operation.update_params if id(tup[0]) in obj_ids]

        async with queryset.transaction():
            await operation.apply_db()
            # the queryset is temporary and maybe even resetted, so we don't need to update the cache
            if operation.row_count_update != len(raw_values):
                related_name = self._shared_relation_signals_params["field"]
                raise RelationshipNotFound(
                    detail=(
                        f"There is no relationship through '{related_name}' to {self.instance} from "
                        f"{('one of ' if len(prepared) > 1 else '')}"
                        f"{', '.join(str(child) for child in prepared)}."
                    )
                )
        # replace unsuitable parameters
        operation.signal_params["raw_values"] = raw_values
        operation.signal_params["row_count"] = operation.signal_params.pop("row_count_update")
        del operation.signal_params["values"]
        del operation.signal_params["create_params"]
        del operation.signal_params["update_params"]
        await operation.send_post_signal()

    async def remove(self, child: BaseModelType | None = None) -> None:
        """
        Asynchronously removes a child from the one-to-many or one-to-one relationship.
        This is typically done by setting the foreign key on the child to None.

        Args:
            child (BaseModelType | None): The child instance to remove. If None and
                                          the foreign key is unique, it attempts to
                                          retrieve a single related child.

        Raises:
            RelationshipNotFound: If no child is found or specified for removal.
            RelationshipIncompatible: If the child type is not compatible.
        """
        # Get the foreign key field on the 'to' model.
        fk = self.to.meta.fields[self.to_foreign_key]
        if child is None:
            # If no child is specified and the foreign key is unique, attempt to get a single child.
            if fk.unique:
                try:
                    child = await self.get()
                except ObjectNotFound:
                    # If no child is found, raise a RelationshipNotFound error.
                    raise RelationshipNotFound(detail="no child found") from None
            else:
                # If no child is specified and the foreign key is not unique, raise an error.
                raise RelationshipNotFound(detail="no child specified")
        await self.remove_many(cast("BaseModelType", child))

    def __repr__(self) -> str:
        """
        Returns a developer-friendly string representation of the SingleRelation.
        """
        return f"<{type(self).__name__}: {self}>"

    def __str__(self) -> str:
        """
        Returns a human-readable string representation of the SingleRelation,
        displaying the name of the 'to' model.
        """
        return f"{self.to.__name__}"

    def __get__(self, instance: BaseModelType, owner: Any = None) -> ManyRelationProtocol:
        """
        Descriptor method. When accessing a `SingleRelation` field on a model
        instance, this method ensures that the `instance` attribute of the
        `SingleRelation` is set to the current model instance.

        Args:
            instance (BaseModelType): The instance of the model on which this
                                      SingleRelation is being accessed.
            owner (Any): The owner class (model class). Unused in this context.

        Returns:
            ManyRelationProtocol: The SingleRelation instance itself, with its
                                  `instance` attribute set.
        """
        self.instance = instance
        return self


class VirtualCascadeDeletionSingleRelation(SingleRelation):
    """
    A specialized `SingleRelation` that implements a virtual cascade deletion.
    When the owner model instance is deleted, this class ensures that the
    related models are also deleted or disassociated based on the `use_model_based_deletion`
    flag and the `to_foreign_key` reference.
    """

    async def post_delete_callback(self) -> None:
        """
        An asynchronous callback executed after the owner model instance is deleted.
        This method performs a raw deletion on the related objects, potentially
        disregarding signals on the `QuerySet` based on configuration.
        """
        # Issue a plain deletion on the related models.
        await self.raw_delete(
            # Determine whether to use model-based deletion from the foreign key's configuration.
            use_models=self.to.meta.fields[self.to_foreign_key].use_model_based_deletion,
            # Specify the foreign key that references the deleted instance to ensure correct removal.
            remove_referenced_call=self.to_foreign_key or True,
        )
