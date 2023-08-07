import functools
from typing import TYPE_CHECKING, Any, Optional, Type, Union

from pydantic import ConfigDict

from edgy.exceptions import RelationshipIncompatible, RelationshipNotFound
from edgy.protocols.many_relationship import ManyRelationProtocol

if TYPE_CHECKING:
    from edgy import Model, ReflectModel


class Relation(ManyRelationProtocol):
    """
    When a `related_name` is generated, creates a RelatedField from the table pointed
    from the ForeignKey declaration and the the table declaring it.
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __init__(
        self,
        instance: Optional[Union[Type["Model"], Type["ReflectModel"]]] = None,
        through: Optional[Union[Type["Model"], Type["ReflectModel"]]] = None,
        to: Optional[Union[Type["Model"], Type["ReflectModel"]]] = None,
        owner: Optional[Union[Type["Model"], Type["ReflectModel"]]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.through = through
        self.instance = instance
        self.to = to
        self.owner = owner

        # Relationship parameters
        self.owner_name = self.owner.__name__.lower()  # type: ignore
        self.to_name = self.to.__name__.lower()  # type: ignore
        self._relation_params = {
            self.owner_name: None,
            self.to_name: None,
        }

    def __get__(self, instance: Any, owner: Any) -> Any:
        return self.__class__(
            instance=instance, through=self.through, to=self.to, owner=self.owner
        )

    def __getattr__(self, item: Any) -> Any:
        """
        Gets the attribute from the queryset and if it does not
        exist, then lookup in the model.
        """
        manager = self.through.meta.manager  # type: ignore
        try:
            attr = getattr(manager.get_queryset(), item)
        except AttributeError:
            attr = getattr(self.through, item)

        func = self.wrap_args(attr)
        return func

    def wrap_args(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            kwargs[self.owner_name] = self.instance.pk  # type: ignore
            return func(*args, **kwargs)

        return wrapped

    async def add(self, child: Type["Model"]) -> None:
        """
        Adds a child to the model as a list

        . Validates the type of the child being added to the relationship and raises error for
        if the type is wrong.
        . Checks if the middle table already contains the record being added. Raises error if yes.
        """
        if not isinstance(child, self.to):
            raise RelationshipIncompatible(f"The child is not from the type '{self.to.__name__}'.")  # type: ignore

        self._relation_params.update({self.owner_name: self.instance, self.to_name: child})  # type: ignore
        exists = await self.through.query.filter(**self._relation_params).exists()  # type: ignore

        if not exists:
            await self.through.query.create(**self._relation_params)  # type: ignore

    async def remove(self, child: Type["Model"]) -> None:
        """Removes a child from the list of many to many.

        . Validates if there is a relationship between the entities.
        . Removes the field if there is
        """
        if not isinstance(child, self.to):
            raise RelationshipIncompatible(f"The child is not from the type '{self.to.__name__}'.")  # type: ignore

        self._relation_params.update({self.owner_name: self.instance, self.to_name: child})  # type: ignore
        exists = await self.through.query.filter(**self._relation_params).exists()  # type: ignore

        if not exists:
            raise RelationshipNotFound(
                detail=f"There is no relationship between '{self.owner_name}' and '{self.to_name}: {child.pk}'."
            )

        child = await self.through.query.filter(**self._relation_params).get()  # type: ignore
        await child.delete()  # type: ignore

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.through.__name__}"  # type: ignore
