from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from edgy.core.db.fields.base import RelationshipField
from edgy.exceptions import ObjectNotFound, RelationshipIncompatible, RelationshipNotFound
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
            if not self.through.meta.fields[self.from_foreign_key].is_cross_db():
                # not initialized yet
                queryset._select_related.add(self.from_foreign_key)
        else:
            if not self.through.meta.fields[self.to_foreign_key].is_cross_db():
                # not initialized yet
                queryset._select_related.add(self.to_foreign_key)
        return queryset

    async def save_related(self) -> None:
        """
        Asynchronously saves all staged related instances to the database.
        This method iterates through the `refs` (staged children) and adds them
        to the relationship.
        """
        # TODO: improve performance
        # Get the foreign key field on the 'through' model that points back to the 'from' model.
        fk = self.through.meta.fields[self.from_foreign_key]
        # Iterate while there are references in the list.
        while self.refs:
            # Pop the last reference from the list.
            ref = self.refs.pop()
            # Clean the foreign key value and update the reference's dictionary.
            ref.__dict__.update(fk.clean(fk.name, self.instance))
            # Asynchronously add the reference to the relationship.
            await self.add(ref)

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

    def expand_relationship(self, value: Any) -> Any:
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
        instance.identifying_db_fields = [self.from_foreign_key, self.to_foreign_key]  # type: ignore
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
            # Validate that the child is compatible with the relationship.
            if not isinstance(
                child,
                self.to | self.to.proxy_model | self.through | self.through.proxy_model | dict,
            ):
                raise RelationshipIncompatible(
                    f"The child is not from the types '{self.to.__name__}', "
                    f"'{self.through.__name__}'."
                )
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
        # Validate that the child is compatible with the relationship.
        if not isinstance(
            child,
            self.to | self.to.proxy_model | self.through | self.through.proxy_model | dict,
        ):
            raise RelationshipIncompatible(
                f"The child is not from the types '{self.to.__name__}', '{self.through.__name__}'."
            )
        # Expand the child into a 'through' model instance.
        child = self.expand_relationship(child)
        try:
            # Attempt to save the intermediate model. If it fails due to IntegrityError,
            # it means the record already exists, so return None.
            return await child.save(force_insert=True)
        except IntegrityError:
            pass  # The record already exists.
        return None

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
        # Determine the foreign key based on whether it's a reverse relationship.
        if self.reverse:
            fk = self.through.meta.fields[self.from_foreign_key]
        else:
            fk = self.through.meta.fields[self.to_foreign_key]

        if child is None:
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

        # Validate that the child is compatible before removal.
        if not isinstance(
            child,
            self.to | self.to.proxy_model | self.through | self.through.proxy_model,
        ):
            raise RelationshipIncompatible(
                f"The child is not from the types '{self.to.__name__}', '{self.through.__name__}'."
            )
        # Cast the child to BaseModelType as it is now confirmed to be a model instance.
        child = cast("BaseModelType", self.expand_relationship(child))
        # Count the number of relationships based on the identifying clauses of the child.
        count = await child.query.filter(*child.identifying_clauses()).count()
        if count == 0:
            # If no relationship is found, raise an error.
            raise RelationshipNotFound(
                detail=f"There is no relationship between '{self.from_foreign_key}' and "
                f"'{self.to_foreign_key}: {getattr(child, self.to_foreign_key).pk}'."
            )
        else:
            # If a relationship exists, delete the child from the through table.
            await child.delete()

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

        # If the value is already an instance of the target model or its proxy, return it directly.
        if isinstance(value, target | target.proxy_model):
            return value

        related_columns = self.to.meta.fields[self.to_foreign_key].related_columns.keys()
        # If there's only one related column and the value is not a dict or BaseModel,
        # wrap it in a dictionary with the related column name as key.
        if len(related_columns) == 1 and not isinstance(value, dict | BaseModel):
            value = {next(iter(related_columns)): value}
        # Create a new proxy model instance of the 'to' model using the value.
        instance = target.proxy_model(**value)
        # Set identifying database fields for the 'to' model instance.
        instance.identifying_db_fields = related_columns  # type: ignore
        # If the 'to' model is a tenant model, set the active schema for the instance.
        if getattr(target.meta, "is_tenant", False):
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
                                      `to` model or a dictionary.
        """
        for child in children:
            # Validate that the child is compatible with the relationship.
            if not isinstance(child, self.to | self.to.proxy_model | dict):
                raise RelationshipIncompatible(
                    f"The child is not from the types '{self.to.__name__}', "
                    f"'{self.through.__name__}'."
                )
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
        # Iterate while there are references in the list.
        while self.refs:
            # Pop the last reference from the list and add it to the relationship.
            await self.add(self.refs.pop())

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
        # Set the foreign key in kwargs to link the new child to the current instance.
        kwargs[self.to_foreign_key] = self.instance
        # Create the new instance using the 'to' model's query manager.
        return await cast("QuerySet", self.to.query).create(*args, **kwargs)

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
        # Validate that the child is compatible with the relationship.
        if not isinstance(child, self.to | self.to.proxy_model | dict):
            raise RelationshipIncompatible(f"The child is not from the type '{self.to.__name__}'.")
        # Expand the child into a 'to' model instance.
        child = self.expand_relationship(child)
        # Save the child, setting its foreign key to the current instance.
        await child.save(values={self.to_foreign_key: self.instance})
        return child

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
        # Validate that the child is an instance of the 'to' model.
        if not isinstance(child, self.to):
            raise RelationshipIncompatible(f"The child is not from the type '{self.to.__name__}'.")

        # Save the child, setting its foreign key to None to remove the relationship.
        await child.save(values={self.to_foreign_key: None})

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
            remove_referenced_call=self.to_foreign_key,
        )
