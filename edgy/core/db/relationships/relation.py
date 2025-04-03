from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

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
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """

    def __init__(
        self,
        *,
        from_foreign_key: str,
        to_foreign_key: str,
        to: type["BaseModelType"],
        through: type["BaseModelType"],
        reverse: bool = False,
        embed_through: Union[Literal[False], str] = "",
        refs: Any = (),
        instance: Optional[Union["BaseModelType"]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.through = through
        self.to = to
        self.instance = instance
        self.reverse = reverse
        self.from_foreign_key = from_foreign_key
        self.to_foreign_key = to_foreign_key
        self.embed_through = embed_through
        self.refs: Sequence[BaseModelType] = []
        if not isinstance(refs, Sequence):
            refs = [refs]
        self.stage(*refs)

    def get_queryset(self) -> "QuerySet":
        # we need to check tenant every request
        queryset = self.through.meta.managers["query_related"].get_queryset()
        assert self.instance, "instance not initialized"
        fk = self.through.meta.fields[self.from_foreign_key]
        query = {}
        for related_name in fk.related_columns:
            query[related_name] = getattr(self.instance, related_name)
        queryset = queryset.filter(**{self.from_foreign_key: query})
        # now set embed_parent
        queryset.embed_parent = (self.to_foreign_key, self.embed_through or "")
        if self.embed_through != "":
            queryset.embed_parent_filters = queryset.embed_parent
        return queryset

    async def save_related(self) -> None:
        # TODO: improve performance
        fk = self.through.meta.fields[self.from_foreign_key]
        while self.refs:
            ref = self.refs.pop()
            ref.__dict__.update(fk.clean(fk.name, self.instance))
            await self.add(ref)

    def __getattr__(self, item: Any) -> Any:
        """
        Gets the attribute from the queryset and if it does not
        exist, then lookup in the model.
        """  #
        try:
            attr = getattr(self.get_queryset(), item)
        except AttributeError:
            attr = getattr(self.through, item)

        return attr

    def all(self, clear_cache: bool = False) -> "QuerySet":
        # get_queryset returns already a fresh queryset. Skip making a copy.
        return self.get_queryset()

    def expand_relationship(self, value: Any) -> Any:
        through = self.through

        if isinstance(value, (through, through.proxy_model)):  # type: ignore
            return value
        instance = through.proxy_model(
            **{self.from_foreign_key: self.instance, self.to_foreign_key: value}
        )
        instance.identifying_db_fields = [self.from_foreign_key, self.to_foreign_key]  # type: ignore
        if getattr(through.meta, "is_tenant", False):
            instance.__using_schema__ = self.instance.get_active_instance_schema()  # type: ignore
        return instance

    def stage(self, *children: "BaseModelType") -> None:
        for child in children:
            if not isinstance(
                child,
                (self.to, self.to.proxy_model, self.through, self.through.proxy_model, dict),  # type: ignore
            ):
                raise RelationshipIncompatible(
                    f"The child is not from the types '{self.to.__name__}', '{self.through.__name__}'."
                )
            self.refs.append(self.expand_relationship(child))

    async def create(self, *args: Any, **kwargs: Any) -> Optional["BaseModelType"]:
        """Creates and add a child"""
        return await self.add(self.to(*args, **kwargs))

    async def add(self, child: "BaseModelType") -> Optional["BaseModelType"]:
        """
        Adds a child to the model as a list

        . Validates the type of the child being added to the relationship and raises error for
        if the type is wrong.
        . Checks if the middle table already contains the record being added. Raises error if yes.
        """
        if not isinstance(
            child,
            (self.to, self.to.proxy_model, self.through, self.through.proxy_model, dict),  # type: ignore
        ):
            raise RelationshipIncompatible(
                f"The child is not from the types '{self.to.__name__}', '{self.through.__name__}'."
            )
        child = self.expand_relationship(child)
        # try saving intermediate model. If it fails another instance already exists and return None
        try:
            return await child.save(force_insert=True)
        except IntegrityError:
            pass
        return None

    async def remove(self, child: Optional["BaseModelType"] = None) -> None:
        """Removes a child from the list of many to many.

        . Validates if there is a relationship between the entities.
        . Removes the field if there is
        """
        if self.reverse:
            fk = self.through.meta.fields[self.from_foreign_key]
        else:
            fk = self.through.meta.fields[self.to_foreign_key]
        if child is None:
            if fk.unique:
                try:
                    child = await self.get()
                except ObjectNotFound:
                    raise RelationshipNotFound(detail="No child found.") from None
            else:
                raise RelationshipNotFound(detail="No child specified.")
        if not isinstance(
            child,
            (self.to, self.to.proxy_model, self.through, self.through.proxy_model),  # type: ignore
        ):
            raise RelationshipIncompatible(
                f"The child is not from the types '{self.to.__name__}', '{self.through.__name__}'."
            )
        child = cast("BaseModelType", self.expand_relationship(child))
        count = await child.query.filter(*child.identifying_clauses()).count()
        if count == 0:
            raise RelationshipNotFound(
                detail=f"There is no relationship between '{self.from_foreign_key}' and '{self.to_foreign_key}: {getattr(child, self.to_foreign_key).pk}'."
            )
        else:
            await child.delete()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.through.__name__}"

    def __get__(self, instance: "BaseModelType", owner: Any = None) -> ManyRelationProtocol:
        self.instance = instance
        return self


class SingleRelation(ManyRelationProtocol):
    """
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """

    def __init__(
        self,
        *,
        to_foreign_key: str,
        to: type["BaseModelType"],
        embed_parent: Optional[tuple[str, str]] = None,
        refs: Any = (),
        instance: Optional["BaseModelType"] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.to = to
        self.instance = instance
        self.to_foreign_key = to_foreign_key
        self.embed_parent = embed_parent
        self.refs: Sequence[BaseModelType] = []
        if not isinstance(refs, Sequence):
            refs = [refs]
        self.stage(*refs)

    def get_queryset(self) -> "QuerySet":
        # we need to check tenant every request
        queryset = self.to.meta.managers["query_related"].get_queryset()
        fk = self.to.meta.fields[self.to_foreign_key]
        assert self.instance, "instance not initialized"
        query = {}
        for column_name in fk.get_column_names():
            related_name = fk.from_fk_field_name(fk.name, column_name)
            query[related_name] = getattr(self.instance, related_name)
        queryset = queryset.filter(**{self.to_foreign_key: query})
        # now set embed_parent
        queryset.embed_parent = self.embed_parent
        # only apply if relationship field. Add fallback for empty embed_parent
        if self.embed_parent and isinstance(
            fk.owner.meta.fields[self.embed_parent[0].split("__", 1)[0]],
            RelationshipField,
        ):
            queryset.embed_parent_filters = queryset.embed_parent
        return queryset

    def all(self, clear_cache: bool = False) -> "QuerySet":
        # get_queryset returns already a fresh queryset. Skip making a copy.
        return self.get_queryset()

    def expand_relationship(self, value: Any) -> Any:
        target = self.to

        if isinstance(value, (target, target.proxy_model)):  # type: ignore
            return value
        related_columns = self.to.meta.fields[self.to_foreign_key].related_columns.keys()
        if len(related_columns) == 1 and not isinstance(value, (dict, BaseModel)):
            value = {next(iter(related_columns)): value}
        instance = target.proxy_model(**value)
        instance.identifying_db_fields = related_columns  # type: ignore
        if getattr(target.meta, "is_tenant", False):
            instance.__using_schema__ = self.instance.get_active_instance_schema()  # type: ignore
        return instance

    def stage(self, *children: "BaseModelType") -> None:
        for child in children:
            if not isinstance(child, (self.to, self.to.proxy_model, dict)):  # type: ignore
                raise RelationshipIncompatible(
                    f"The child is not from the types '{self.to.__name__}', '{self.through.__name__}'."
                )
            self.refs.append(self.expand_relationship(child))

    def __getattr__(self, item: Any) -> Any:
        """
        Gets the attribute from the queryset and if it does not
        exist, then lookup in the model.
        """
        try:
            attr = getattr(self.get_queryset(), item)
        except AttributeError:
            attr = getattr(self.to, item)

        return attr

    async def save_related(self) -> None:
        while self.refs:
            await self.add(self.refs.pop())

    async def create(self, *args: Any, **kwargs: Any) -> Optional["BaseModelType"]:
        """Creates and add a child"""
        kwargs[self.to_foreign_key] = self.instance
        return await cast("QuerySet", self.to.query).create(*args, **kwargs)

    async def add(self, child: "BaseModelType") -> Optional["BaseModelType"]:
        """
        Adds a child to the model as a list

        . Validates the type of the child being added to the relationship and raises error for
        if the type is wrong.
        . Checks if the middle table already contains the record being added. Raises error if yes.
        """
        if not isinstance(child, (self.to, self.to.proxy_model, dict)):  # type: ignore
            raise RelationshipIncompatible(f"The child is not from the type '{self.to.__name__}'.")
        child = self.expand_relationship(child)
        await child.save(values={self.to_foreign_key: self.instance})
        return child

    async def remove(self, child: Optional["BaseModelType"] = None) -> None:
        """Removes a child from the list of one to many.

        . Validates if there is a relationship between the entities.
        . Removes the field if there is
        """
        fk = self.to.meta.fields[self.to_foreign_key]
        if child is None:
            if fk.unique:
                try:
                    child = await self.get()
                except ObjectNotFound:
                    raise RelationshipNotFound(detail="no child found") from None
            else:
                raise RelationshipNotFound(detail="no child specified")
        if not isinstance(child, self.to):
            raise RelationshipIncompatible(f"The child is not from the type '{self.to.__name__}'.")

        await child.save(values={self.to_foreign_key: None})

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.to.__name__}"

    def __get__(self, instance: "BaseModelType", owner: Any = None) -> ManyRelationProtocol:
        self.instance = instance
        return self


class VirtualCascadeDeletionSingleRelation(SingleRelation):
    async def post_delete_callback(self, instance: "BaseModelType") -> None:
        await self.delete()
