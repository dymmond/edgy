import functools
from typing import TYPE_CHECKING, Any, Literal, Optional, Sequence, Tuple, Type, Union, cast

import sqlalchemy
from pydantic import BaseModel, ConfigDict

from edgy.core.db.fields.base import RelationshipField
from edgy.exceptions import ObjectNotFound, RelationshipIncompatible, RelationshipNotFound
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:
    from edgy import Model, QuerySet, ReflectModel



def _removeprefix(text: str, prefix: str) -> str:
    # TODO: replace with removeprefix when python3.9 is minimum
    if text.startswith(prefix):
        return text[len(prefix) :]
    else:
        return text


def _removeprefixes(text:str, *prefixes: Sequence[str]) -> str:
    for prefix in prefixes:
        text = _removeprefix(text, prefix)
    return text


class ManyRelation(ManyRelationProtocol):
    """
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __init__(
        self,
        *,
        from_foreign_key: str,
        to_foreign_key: str,
        to: Union[Type["Model"], Type["ReflectModel"]],
        through: Union[Type["Model"], Type["ReflectModel"]],
        reverse: bool=False,
        embed_through: Union[Literal[False], str] = "",
        refs: Any = (),
        instance: Optional[Union["Model", "ReflectModel"]] = None,
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
        self.refs: Sequence[Union["Model", "ReflectModel"]] = []
        if not isinstance(refs, Sequence):
            refs = [refs]
        for v in refs:
            self._add_object(v)

    def get_queryset(self) -> "QuerySet":
        # we need to check tenant every request
        queryset = self.through.meta.managers["query_related"].get_queryset()
        queryset.embed_parent = (self.to_foreign_key, self.embed_through)
        return queryset

    async def save_related(self) -> None:
        # TODO: improve performance
        fk = self.through.meta.fields_mapping[self.from_foreign_key]
        while self.refs:
            ref = self.refs.pop()
            ref.__dict__.update(fk.clean(fk.name, self.instance))
            await self.add(ref)

    def __getattr__(self, item: Any) -> Any:
        """
        Gets the attribute from the queryset and if it does not
        exist, then lookup in the model.
        """#
        try:
            attr = getattr(self.get_queryset(), item)
        except AttributeError:
            attr = getattr(self.through, item)

        func = self.wrap_args(attr)
        return func

    def wrap_args(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            assert self.instance, "instance not initialized"
            fk = self.through.meta.fields_mapping[self.from_foreign_key]
            query = {}
            if self.embed_through == "":
                new_kwargs = kwargs
            else:
                new_kwargs = {}
                for key, val in kwargs.items():
                    if self.embed_through is False or not key.startswith(self.embed_through):
                        new_kwargs[f"{self.to_foreign_key}__{key}"] = val
                    else:
                        new_kwargs[_removeprefixes(key, self.embed_through, "__")] = val
            for related_name in fk.related_columns.keys():
                query[related_name] = getattr(self.instance, related_name)
            new_kwargs[self.from_foreign_key] = query
            return func(*args, **new_kwargs)

        return wrapped

    def expand_relationship(self, value: Any) -> Any:
        through = self.through

        if isinstance(value, (through, through.proxy_model)):
            return value
        instance = through.proxy_model(**{self.from_foreign_key: self.instance, self.to_foreign_key: value})
        instance.identifying_db_fields = [self.from_foreign_key, self.to_foreign_key]
        return instance

    def _add_object(self, child: Type["Model"]) -> None:
        self.refs.append(self.expand_relationship(child))

    async def add(self, child: "Model") -> Optional["Model"]:
        """
        Adds a child to the model as a list

        . Validates the type of the child being added to the relationship and raises error for
        if the type is wrong.
        . Checks if the middle table already contains the record being added. Raises error if yes.
        """
        if not isinstance(child, (self.to, self.to.proxy_model, self.through, self.through.proxy_model)):
            raise RelationshipIncompatible(f"The child is not from the types '{self.to.__name__}', '{self.through.__name__}'.")
        child = self.expand_relationship(child)

        try:
            async with child.database.transaction():
                return await child.save(force_save=True)
        except Exception:
            pass
        return None

    async def remove(self, child: Optional["Model"]=None) -> None:
        """Removes a child from the list of many to many.

        . Validates if there is a relationship between the entities.
        . Removes the field if there is
        """
        if self.reverse:
            fk = self.through.meta.fields_mapping[self.from_foreign_key]
        else:
            fk = self.through.meta.fields_mapping[self.to_foreign_key]
        if child is None:
            if fk.unique:
                try:
                    child = await self.get()
                except ObjectNotFound:
                    raise RelationshipNotFound(detail="no child found") from None
            else:
                raise RelationshipNotFound(detail="no child specified")
        if not isinstance(child, (self.to, self.to.proxy_model, self.through, self.through.proxy_model)):
            raise RelationshipIncompatible(f"The child is not from the types '{self.to.__name__}', '{self.through.__name__}'.")
        child = cast("Model", self.expand_relationship(child))
        count = await child.query.filter(sqlalchemy.and_(*child.identifying_clauses())).count()
        if count == 0:
            raise RelationshipNotFound(
                detail=f"There is no relationship between '{self.from_foreign_key}' and '{self.to_foreign_key}: {getattr(child,self.to_foreign_key).pk}'."
            )
        else:
            await child.delete()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.through.__name__}"



class SingleRelation(ManyRelationProtocol):
    """
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __init__(
        self,
        *,
        to_foreign_key: str,
        to: Union[Type["Model"], Type["ReflectModel"]],
        embed_parent: Optional[Tuple[str, str]]=None,
        refs: Any = (),
        instance: Optional[Union["Model", "ReflectModel"]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.to = to
        self.instance = instance
        self.to_foreign_key = to_foreign_key
        self.embed_parent = embed_parent
        self.refs: Sequence[Union["Model","ReflectModel"]] = []
        if not isinstance(refs, Sequence):
            refs = [refs]
        for v in refs:
            self._add_object(v)

    def get_queryset(self) -> "QuerySet":
        # we need to check tenant every request
        queryset = self.to.meta.managers["query_related"].get_queryset()
        queryset.embed_parent = self.embed_parent
        return queryset

    def expand_relationship(self, value: Any) -> Any:
        target = self.to

        if isinstance(value, (target, target.proxy_model)):
            return value
        related_columns = self.to.meta.fields_mapping[self.to_foreign_key].related_columns.keys()
        if len(related_columns) == 1 and not isinstance(value, (dict, BaseModel)):
            value = {next(iter(related_columns)): value}
        if isinstance(value, dict):
            for key in related_columns:
                if value.get(key) is None:
                    return None
        else:
            for key in related_columns:
                if getattr(value, key, None) is None:
                    return None
        instance = target.proxy_model(**value)
        instance.identifying_db_fields = related_columns
        return instance

    def _add_object(self, child: Type["Model"]) -> None:
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

        func = self.wrap_args(attr)
        return func

    def wrap_args(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            assert self.instance, "instance not initialized"
            fk = self.to.meta.fields_mapping[self.to_foreign_key]
            query = {}
            if not self.embed_parent or not isinstance(fk.owner.meta.fields_mapping[self.embed_parent[0]], RelationshipField):
                new_kwargs = kwargs
            else:
                new_kwargs = {}
                for key, val in kwargs.items():
                    if not self.embed_parent[1] or not key.startswith(self.embed_parent[1]):
                        new_kwargs[f"{self.embed_parent[0]}__{key}"] = val
                    else:
                        new_kwargs[_removeprefixes(key, self.embed_parent[1], "__")] = val

            for column_name in fk.get_column_names():
                related_name = fk.from_fk_field_name(fk.name, column_name)
                query[related_name] = getattr(self.instance, related_name)
            new_kwargs[self.to_foreign_key] = query
            return func(*args, **new_kwargs)

        return wrapped

    async def save_related(self) -> None:
        while self.refs:
            await self.add(self.refs.pop())

    async def add(self, child: "Model") -> Optional["Model"]:
        """
        Adds a child to the model as a list

        . Validates the type of the child being added to the relationship and raises error for
        if the type is wrong.
        . Checks if the middle table already contains the record being added. Raises error if yes.
        """
        if not isinstance(child, (self.to, self.to.proxy_model)):
            raise RelationshipIncompatible(f"The child is not from the type '{self.to.__name__}'.")

        await child.save(values={self.to_foreign_key: self.instance})
        return child

    async def remove(self, child: Optional["Model"]=None) -> None:
        """Removes a child from the list of one to many.

        . Validates if there is a relationship between the entities.
        . Removes the field if there is
        """
        fk = self.to.meta.fields_mapping[self.to_foreign_key]
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
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.to.__name__}"
