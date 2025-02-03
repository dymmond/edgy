from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import monkay

from edgy.testing.factory.base import ModelFactory
from edgy.utils.compat import is_class_and_subclass

if TYPE_CHECKING:
    from edgy.testing.factory import FactoryField


def SubFactory(factory_class: Any, **kwargs: Any) -> FactoryField:
    """
    Initializes the SubFactory with a factory class and keyword arguments.

    Args:
        factory_class (Type[Any]): The factory class to use for building or creating instances.
        **kwargs (Any): Additional keyword arguments to pass to the factory class.
    """
    if isinstance(factory_class, str):
        factory_class = monkay.load(factory_class)

    if not is_class_and_subclass(factory_class, ModelFactory):
        raise ValueError(
            f"factory_class must be a subclass of ModelFactory or a string '.' dotted represented of the factory, got {type(factory_class)} instead."
        )
    return cast(type[ModelFactory], factory_class)(**kwargs).to_factory_field()


def ListSubFactory(factory_class: Any, min: int = 0, max: int = 10, **kwargs: Any) -> FactoryField:
    """
    Initializes the SubFactory with a factory class and keyword arguments.

    Args:
        factory_class (Type[Any]): The factory class to use for building or creating instances.
        **kwargs (Any): Additional keyword arguments to pass to the factory class.
    """
    if isinstance(factory_class, str):
        factory_class = monkay.load(factory_class)

    if not is_class_and_subclass(factory_class, ModelFactory):
        raise ValueError(
            f"factory_class must be a subclass of ModelFactory or a string '.' dotted represented of the factory, got {type(factory_class)} instead."
        )
    return cast(type[ModelFactory], factory_class)(**kwargs).to_list_factory_field(
        min=min, max=max
    )
